"""Version-one raw content projection and atomic empty-target restore.

The eight public keys are fixed. All table values are rowid-ordered lists of
raw SQLite column dictionaries (including rowid); ``sources`` maps to
content_sources. ``settings`` is a dictionary containing only the optional
``enrichment_route`` object (provider/model/owner_profile). Restored route intent
is never activated. processing_history is nullable TEXT containing a JSON list
of historical processing-status strings; original text is retained unchanged
unless a pending/running state must be appended during restore.

Callers own a consistent SQLite transaction and asset-byte publication. This
module performs no filesystem, provider, worker, receipt or identity operations.
"""
import json
import math
import re

from ..errors import ConflictError, ValidationError
from ..labels import normalize_label, validate_text

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_INTEGER = 2**63 - 1
TABLES = {
    'items': 'items', 'collections': 'collections', 'tags': 'tags',
    'item_tags': 'item_tags', 'item_assets': 'item_assets',
    'assets': 'assets', 'sources': 'content_sources',
}
LIMITS = {'items':10000, 'collections':10000, 'tags':20000,
          'item_tags':200000, 'item_assets':100000, 'assets':10000, 'sources':200000}
FIELDS = {
    'items': ('rowid','id','url','title','revision','enrichment_status','summary','tags',
              'kind','description','notes','collection_id','favorite','read_later',
              'primary_asset_id','created_at','updated_at','deleted_at','processing_history'),
    'collections': ('rowid','id','name','identity','parent_id','revision','created_at','updated_at'),
    'tags': ('rowid','id','label','identity'),
    'item_tags': ('rowid','item_id','tag_id','manual','generated','suppressed','label'),
    'item_assets': ('rowid','item_id','asset_id','role'),
    'assets': ('rowid','id','mime_type','size','width','height'),
    'sources': ('rowid','item_id','source_id','source','locator','imported_summary','source_text'),
}
STATES = {'not_started','not_configured','pending','running','succeeded','failed','cancelled','needs_review'}
ROUTE_FIELDS = {'provider','model','owner_profile'}


def snapshot(connection) -> dict:
    """Read one caller-owned consistent snapshot without projecting away aliases."""
    _transaction(connection)
    data = {}
    for key, table in TABLES.items():
        rows = [dict(row) for row in connection.execute('SELECT rowid,* FROM '+table+' ORDER BY rowid')]
        if key == 'items':
            for row in rows:
                row.pop('enrichment_job_id', None)
                row.pop('enrichment_generation', None)
                # Explicit v1 projection is a compatibility boundary, not a
                # lossy full-backup export option. Keep its validator frozen.
                for field in ('summary_source','summary_revision','extracted_text','generated_provenance'):
                    row.pop(field, None)
        data[key] = rows
    row = connection.execute("""SELECT value FROM library_config
        WHERE key IN ('enrichment_route','restored_enrichment_route')
        ORDER BY CASE key WHEN 'enrichment_route' THEN 0 ELSE 1 END LIMIT 1""").fetchone()
    data['settings'] = {'enrichment_route': _json(row['value'])} if row else {}
    # Export must fail rather than silently lose unsupported or oversized data.
    validate_content(data)
    return data


def _transaction(connection):
    if not connection.in_transaction:
        raise ValidationError()


def _json(value):
    validate_text(value)
    try:
        return json.loads(value, parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError):
        raise ValidationError() from None


