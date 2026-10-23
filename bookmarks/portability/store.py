"""Owned, bounded portability operations; no workers, paths or inference API."""
import base64
import binascii
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import uuid4
from ..errors import ValidationError, ConflictError, NotFoundError, StorageError
from ..items import validate_operation_key

MAX_BYTES=512*1024*1024
CHUNK_BYTES=32768
TTL=86400

def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def digest_bytes(value):return hashlib.sha256(value).hexdigest()
def identifier(value):
 if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValidationError()
 return value

def sha(value):
 if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value):raise ValidationError()
 return value

def integer(value,maximum=MAX_BYTES):
 if type(value) is not int or not 0<=value<=maximum:raise ValidationError()
 return value

class PortabilityStore:
 def __init__(self,storage):
  self.storage=storage;self.root=storage.database_path.parent;self.folder=self.root/'portability'
  if self.folder.is_symlink():raise StorageError()
  self.folder.mkdir(mode=0o700,exist_ok=True)
  if not self.folder.is_dir():raise StorageError()

 @contextmanager
 def _file(self,name,mode='rb',folder=None,exclusive=False):
  # Names are generated IDs with a fixed suffix, never values from an archive.
  if not re.fullmatch(r'[a-f0-9]{32}\.(blob|part|ready)',name):raise ValidationError()
  directory=self.folder if folder is None else folder
  if directory.is_symlink() or not directory.is_dir():raise StorageError()
  flags=os.O_RDONLY if mode=='rb' else os.O_RDWR
  if exclusive:flags|=os.O_CREAT|os.O_EXCL
  flags|=getattr(os,'O_NOFOLLOW',0)
  descriptor=None
  try:
   descriptor=os.open(directory/name,flags,0o600)
   info=os.fstat(descriptor)
   if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise StorageError()
   with os.fdopen(descriptor,mode) as handle:
    descriptor=None;yield handle
  except (OSError,ValueError):raise StorageError() from None
  finally:
   if descriptor is not None:os.close(descriptor)

 def _path(self,key,suffix):
  identifier(key);path=self.folder/(key+'.'+suffix)
  if self.folder.is_symlink() or path.is_symlink():raise StorageError()
  return path

 def _hash(self,key,suffix):
  h=hashlib.sha256();size=0
  with self._file(key+'.'+suffix) as handle:
   while chunk:=handle.read(CHUNK_BYTES):
    size+=len(chunk)
    if size>MAX_BYTES:raise ValidationError()
    h.update(chunk)
  return size,h.hexdigest()

 def _operation(self,c,key,kind=None,*,request=False):
  if request:validate_operation_key(key)
  else:identifier(key)
  row=c.execute('SELECT * FROM portability_ops WHERE '+('request_id' if request else 'id')+'=?',(key,)).fetchone()
  if row is None or (kind and row['kind']!=kind):raise NotFoundError()
  if row['expires_at']<=time.time():raise NotFoundError()
  return row

 def _metadata(self,row):
  return {'id':row['id'],'state':row['state'],'size':row['size'],'offset':row['offset'],
          'digest':row['digest'],'expires_at':row['expires_at'],**json.loads(row['metadata'])}

 def _cleanup(self):
  # Lazy and ownership based: no globbing/deletion of arbitrary library paths.
  with self.storage._transaction(write=True) as c:
   rows=c.execute('SELECT id,state,expires_at FROM portability_ops WHERE expires_at<=?',(time.time(),)).fetchall()
   for row in rows:
    for suffix in ('part','ready'):
     path=self._path(row['id'],suffix)
     if path.exists() and not path.is_symlink():path.unlink()
   claims=c.execute("""SELECT a.asset_id,a.digest,a.restore_id FROM portability_asset_claims a
    JOIN portability_restores r ON r.id=a.restore_id JOIN portability_previews p ON p.id=r.preview_id
    WHERE p.expires_at<=? AND NOT EXISTS(SELECT 1 FROM assets s WHERE s.id=a.asset_id)""",(time.time(),)).fetchall()
   folder=self.root/'assets'
   for claim in claims:
    identifier(claim['asset_id']);path=folder/(claim['asset_id']+'.blob')
    if path.exists() and not path.is_symlink():
     with self._file(claim['asset_id']+'.blob',folder=folder) as handle:
      if digest_bytes(handle.read(10*1024*1024+1))!=claim['digest']:continue
     path.unlink()
    c.execute('DELETE FROM portability_asset_claims WHERE asset_id=? AND restore_id=?',(claim['asset_id'],claim['restore_id']))
   # Retain immutable receipt identities. Expired reads fail even when metadata remains.

 def export_create(self,format='bundle',include_trash=False,request_id=None):
  from .content import snapshot
  from .archive import write_bundle,write_html
  from ..assets import AssetStore
  validate_operation_key(request_id)
  if format not in ('bundle','html') or type(include_trash) is not bool:raise ValidationError()
  self._cleanup();args=encoded({'format':format,'include_trash':include_trash})
  with self.storage._transaction(write=True) as c:
   prior=c.execute('SELECT id,args FROM portability_ops WHERE request_id=?',(request_id,)).fetchone()
   if prior:
    if prior['args']!=args:raise ConflictError()
    row=self._operation(c,request_id,'export',request=True);return self._metadata(row)
   key=uuid4().hex;expires=time.time()+TTL
   c.execute('INSERT INTO portability_ops(id,kind,request_id,args,state,pid,digest,expires_at) VALUES(?,?,?,?,?,?,?,?)',(key,'export',request_id,args,'pending',os.getpid(),'',expires))
  try:
   with self.storage._transaction() as c:
    data=snapshot(c);identity=c.execute("SELECT value FROM library_config WHERE key='library_id'").fetchone()[0]
   # Codec reserves the generated leaf with exclusive creation.
   target=self._path(key,'part')
   assets=AssetStore(self.root)
   try:details=write_bundle(target,data,lambda asset_id:assets.read_asset(asset_id)[0],identity) if format=='bundle' else write_html(target,data,include_trash)
   except ValueError:raise ValidationError() from None
   size,digest=self._hash(key,'part')
   with self._file(key+'.part','r+b') as handle:handle.flush();os.fsync(handle.fileno())
   os.replace(target,self._path(key,'ready'))
   metadata={'format':format,'format_version':1 if format=='bundle' else None,'filename':'hermes-bookmarks-backup.zip' if format=='bundle' else 'hermes-bookmarks.html',
    'mime_type':'application/zip' if format=='bundle' else 'text/html',**details}
   with self.storage._transaction(write=True) as c:
    c.execute("UPDATE portability_ops SET state='ready',size=?,digest=?,metadata=? WHERE id=?",(size,digest,encoded(metadata),key))
    return self._metadata(self._operation(c,key,'export'))
  except BaseException:
   with self.storage._transaction(write=True) as c:c.execute("UPDATE portability_ops SET state='failed' WHERE id=? AND state='pending'",(key,))
   raise

 def export_get(self,request_id):
  with self.storage._transaction(write=True) as c:
   row=self._operation(c,request_id,'export',request=True)
   if row['state']=='pending':
    try:os.kill(row['pid'],0)
    except ProcessLookupError:
     c.execute("UPDATE portability_ops SET state='failed' WHERE id=?",(row['id'],));row=self._operation(c,row['id'])
   return self._metadata(row)

 def export_read(self,artifact_id,offset=0):
  integer(offset)
  with self.storage._transaction() as c:
   row=self._operation(c,artifact_id,'export')
   if row['state']!='ready' or offset>row['size']:raise ConflictError()
   metadata=self._metadata(row)
   with self._file(row['id']+'.ready') as handle:
    if os.fstat(handle.fileno()).st_size!=row['size']:raise StorageError()
    handle.seek(offset);raw=handle.read(min(CHUNK_BYTES,row['size']-offset))
   return {'artifact_id':artifact_id,'offset':offset,'next_offset':offset+len(raw),'eof':offset+len(raw)==row['size'],
    'content_base64':base64.b64encode(raw).decode(),'size':row['size'],'digest':row['digest'],
    'filename':metadata['filename'],'mime_type':metadata['mime_type']}

 def upload_create(self,size,digest,request_id):
  integer(size);sha(digest);validate_operation_key(request_id)
  if size==0:raise ValidationError()
  self._cleanup();args=encoded({'size':size,'digest':digest})
  with self.storage._transaction(write=True) as c:
   prior=c.execute('SELECT args FROM portability_ops WHERE request_id=?',(request_id,)).fetchone()
   if prior:
    if prior['args']!=args:raise ConflictError()
    return self._metadata(self._operation(c,request_id,'upload',request=True))
   key=uuid4().hex
   with self._file(key+'.part','r+b',exclusive=True) as handle:handle.flush();os.fsync(handle.fileno())
   c.execute('INSERT INTO portability_ops(id,kind,request_id,args,state,pid,size,digest,expires_at) VALUES(?,?,?,?,?,?,?,?,?)',(key,'upload',request_id,args,'uploading',os.getpid(),size,digest,time.time()+TTL))
   return self._metadata(self._operation(c,key,'upload'))

 def upload_chunk(self,upload_id,offset,content_base64):
  integer(offset)
  if not isinstance(content_base64,str) or len(content_base64)>((CHUNK_BYTES+2)//3)*4:raise ValidationError()
  try:raw=base64.b64decode(content_base64,validate=True)
  except (ValueError,binascii.Error):raise ValidationError() from None
  if not raw or len(raw)>CHUNK_BYTES:raise ValidationError()
  with self.storage._transaction(write=True) as c:
   row=self._operation(c,upload_id,'upload')
   if offset+len(raw)>row['size'] or offset>row['offset']:raise ConflictError()
   with self._file(upload_id+'.part','r+b') as handle:
    if os.fstat(handle.fileno()).st_size<row['offset']:raise StorageError()
    if offset<row['offset']:
     if offset+len(raw)>row['offset']:raise ConflictError()
     handle.seek(offset)
     if handle.read(len(raw))!=raw:raise ConflictError()
     return self._metadata(row)
    if row['state']!='uploading':raise ConflictError()
    # Discard only uncommitted tail from our own prior interrupted append.
    handle.truncate(row['offset']);handle.seek(offset);handle.write(raw);handle.flush();os.fsync(handle.fileno())
   c.execute('UPDATE portability_ops SET offset=? WHERE id=?',(offset+len(raw),upload_id))
   return self._metadata(self._operation(c,upload_id))

 def _uploaded(self,c,upload_id):
  row=self._operation(c,upload_id,'upload')
  if row['offset']!=row['size']:raise ConflictError()
  size,digest=self._hash(upload_id,'part')
  if size!=row['size'] or digest!=row['digest']:raise ValidationError()
  return row

 def backup_preview(self,upload_id):
  from .archive import read_bundle
  from .content import empty
  with self.storage._transaction() as c:
   row=self._uploaded(c,upload_id)
   if not empty(c):raise ConflictError()
   source=self._path(upload_id,'part')
  try:data,assets,manifest=read_bundle(source)
  except ValueError:raise ValidationError() from None
  counts={key:len(value) for key,value in data.items() if isinstance(value,list)}
  with self.storage._transaction(write=True) as c:
   row=self._uploaded(c,upload_id)
   if not empty(c):raise ConflictError()
   prior=c.execute('SELECT report FROM portability_previews WHERE upload_id=?',(upload_id,)).fetchone()
   if prior:return json.loads(prior['report'])
   key=uuid4().hex;report={'preview_id':key,'input_digest':row['digest'],'counts':counts,'empty_target':True,'format_version':1,
    'limitations':['Restore preserves this target library identity.','No chat sessions, credentials or queued execution are restored.','Saved routing intent is inert until explicitly configured.']}
   c.execute('INSERT INTO portability_previews VALUES(?,?,?,?,?)',(key,upload_id,row['digest'],row['expires_at'],encoded(report)))
   c.execute("UPDATE portability_ops SET state='sealed' WHERE id=?",(upload_id,))
   return report

 def backup_restore_get(self,request_id):
  validate_operation_key(request_id)
  with self.storage._transaction() as c:
   row=c.execute('SELECT * FROM portability_restores WHERE request_id=?',(request_id,)).fetchone()
   if row is None:raise NotFoundError()
   return json.loads(row['result']) if row['state']=='succeeded' else {'id':row['id'],'state':row['state'],'counts':{}}

 def backup_restore(self,preview_id,input_digest,request_id):
  identifier(preview_id);sha(input_digest);validate_operation_key(request_id)
  try:return self._restore(preview_id,input_digest,request_id)
  except BaseException:
   with self.storage._transaction(write=True) as c:
    c.execute("UPDATE portability_restores SET state='failed' WHERE request_id=? AND preview_id=? AND digest=? AND state!='succeeded'",(request_id,preview_id,input_digest))
   raise

 def _restore(self,preview_id,input_digest,request_id):
  from .archive import read_bundle
  from .content import empty,restore_content
  identifier(preview_id);sha(input_digest);validate_operation_key(request_id)
  # Persist admission before executor/file work; receipts contain no user content.
  with self.storage._transaction(write=True) as c:
   prior=c.execute('SELECT * FROM portability_restores WHERE request_id=?',(request_id,)).fetchone()
   if prior:
    if prior['preview_id']!=preview_id or prior['digest']!=input_digest:raise ConflictError()
    if prior['state']=='succeeded':return json.loads(prior['result'])
    restore_id=prior['id']
   else:
    restore_id=uuid4().hex
    c.execute('INSERT INTO portability_restores(id,request_id,preview_id,digest,state) VALUES(?,?,?,?,?)',(restore_id,request_id,preview_id,input_digest,'admitted'))
   preview=c.execute('SELECT * FROM portability_previews WHERE id=?',(preview_id,)).fetchone()
   if preview is None or preview['expires_at']<=time.time():raise NotFoundError()
   if preview['digest']!=input_digest:raise ConflictError()
   upload=self._uploaded(c,preview['upload_id'])
   if not empty(c):raise ConflictError()
   source=self._path(upload['id'],'part')
  try:data,assets,manifest=read_bundle(source)
  except ValueError:raise ValidationError() from None
  asset_folder=self.root/'assets'
  if asset_folder.is_symlink():raise StorageError()
  asset_folder.mkdir(mode=0o700,exist_ok=True)
  # Persist generated-file claims before content commit so crash retry can
  # recognize only its own orphaned files. Never overwrite an unclaimed leaf.
  with self.storage._transaction(write=True) as c:
   if not empty(c):raise ConflictError()
   for key,raw in assets.items():
    identifier(key);h=digest_bytes(raw)
    claim=c.execute('SELECT * FROM portability_asset_claims WHERE asset_id=?',(key,)).fetchone()
    if claim and (claim['restore_id']!=restore_id or claim['digest']!=h):raise ConflictError()
    if not claim:
     if (asset_folder/(key+'.blob')).exists() or (asset_folder/(key+'.blob')).is_symlink():raise ConflictError()
     c.execute('INSERT INTO portability_asset_claims VALUES(?,?,?)',(key,restore_id,h))
  with self.storage._transaction(write=True) as c:
   prior=c.execute('SELECT * FROM portability_restores WHERE request_id=?',(request_id,)).fetchone()
   if prior['state']=='succeeded':return json.loads(prior['result'])
   self._uploaded(c,upload['id'])
   if not empty(c):raise ConflictError()
   for key,raw in assets.items():
    target=asset_folder/(key+'.blob')
    if target.exists() or target.is_symlink():
     with self._file(key+'.blob',folder=asset_folder) as handle:
      if digest_bytes(handle.read(10*1024*1024+1))!=digest_bytes(raw):raise StorageError()
    else:
     with self._file(key+'.blob','r+b',folder=asset_folder,exclusive=True) as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
   restore_content(c,data)
   report={'id':restore_id,'state':'succeeded','counts':{key:len(value) for key,value in data.items() if isinstance(value,list)}}
   c.execute("UPDATE portability_restores SET state='succeeded',result=? WHERE id=?",(encoded(report),restore_id))
   return report
