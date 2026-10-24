"""Serialized hierarchy mutations; deletion never removes child items."""
import time
import unicodedata
from uuid import uuid4
from .errors import ConflictError, NotFoundError, ValidationError
from .labels import normalize_label, validate_text
from .queries import pagination


def require_collection(connection, collection_id):
    if collection_id is None:
        return None
    validate_text(collection_id, max_chars=100, nonempty=True)
    row = connection.execute('SELECT * FROM collections WHERE id=?', (collection_id,)).fetchone()
    if row is None:
        raise NotFoundError()
    return row


def revision(value):
    if type(value) is not int or not 1 <= value <= 2**63-1:
        raise ValidationError()


def project(row):
    return {key:row[key] for key in ('id','name','parent_id','revision','created_at','updated_at')}


def path(connection, collection_id):
    result = []
    while collection_id is not None:
        if len(result) == 16 or any(part['id'] == collection_id for part in result):
            raise ConflictError()
        row = require_collection(connection, collection_id)
        result.append({'id':row['id'],'name':row['name']})
        collection_id = row['parent_id']
    return list(reversed(result))


def subtree(connection, collection_id):
    return connection.execute('''WITH RECURSIVE subtree(id,depth) AS (
        SELECT id,1 FROM collections WHERE id=? UNION ALL
        SELECT c.id,s.depth+1 FROM collections c JOIN subtree s ON c.parent_id=s.id WHERE s.depth<16)
        SELECT id,depth FROM subtree''', (collection_id,)).fetchall()


def placement(connection, parent_id, identity, *, collection_id=None):
    ancestors = path(connection, parent_id)
    descendants = subtree(connection, collection_id) if collection_id else []
    if any(part['id'] == collection_id for part in ancestors):
        raise ConflictError()
    height = max((row['depth'] for row in descendants), default=1)
    if len(ancestors)+height > 16:
        raise ConflictError()
    sibling = connection.execute('SELECT id FROM collections WHERE parent_id IS ? AND identity=? AND id IS NOT ?',
                                 (parent_id,identity,collection_id)).fetchone()
    if sibling is not None:
        raise ConflictError()


class CollectionStore:
    def __init__(self, storage):
        self.storage = storage

    def create(self, name, parent_id=None):
        display, identity = normalize_label(name, 100)
        with self.storage._transaction(write=True) as connection:
            placement(connection, parent_id, identity)
            key = str(uuid4()); now = time.time()
            connection.execute('INSERT INTO collections(id,name,identity,parent_id,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                               (key,display,identity,parent_id,now,now))
            return project(require_collection(connection,key))

    def update(self, collection_id, expected_revision, changes):
        revision(expected_revision)
        if not isinstance(changes,dict) or set(changes)-{'name','parent_id'}:
            raise ValidationError()
        with self.storage._transaction(write=True) as connection:
            row = require_collection(connection,collection_id)
            if row is None:
                raise ValidationError()
            if row['revision'] != expected_revision:
                raise ConflictError(row['revision'])
            display, identity = normalize_label(changes.get('name',row['name']),100)
            parent_id = changes.get('parent_id',row['parent_id'])
            placement(connection,parent_id,identity,collection_id=collection_id)
            if display != row['name'] or parent_id != row['parent_id']:
                connection.execute('UPDATE collections SET name=?,identity=?,parent_id=?,revision=revision+1,updated_at=? WHERE id=?',
                                   (display,identity,parent_id,time.time(),collection_id))
            return project(require_collection(connection,collection_id))

    def delete(self, collection_id, expected_revision, contents_policy):
        revision(expected_revision)
        if contents_policy not in ('move_to_parent','move_to_inbox'):
            raise ValidationError()
        with self.storage._transaction(write=True) as connection:
            row = require_collection(connection,collection_id)
            if row is None:
                raise ValidationError()
            if row['revision'] != expected_revision:
                raise ConflictError(row['revision'])
            target = row['parent_id'] if contents_policy == 'move_to_parent' else None
            children = connection.execute('SELECT * FROM collections WHERE parent_id=?', (collection_id,)).fetchall()
            for child in children:
                # The deleted row itself is not a surviving sibling; a child may
                # legitimately reuse its name after that row is removed.
                ancestors = path(connection,target)
                if len(ancestors)+max(r['depth'] for r in subtree(connection,child['id'])) > 16:
                    raise ConflictError()
                collision = connection.execute('SELECT id FROM collections WHERE parent_id IS ? AND identity=? AND id NOT IN (?,?)',
                                               (target,child['identity'],collection_id,child['id'])).fetchone()
                if collision is not None:
                    raise ConflictError()
            now = time.time()
            # Rename the soon-deleted identity to avoid a transient uniqueness
            # collision when a child shares its name. This rolls back atomically.
            connection.execute('UPDATE collections SET identity=? WHERE id=?', (uuid4().hex,collection_id))
            connection.execute('UPDATE collections SET parent_id=?,revision=revision+1,updated_at=? WHERE parent_id=?', (target,now,collection_id))
            connection.execute('UPDATE items SET collection_id=?,revision=revision+1,updated_at=? WHERE collection_id=?', (target,now,collection_id))
            connection.execute('DELETE FROM collections WHERE id=?', (collection_id,))
            return {'deleted_id':collection_id}

    def list(self, limit=50, offset=0, *, parent_id=None, query=''):
        pagination(limit,offset); validate_text(query,max_chars=2000)
        with self.storage._transaction() as connection:
            require_collection(connection,parent_id)
            if query.strip():
                where = 'instr(identity,?)>0'
                params = (unicodedata.normalize('NFC',unicodedata.normalize('NFC',query.strip()).casefold()),)
            else:
                where = 'parent_id IS ?'; params = (parent_id,)
            total = connection.execute('SELECT count(*) FROM collections WHERE '+where,params).fetchone()[0]
            rows = []
            if offset < total:
                rows = connection.execute('SELECT * FROM collections WHERE '+where+' ORDER BY identity,id LIMIT ? OFFSET ?',(*params,limit,offset)).fetchall()
            result = []
            for row in rows:
                count = connection.execute('''WITH RECURSIVE subtree(id,depth) AS (
                    SELECT id,1 FROM collections WHERE id=? UNION ALL
                    SELECT c.id,s.depth+1 FROM collections c JOIN subtree s ON c.parent_id=s.id WHERE s.depth<16)
                    SELECT count(*) FROM items WHERE deleted_at IS NULL AND collection_id IN (SELECT id FROM subtree)''', (row['id'],)).fetchone()[0]
                result.append({**project(row),'count':count,'path':path(connection,row['id'])})
            return {'collections':result,'total':total,'limit':limit,'offset':offset}
