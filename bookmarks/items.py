"""Atomic capture, revision-safe metadata, notes, and owned image associations."""
import hashlib
import json
import re
import time
from uuid import uuid4

from .collections import require_collection, revision
from .errors import ConflictError, NotFoundError, ValidationError
from .labels import validate_text
from .tags import normalize_tags, apply_manual
from .urls import validate_url

EDIT_FIELDS = {'title','description','notes','collection_id','favorite','read_later','add_tags','remove_tags','attachment_ids'}


def validate_operation_key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',value):
        raise ValidationError()
    return value


def optional_collection(value):
    if value is not None:
        validate_text(value,max_chars=100,nonempty=True)
    return value


def asset_id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):
        raise ValidationError()
    return value


def attachment_ids(values):
    if not isinstance(values,(tuple,list)) or len(values)>10:
        raise ValidationError()
    result = [asset_id(value) for value in values]
    if len(set(result)) != len(result):
        raise ValidationError()
    return result


def metadata(values):
    result = dict(values)
    for key in ('title','description','notes'):
        if key in result:
            validate_text(result[key],max_chars=1000 if key=='title' else None,
                          max_bytes={'title':None,'description':16384,'notes':65536}[key])
    for key in ('favorite','read_later'):
        if key in result and type(result[key]) is not bool:
            raise ValidationError()
    if 'collection_id' in result:
        optional_collection(result['collection_id'])
    if 'attachment_ids' in result:
        result['attachment_ids'] = attachment_ids(result['attachment_ids'])
    for key in ('add_tags','remove_tags'):
        if key in result:
            result[key] = normalize_tags(result[key])
    if {key for _,key in result.get('add_tags',[])} & {key for _,key in result.get('remove_tags',[])}:
        raise ValidationError()
    return result


def require_assets(connection, ids):
    for key in ids:
        row = connection.execute('SELECT * FROM assets WHERE id=?',(key,)).fetchone()
        if row is None:
            raise NotFoundError()
        if (row['mime_type'] not in {'image/png','image/jpeg','image/webp'} or
            not 0 < row['size'] <= 10*1024*1024 or not 0 < row['width']*row['height'] <= 20_000_000):
            raise ValidationError()


def load(connection, item_id, expected_revision=None):
    validate_text(item_id,max_chars=100,nonempty=True)
    row = connection.execute('SELECT * FROM items WHERE id=?',(item_id,)).fetchone()
    if row is None:
        raise NotFoundError()
    if expected_revision is not None and row['revision'] != expected_revision:
        raise ConflictError(row['revision'])
    return row


def project(connection, item_id):
    from .storage import item_from_row
    return item_from_row(load(connection,item_id),connection)


def receipt(row):
    return {key:row[key] for key in ('operation_key','item_id','accepted_revision','outcome')}


def associations(connection, item_id, primary, ids):
    if len(ids)+(1 if primary else 0)>10 or primary in ids:
        raise ValidationError()
    require_assets(connection, [*([primary] if primary else []), *ids])
    connection.execute("DELETE FROM item_assets WHERE item_id=? AND role='attachment'",(item_id,))
    for key in ids:
        connection.execute("INSERT INTO item_assets(item_id,asset_id,role) VALUES(?,?,'attachment')",(item_id,key))


