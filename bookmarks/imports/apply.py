"""Apply one row in the same transaction as the cursor and its report."""
import time
from uuid import uuid4
from ..collections import placement
from ..errors import BookmarkError
from ..items import ItemStore
from ..labels import normalize_label
from .records import record


def collection_path(c,parts):
    parent=None
    for name in parts:
        label,key=normalize_label(name,100)
        row=c.execute('SELECT id FROM collections WHERE parent_id IS ? AND identity=?',(parent,key)).fetchone()
        if row:parent=row['id'];continue
        placement(c,parent,key);now=time.time();identity=uuid4().hex
        c.execute('INSERT INTO collections(id,name,identity,parent_id,created_at,updated_at) VALUES(?,?,?,?,?,?)',(identity,label,key,parent,now,now));parent=identity
    return parent


def apply_record(storage,c,staged,job,index,settings):
    warnings=list(staged['warnings'])
    if staged['error_code']:return 'failed',None,staged['error_code'],warnings
    source=staged['record']
    existing=c.execute('SELECT id FROM items WHERE url=?',(source['url'],)).fetchone()
    if existing:return 'skipped',existing['id'],None,warnings
    # A savepoint prevents a failed source row from leaving empty collections.
    c.execute('SAVEPOINT import_row')
    try:
        clean,_=record(c,source)
        parent=collection_path(c,clean['collection_path'])
        saved=ItemStore(storage).capture(url=clean['url'],title=clean['title'],description=clean['description'],notes=clean['notes'],
            collection_id=parent,tags=clean['tags'],attachment_ids=clean['attachment_ids'],enrichment_settings=settings,_connection=c)
        key=saved['item']['id']
        c.execute('''INSERT INTO import_provenance VALUES(?,?,?,?,?,?,?,?)''',
            (key,job['id'],index,clean['source_id'],clean['provenance']['source'],clean['provenance']['locator'],clean['imported_summary'],clean['source_text']))
        c.execute('RELEASE import_row')
        return 'imported',key,None,warnings
    except BookmarkError as error:
        # Storage faults must abort the entire row+cursor transaction, not become
        # a misleading per-record validation failure after uncertain I/O.
        from ..errors import StorageError
        if isinstance(error,StorageError):raise
        c.execute('ROLLBACK TO import_row');c.execute('RELEASE import_row')
        return 'failed',None,error.code,warnings
