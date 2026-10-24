"""Library-owned nonsecret AI settings; callers own snapshot transactions."""
import copy
import json
from .errors import ConflictError, ValidationError, StorageError
from .labels import validate_text
from .tags import normalize_tags

DEFAULTS = {'provider':'','model':'','owner_profile':'','automatic_tags':True,
    'automatic_summary':True,'image_analysis':False,'summary_language':'auto',
    'summary_length':'medium','preferred_tags':[],'guidance':'',
    'retain_extracted_text':False,'paused':False}
ROUTE_FIELDS = {'provider','model','owner_profile'}
OPTION_FIELDS = set(DEFAULTS) - ROUTE_FIELDS - {'paused'}
EDITABLE_FIELDS = set(DEFAULTS) - {'owner_profile'}
BOOL_FIELDS = {'automatic_tags','automatic_summary','image_analysis','retain_extracted_text','paused'}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',',':'))


def validate_changes(changes, *, allow_owner=False):
    if type(changes) is not dict or set(changes) - (set(DEFAULTS) if allow_owner else EDITABLE_FIELDS):
        raise ValidationError()
    clean = copy.deepcopy(changes)
    for key, value in clean.items():
        if key in BOOL_FIELDS:
            if type(value) is not bool: raise ValidationError()
        elif key in ROUTE_FIELDS:
            validate_text(value,max_chars=300)
            if value and (not value.strip() or '://' in value or '@' in value or any(ch.isspace() for ch in value)):
                raise ValidationError()
        elif key == 'summary_language':
            validate_text(value,max_chars=80,nonempty=True)
            if not value.strip(): raise ValidationError()
        elif key == 'summary_length':
            if type(value) is not str or value not in {'short','medium','long'}: raise ValidationError()
        elif key == 'guidance':
            validate_text(value,max_chars=2000,max_bytes=8000)
        elif key == 'preferred_tags':
            clean[key] = [name for name,_ in normalize_tags(value)]
    return clean


def validate_settings(value):
    if type(value) is not dict or set(value) != set(DEFAULTS): raise ValidationError()
    return validate_changes(value,allow_owner=True)


def _load(raw):
    try:
        return json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError,TypeError,RecursionError): raise StorageError() from None


def _put(c,key,value):
    c.execute('INSERT INTO library_config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))


def persist(c,settings,revision):
    _put(c,'enrichment_settings',encoded(settings))
    _put(c,'enrichment_settings_revision',str(revision))
    # Legacy route consumers remain pinned until all admission paths use snapshots.
    route = {key:settings[key] for key in sorted(ROUTE_FIELDS) if settings[key]}
    if route: _put(c,'enrichment_route',json.dumps(route,sort_keys=True))
    else: c.execute("DELETE FROM library_config WHERE key='enrichment_route'")


def initialize(c):
    settings=copy.deepcopy(DEFAULTS)
    route=c.execute("SELECT value FROM library_config WHERE key='enrichment_route'").fetchone()
    if route:
        value=_load(route['value'])
        if type(value) is not dict or set(value)-ROUTE_FIELDS: raise StorageError()
        try: settings.update(validate_changes(value,allow_owner=True))
        except ValidationError: raise StorageError() from None
    persist(c,settings,1)


def read_settings(c):
    rows=dict(c.execute("SELECT key,value FROM library_config WHERE key IN ('enrichment_settings','enrichment_settings_revision','restored_enrichment_settings')"))
    if 'enrichment_settings' not in rows or 'enrichment_settings_revision' not in rows: raise StorageError()
    try:
        settings=validate_settings(_load(rows['enrichment_settings']))
        raw=rows['enrichment_settings_revision']
        if not raw.isascii() or not raw.isdecimal(): raise ValueError()
        revision=int(raw)
        if not 1<=revision<=2**63-1: raise ValueError()
        restored=validate_settings(_load(rows['restored_enrichment_settings'])) if 'restored_enrichment_settings' in rows else None
    except (ValidationError,ValueError,TypeError): raise StorageError() from None
    return {'revision':revision,'settings':settings,
        'route_ready':all(settings[key] for key in ROUTE_FIELDS),'restored_intent':restored}


def snapshot_settings(c):
    value=read_settings(c); settings=value['settings']
    return {'version':2,'settings_revision':value['revision'],
        'route':{key:settings[key] for key in sorted(ROUTE_FIELDS)},
        'options':{key:copy.deepcopy(settings[key]) for key in sorted(OPTION_FIELDS)}}


def seed_route(c,route):
    if type(route) is not dict or set(route)!=ROUTE_FIELDS or not all(route.values()): raise ValidationError()
    validate_changes(route,allow_owner=True)
    value=read_settings(c);settings=value['settings']; owner=settings['owner_profile']
    if owner and owner!=route['owner_profile']: raise ConflictError()
    if owner: return value
    # Only a genuinely untouched initial route may inherit bootstrap identifiers.
    if value['revision']==1 and not settings['provider'] and not settings['model']:
        settings.update(route)
    else: settings['owner_profile']=route['owner_profile']
    if value['revision']==2**63-1: raise ConflictError(value['revision'])
    persist(c,settings,value['revision']+1)
    return read_settings(c)


class SettingsStore:
    def __init__(self,storage): self.storage=storage

    def get(self):
        with self.storage._transaction() as c: return read_settings(c)

    def seed_route(self,route):
        with self.storage._transaction(write=True) as c: return seed_route(c,route)

    def update(self,expected_revision,changes):
        if type(expected_revision) is not int or not 1<=expected_revision<=2**63-1: raise ValidationError()
        changes=validate_changes(changes)
        with self.storage._transaction(write=True) as c:
            current=read_settings(c)
            if current['revision']!=expected_revision: raise ConflictError(current['revision'])
            updated={**current['settings'],**changes}
            if updated!=current['settings']:
                if expected_revision==2**63-1: raise ConflictError(expected_revision)
                persist(c,updated,expected_revision+1)
            return read_settings(c)