class ItemStore:
    def __init__(self, storage):
        self.storage = storage

    def capture(self, *, kind='link', url=None, title='', description='', notes='', collection_id=None,
                tags=(), favorite=False, read_later=False, primary_asset_id=None, attachment_ids=(),
                operation_key=None, enrichment_settings=None):
        values = metadata({'title':title,'description':description,'notes':notes,'collection_id':collection_id,
                           'favorite':favorite,'read_later':read_later,'attachment_ids':attachment_ids})
        labels = normalize_tags(tags)
        if not isinstance(kind,str) or kind not in {'link','image'}:
            raise ValidationError()
        if operation_key is not None:
            validate_operation_key(operation_key)
        if kind=='link':
            validate_url(url)
            if primary_asset_id is not None:
                raise ValidationError()
        elif url is not None or operation_key is None or primary_asset_id is None:
            raise ValidationError()
        else:
            asset_id(primary_asset_id)
        ids = values.pop('attachment_ids')
        if len(ids)+(1 if primary_asset_id else 0)>10 or primary_asset_id in ids:
            raise ValidationError()
        payload = {**values,'kind':kind,'url':url,'tags':[name for name,_ in labels],
                   'primary_asset_id':primary_asset_id,'attachment_ids':ids}
        digest = hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
        with self.storage._transaction(write=True) as connection:
            if operation_key is not None:
                prior = connection.execute('SELECT * FROM capture_operations WHERE operation_key=?',(operation_key,)).fetchone()
                if prior is not None:
                    if prior['payload_hash'] != digest:
                        raise ConflictError()
                    return {'item':project(connection,prior['item_id']),'receipt':receipt(prior)}
            existing = connection.execute('SELECT id,deleted_at FROM items WHERE url=?',(url,)).fetchone() if kind=='link' else None
            outcome = ('trashed_duplicate' if existing['deleted_at'] is not None else 'duplicate') if existing is not None else 'created'
            if existing is not None:
                item_id = existing['id']
            else:
                require_collection(connection,collection_id)
                require_assets(connection,[*([primary_asset_id] if primary_asset_id else []),*ids])
                item_id = str(uuid4()); now = time.time()
                connection.execute('''INSERT INTO items(id,kind,url,title,description,notes,collection_id,
                    favorite,read_later,primary_asset_id,created_at,updated_at,enrichment_status)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (item_id,kind,url,title,description,notes,collection_id,favorite,read_later,primary_asset_id,
                     now,now,'not_configured' if kind=='image' else 'not_started'))
                if primary_asset_id:
                    connection.execute("INSERT INTO item_assets(item_id,asset_id,role) VALUES(?,?,'primary')",(item_id,primary_asset_id))
                associations(connection,item_id,primary_asset_id,ids)
                apply_manual(connection,item_id,labels,[])
            row = load(connection,item_id)
            if kind=='link' and row['deleted_at'] is None and enrichment_settings is not None and row['enrichment_status']=='not_started':
                from .jobs import validate_settings
                encoded = validate_settings(enrichment_settings)
                prior_job = connection.execute('SELECT id FROM jobs WHERE item_id=? AND revision=?',(item_id,row['revision'])).fetchone()
                if prior_job is None:
                    job_id = str(uuid4())
                    generation = row['enrichment_generation']+(1 if outcome=='duplicate' else 0)
                    connection.execute('INSERT INTO jobs(id,item_id,revision,generation,settings) VALUES(?,?,?,?,?)',
                                       (job_id,item_id,row['revision'],generation,encoded))
                    connection.execute("UPDATE items SET enrichment_status='pending',enrichment_job_id=?,enrichment_generation=? WHERE id=?",(job_id,generation,item_id))
            item = project(connection,item_id)
            result_receipt = None
            if operation_key is not None:
                connection.execute('INSERT INTO capture_operations(operation_key,payload_hash,item_id,accepted_revision,outcome) VALUES(?,?,?,?,?)',
                                   (operation_key,digest,item_id,item['revision'],outcome))
                result_receipt = receipt(connection.execute('SELECT * FROM capture_operations WHERE operation_key=?',(operation_key,)).fetchone())
            return {'item':item,'receipt':result_receipt}

    def capture_status(self, key):
        validate_operation_key(key)
        with self.storage._transaction() as connection:
            row = connection.execute('SELECT * FROM capture_operations WHERE operation_key=?',(key,)).fetchone()
            if row is None:
                raise NotFoundError()
            return {'item':project(connection,row['item_id']),'receipt':receipt(row)}

    def update(self, item_id, expected_revision, changes):
        revision(expected_revision)
        if not isinstance(changes,dict) or set(changes)-EDIT_FIELDS:
            raise ValidationError()
        values = metadata(changes)
        with self.storage._transaction(write=True) as connection:
            row = load(connection,item_id,expected_revision)
            if row['deleted_at'] is not None: raise ConflictError(row['revision'])
            return self._update(connection,row,values)

    def _update(self, connection, row, values):
        item_id = row['id']; before = project(connection,item_id)
        old_tags = [tuple(tag) for tag in connection.execute('SELECT tag_id,manual,generated,suppressed FROM item_tags WHERE item_id=? ORDER BY tag_id',(item_id,))]
        if 'collection_id' in values:
            require_collection(connection,values['collection_id'])
        if 'attachment_ids' in values:
            associations(connection,item_id,row['primary_asset_id'],values['attachment_ids'])
        if 'add_tags' in values or 'remove_tags' in values:
            apply_manual(connection,item_id,values.get('add_tags',[]),values.get('remove_tags',[]))
        scalars = {key:value for key,value in values.items() if key not in {'add_tags','remove_tags','attachment_ids'}}
        if scalars:
            # Keys originate only from EDIT_FIELDS; values are always bound.
            connection.execute('UPDATE items SET '+','.join(key+'=?' for key in scalars)+' WHERE id=?',(*scalars.values(),item_id))
        after = project(connection,item_id)
        new_tags = [tuple(tag) for tag in connection.execute('SELECT tag_id,manual,generated,suppressed FROM item_tags WHERE item_id=? ORDER BY tag_id',(item_id,))]
        if before != after or old_tags != new_tags:
            connection.execute('UPDATE items SET revision=revision+1,updated_at=? WHERE id=?',(time.time(),item_id))
        return project(connection,item_id)

    def note_update(self, item_id, expected_revision, text, mode='replace'):
        revision(expected_revision); validate_text(text,max_bytes=65536)
        if mode not in ('append','replace'):
            raise ValidationError()
        with self.storage._transaction(write=True) as connection:
            row = load(connection,item_id,expected_revision)
            if row['deleted_at'] is not None: raise ConflictError(row['revision'])
            final = row['notes']+text if mode=='append' else text
            return self._update(connection,row,metadata({'notes':final}))
