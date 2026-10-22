"""Bounded, snapshot-consistent literal search and whole-library counts."""
from .errors import ValidationError
from .labels import validate_text
from .tags import normalize_tags


def pagination(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValidationError()
    # Huge Python offsets are deliberately valid empty pages; they are never
    # bound to SQLite unless less than the actual (signed-64-bit) row count.


def search(connection, query, limit, offset, *, view, collection_id, tags):
    from .collections import require_collection
    from .storage import item_from_row
    pagination(limit, offset)
    validate_text(query, max_chars=2000)
    if not isinstance(view, str) or view not in {'all','inbox','favorites','read_later','trash'}:
        raise ValidationError()
    require_collection(connection, collection_id)
    identities = [identity for _,identity in normalize_tags(tags)]
    predicates = ['items.deleted_at IS NOT NULL' if view=='trash' else 'items.deleted_at IS NULL']; parameters = []; source = 'items'
    if query.strip():
        source += ' JOIN items_fts ON items_fts.rowid=items.rowid'
        predicates.append('items_fts MATCH ?')
        parameters.append('"'+query.strip().replace('"','""')+'"')
    if view == 'inbox':
        predicates.append('items.collection_id IS NULL')
    elif view == 'favorites':
        predicates.append('items.favorite=1')
    elif view == 'read_later':
        predicates.append('items.read_later=1')
    if collection_id is not None:
        predicates.append('''items.collection_id IN (WITH RECURSIVE subtree(id,depth) AS (
            SELECT id,1 FROM collections WHERE id=? UNION ALL
            SELECT c.id,s.depth+1 FROM collections c JOIN subtree s ON c.parent_id=s.id WHERE s.depth<16)
            SELECT id FROM subtree)''')
        parameters.append(collection_id)
    for identity in identities:
        predicates.append('''EXISTS (SELECT 1 FROM item_tags it JOIN tags t ON t.id=it.tag_id
            WHERE it.item_id=items.id AND t.identity=? AND (it.manual=1 OR it.generated=1) AND it.suppressed=0)''')
        parameters.append(identity)
    if predicates:
        source += ' WHERE ' + ' AND '.join(predicates)
    total = connection.execute('SELECT count(*) FROM '+source, parameters).fetchone()[0]
    rows = []
    if offset < total:
        rows = connection.execute('SELECT items.* FROM '+source+' ORDER BY items.rowid ASC,items.id ASC LIMIT ? OFFSET ?', (*parameters,limit,offset)).fetchall()
    return {'items':[item_from_row(row,connection) for row in rows], 'total':total, 'limit':limit, 'offset':offset}


def counts(connection):
    row = connection.execute('''SELECT count(*) AS "all",coalesce(sum(collection_id IS NULL),0) AS inbox,
        coalesce(sum(favorite),0) AS favorites,coalesce(sum(read_later),0) AS read_later FROM items WHERE deleted_at IS NULL''').fetchone()
    return {**dict(row),'trash':connection.execute('SELECT count(*) FROM items WHERE deleted_at IS NOT NULL').fetchone()[0]}


def tag_list(connection, query, limit, offset):
    import unicodedata
    pagination(limit, offset); validate_text(query, max_chars=2000)
    identity = unicodedata.normalize('NFC',unicodedata.normalize('NFC',query.strip()).casefold())
    source = '''FROM tags t JOIN item_tags it ON it.tag_id=t.id JOIN items i ON i.id=it.item_id
        WHERE i.deleted_at IS NULL AND (it.manual=1 OR it.generated=1) AND it.suppressed=0 AND instr(t.identity,?)>0'''
    total = connection.execute('SELECT count(DISTINCT t.id) '+source, (identity,)).fetchone()[0]
    rows = []
    if offset < total:
        rows = connection.execute('SELECT t.label AS name,count(*) AS count '+source+
            ' GROUP BY t.id ORDER BY t.identity,t.id LIMIT ? OFFSET ?', (identity,limit,offset)).fetchall()
    return {'tags':[dict(row) for row in rows], 'total':total, 'limit':limit, 'offset':offset}