def _integer(value, minimum=0, maximum=MAX_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError()


def _identity(value):
    validate_text(value, max_chars=100, nonempty=True)


def _timestamp(value, nullable=False):
    if value is None and nullable:
        return
    if type(value) not in (int, float):
        raise ValidationError()
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValidationError()


def _reference(value, index, nullable=False):
    if value is None and nullable:
        return
    _identity(value)
    if value not in index:
        raise ValidationError()


def _index(rows):
    result = {}
    for row in rows:
        _identity(row['id'])
        if row['id'] in result:
            raise ValidationError()
        result[row['id']] = row
    return result


def _label(display, identity, maximum, *, canonical=False):
    label, key = normalize_label(display, maximum)
    if identity != key or (canonical and label != display):
        raise ValidationError()


def _history(value):
    if value is None:
        return []
    result = _json(value)
    if type(result) is not list or any(type(state) is not str or state not in STATES for state in result):
        raise ValidationError()
    return result


def validate_content(data) -> None:
    """Reject any v1 field/type/graph/limit with no exact supported meaning.

    Unlike new captures, stored legacy URLs are data, not executable hrefs. Tag
    JSON and membership labels keep original normalization aliases verbatim.
    Unknown fields are never discarded. This function never opens user storage.
    """
    if type(data) is not dict or set(data) != {*TABLES, 'settings'}:
        raise ValidationError()
    for key in TABLES:
        rows = data[key]
        if type(rows) is not list or len(rows) > LIMITS[key]:
            raise ValidationError()
        previous = 0
        for row in rows:
            if type(row) is not dict or set(row) != set(FIELDS[key]):
                raise ValidationError()
            _integer(row['rowid'], 1)
            if row['rowid'] <= previous:
                raise ValidationError()
            previous = row['rowid']
    try:
        size = 0
        for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',',':')).iterencode(data):
            size += len(chunk.encode('utf-8'))
            if size > MAX_JSON_BYTES:
                raise ValidationError()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValidationError() from None
    settings = data['settings']
    if type(settings) is not dict or set(settings) - {'enrichment_route'}:
        raise ValidationError()
    if 'enrichment_route' in settings:
        route = settings['enrichment_route']
        if type(route) is not dict or set(route) - ROUTE_FIELDS:
            raise ValidationError()
        for value in route.values():
            validate_text(value, max_chars=300, nonempty=True)
            if not value.strip():
                raise ValidationError()
    items = _index(data['items'])
    collections = _index(data['collections'])
    tags = _index(data['tags'])
    assets = _index(data['assets'])
    siblings = set()
    for row in collections.values():
        _label(row['name'], row['identity'], 100, canonical=True)
        _reference(row['parent_id'], collections, nullable=True)
        _integer(row['revision'], 1)
        _timestamp(row['created_at']); _timestamp(row['updated_at'])
        sibling = (row['parent_id'], row['identity'])
        if sibling in siblings:
            raise ValidationError()
        siblings.add(sibling)
        seen = set(); current = row['id']
        while current is not None:
            if current in seen or len(seen) == 16:
                raise ValidationError()
            seen.add(current)
            current = collections[current]['parent_id']
            _reference(current, collections, nullable=True)
    identities = set()
    for row in tags.values():
        _label(row['label'], row['identity'], 80, canonical=True)
        if row['identity'] in identities:
            raise ValidationError()
        identities.add(row['identity'])
    for row in assets.values():
        if not re.fullmatch('[a-f0-9]{32}', row['id']):
            raise ValidationError()
        if type(row['mime_type']) is not str or row['mime_type'] not in {'image/png','image/jpeg','image/webp'}:
            raise ValidationError()
        _integer(row['size'], 1, 10*1024*1024)
        _integer(row['width'], 1, 20_000_000); _integer(row['height'], 1, 20_000_000)
        if row['width'] * row['height'] > 20_000_000:
            raise ValidationError()
    urls = set(); caches = {}
    for row in items.values():
        _integer(row['revision'], 1)
        for flag in ('favorite','read_later'):
            _integer(row[flag], 0, 1)
        for field in ('created_at','updated_at'):
            _timestamp(row[field])
        _timestamp(row['deleted_at'], nullable=True)
        # Schema-five captures had no title limit; the portable JSON quota is
        # the bound for that valid legacy data, not today's new-capture limit.
        validate_text(row['title'])
        validate_text(row['description'], max_bytes=16384)
        validate_text(row['notes'], max_bytes=65536)
        validate_text(row['summary'], max_chars=16000)
        if type(row['enrichment_status']) is not str or row['enrichment_status'] not in STATES:
            raise ValidationError()
        _history(row['processing_history'])
        _reference(row['collection_id'], collections, nullable=True)
        if row['kind'] == 'link':
            validate_text(row['url'], nonempty=True)
            if row['primary_asset_id'] is not None or row['url'] in urls:
                raise ValidationError()
            urls.add(row['url'])
        elif row['kind'] == 'image':
            if row['url'] is not None:
                raise ValidationError()
            _reference(row['primary_asset_id'], assets)
        else:
            raise ValidationError()
        labels = _json(row['tags'])
        if type(labels) is not list or len(labels) > 20:
            raise ValidationError()
        # Do not enforce uniqueness or NFC display on legacy cache spellings.
        caches[row['id']] = {normalize_label(label,80)[1] for label in labels}
    pairs = set(); effective = {key:set() for key in items}
    for row in data['item_tags']:
        _reference(row['item_id'], items); _reference(row['tag_id'], tags)
        pair = (row['item_id'], row['tag_id'])
        if pair in pairs:
            raise ValidationError()
        pairs.add(pair)
        for flag in ('manual','generated','suppressed'):
            _integer(row[flag], 0, 1)
        identity = tags[row['tag_id']]['identity']
        if row['label'] is not None:
            _label(row['label'], identity, 80)
        if (row['manual'] or row['generated']) and not row['suppressed']:
            effective[row['item_id']].add(identity)
    if caches != effective or any(len(values) > 20 for values in effective.values()):
        raise ValidationError()
    pairs = set(); primary = {}; association_counts = {}
    for row in data['item_assets']:
        _reference(row['item_id'], items); _reference(row['asset_id'], assets)
        pair = (row['item_id'], row['asset_id'])
        if pair in pairs or row['role'] not in ('primary','attachment'):
            raise ValidationError()
        pairs.add(pair)
        count = association_counts.get(row['item_id'], 0) + 1
        association_counts[row['item_id']] = count
        if count > 10:
            raise ValidationError()
        if row['role'] == 'primary':
            if row['item_id'] in primary:
                raise ValidationError()
            primary[row['item_id']] = row['asset_id']
    for row in items.values():
        if primary.get(row['id']) != row['primary_asset_id']:
            raise ValidationError()
    for row in data['sources']:
        _reference(row['item_id'], items)
        for key, maximum in (('source_id',300),('source',300),('locator',300),('imported_summary',16000),('source_text',30000)):
            validate_text(row[key], max_chars=maximum)


