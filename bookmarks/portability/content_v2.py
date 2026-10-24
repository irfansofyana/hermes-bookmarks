"""Version-two content: summary ownership, retained bodies and inert settings.

All version-one graph/type/ordering invariants are reused without changing its
validator. The extended shape is exact and its whole JSON budget includes the
new fields. Restore owns only a savepoint inside its caller's transaction: no
asset publication, receipts, live configuration, identity or executable jobs.
"""
import json

from ..errors import ValidationError
from ..labels import validate_text
from ..settings import DEFAULTS, read_settings, validate_settings
from . import content_v1

MAX_JSON_BYTES = content_v1.MAX_JSON_BYTES
NEW_ITEM_FIELDS = ('summary_source', 'summary_revision', 'extracted_text', 'generated_provenance')
FIELDS = {**content_v1.FIELDS, 'items': (*content_v1.FIELDS['items'], *NEW_ITEM_FIELDS)}
PROVENANCE_FIELDS = {'provider', 'model', 'coverage', 'applied_fields', 'conflicted_fields'}
MAX_PROVENANCE_BYTES = 4096


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def _size(data):
    try:
        size = 0
        for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',', ':')).iterencode(data):
            size += len(chunk.encode('utf-8'))
            if size > MAX_JSON_BYTES:
                raise ValidationError()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValidationError() from None


def _settings(value):
    # The settings API may normalize edit inputs. A backup is already stored
    # content: reject a noncanonical value rather than silently changing it.
    clean = validate_settings(value)
    if type(value['preferred_tags']) is not list or clean != value:
        raise ValidationError()


def _fields(value):
    if type(value) is not list or any(type(field) is not str or field not in ('summary', 'tags') for field in value):
        raise ValidationError()
    if value != [field for field in ('summary', 'tags') if field in value]:
        raise ValidationError()


def _provenance(value):
    if value is None:
        return
    validate_text(value, max_bytes=MAX_PROVENANCE_BYTES)

    def pairs(entries):
        result = {}
        for key, member in entries:
            if key in result:
                raise ValueError()
            result[key] = member
        return result

    def constant(_):
        raise ValueError()

    try:
        result = json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
        if type(result) is not dict or set(result) != PROVENANCE_FIELDS:
            raise ValidationError()
        for key in ('provider', 'model'):
            validate_text(result[key], max_chars=300)
        if type(result['coverage']) is not str or result['coverage'] not in ('extracted_text', 'owned_image'):
            raise ValidationError()
        _fields(result['applied_fields'])
        _fields(result['conflicted_fields'])
        if (not result['applied_fields'] and not result['conflicted_fields']
                or set(result['applied_fields']) & set(result['conflicted_fields'])):
            raise ValidationError()
        if _encoded(result) != value:
            raise ValidationError()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValidationError() from None


def _base(data):
    return {**{key: data[key] for key in content_v1.TABLES},
            'items': [{field: row[field] for field in content_v1.FIELDS['items']} for row in data['items']],
            'settings': {}}


def validate_content(data) -> None:
    if type(data) is not dict or set(data) != {*content_v1.TABLES, 'settings'}:
        raise ValidationError()
    for key in content_v1.TABLES:
        rows = data[key]
        if type(rows) is not list or len(rows) > content_v1.LIMITS[key]:
            raise ValidationError()
        if any(type(row) is not dict or set(row) != set(FIELDS[key]) for row in rows):
            raise ValidationError()
    _size(data)
    content_v1.validate_content(_base(data))
    settings = data['settings']
    if type(settings) is not dict or set(settings) - {'enrichment_settings'}:
        raise ValidationError()
    if 'enrichment_settings' in settings:
        _settings(settings['enrichment_settings'])
    for row in data['items']:
        if type(row['summary_source']) is not str or row['summary_source'] not in ('none', 'legacy', 'generated', 'manual'):
            raise ValidationError()
        content_v1._integer(row['summary_revision'])
        validate_text(row['extracted_text'], max_chars=30000)
        _provenance(row['generated_provenance'])


def snapshot(connection) -> dict:
    content_v1._transaction(connection)
    data = {}
    for key, table in content_v1.TABLES.items():
        rows = [dict(row) for row in connection.execute('SELECT rowid,* FROM ' + table + ' ORDER BY rowid')]
        if key == 'items':
            for row in rows:
                row.pop('enrichment_job_id', None)
                row.pop('enrichment_generation', None)
        data[key] = rows
    value = read_settings(connection)
    # Destination initialization is not adoption. Re-export the inert incoming
    # intent until an explicit settings operation removes that separate record.
    intent = value['restored_intent'] if value['restored_intent'] is not None else value['settings']
    if value['restored_intent'] is None:
        legacy = connection.execute("SELECT value FROM library_config WHERE key='restored_enrichment_route'").fetchone()
        if legacy:
            route = content_v1._json(legacy['value'])
            if type(route) is not dict or set(route) - content_v1.ROUTE_FIELDS:
                raise ValidationError()
            # Pre-upgrade restores may only have the old inert key. Preserve
            # compatible intent; fail closed instead of silently dropping old
            # spellings that the stricter v2 settings boundary cannot carry.
            intent = validate_settings({**DEFAULTS, **route})
    data['settings'] = {'enrichment_settings': intent}
    validate_content(data)
    return data


def restore_content(connection, data) -> None:
    content_v1._transaction(connection)
    validate_content(data)
    connection.execute('SAVEPOINT portable_content_v2_restore')
    try:
        # The old insertion path retains all rowid, hierarchy, cache, source and
        # history rules; none of its v1 settings are passed as live configuration.
        content_v1.restore_content(connection, _base(data))
        for row in data['items']:
            connection.execute('UPDATE items SET ' + ','.join(field + '=?' for field in NEW_ITEM_FIELDS) + ' WHERE id=?',
                               (*[row[field] for field in NEW_ITEM_FIELDS], row['id']))
        if 'enrichment_settings' in data['settings']:
            connection.execute("""INSERT INTO library_config(key,value) VALUES('restored_enrichment_settings',?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                               (_encoded(data['settings']['enrichment_settings']),))
        connection.execute('RELEASE portable_content_v2_restore')
    except BaseException:
        connection.execute('ROLLBACK TO portable_content_v2_restore')
        connection.execute('RELEASE portable_content_v2_restore')
        raise