def empty(connection) -> bool:
    """Operational jobs/configuration/receipts are not content."""
    return not any(connection.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone()
                   for table in ('items','collections','tags','assets','content_sources'))


def _insert(connection, key, row):
    fields = FIELDS[key]
    if key == 'items' and any(column['name'] == 'summary_source' for column in connection.execute('PRAGMA table_info(items)')):
        # Migration ran before restoration, so legacy ownership must be set
        # here rather than waiting for the already-consumed migration backfill.
        fields = (*fields, 'summary_source')
        row = {**row, 'summary_source': 'legacy' if row['summary'] else 'none'}
    connection.execute('INSERT INTO '+TABLES[key]+'('+','.join(fields)+') VALUES('
                       + ','.join('?' for _ in fields)+')', tuple(row[field] for field in fields))


def restore_content(connection, data) -> None:
    """Restore only in the caller transaction; never commit or start work.

    Explicit rowids preserve original ordering even when hierarchy insertion
    requires parents first. A private savepoint also makes statement failures
    atomic if a caller catches them without rolling back its outer transaction.
    """
    _transaction(connection)
    validate_content(data)
    if not empty(connection):
        raise ConflictError()
    connection.execute('SAVEPOINT portable_content_restore')
    try:
        for row in data['assets']:
            _insert(connection, 'assets', row)
        collections = {row['id']:row for row in data['collections']}
        def depth(row):
            result = 0
            while row['parent_id'] is not None:
                result += 1; row = collections[row['parent_id']]
            return result
        for row in sorted(data['collections'], key=depth):
            _insert(connection, 'collections', row)
        for original in data['items']:
            row = dict(original)
            if row['enrichment_status'] in {'pending','running'}:
                row['processing_history'] = json.dumps([*_history(row['processing_history']),row['enrichment_status']], ensure_ascii=False)
                row['enrichment_status'] = 'needs_review'
            _insert(connection, 'items', row)
        for key in ('tags','item_tags','item_assets','sources'):
            for row in data[key]:
                _insert(connection, key, row)
        if 'enrichment_route' in data['settings']:
            connection.execute("""INSERT INTO library_config(key,value) VALUES('restored_enrichment_route',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (json.dumps(data['settings']['enrichment_route'], ensure_ascii=False, sort_keys=True),))
            # Retain the exact old route above even if it has a spelling that
            # newer editable-settings rules disallow. Represent compatible old
            # intent in the schema-11 settings API without activating it.
            from ..settings import DEFAULTS, validate_settings
            intent = {**DEFAULTS, **data['settings']['enrichment_route']}
            try:
                intent = validate_settings(intent)
            except ValidationError:
                pass
            else:
                connection.execute("""INSERT INTO library_config(key,value) VALUES('restored_enrichment_settings',?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                    (json.dumps(intent, ensure_ascii=False, sort_keys=True, separators=(',',':')),))
        connection.execute('RELEASE portable_content_restore')
    except BaseException:
        connection.execute('ROLLBACK TO portable_content_restore')
        connection.execute('RELEASE portable_content_restore')
        raise
