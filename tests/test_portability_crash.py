import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4
from bookmarks.service import BookmarkService
from bookmarks.portability.store import PortabilityStore
from bookmarks.assets import AssetStore

class PortabilityCrashTests(unittest.TestCase):
 def interrupted(self,root,phase):
  source=BookmarkService(root/'source');asset=AssetStore(root/'source').store_image((Path(__file__).parent/'fixtures/tiny.png').read_bytes(),'image/png');item=source.capture(kind='image',primary_asset_id=asset['id'],operation_key=str(uuid4()),notes='Synthetic crash-recovery note')['item']
  ss=PortabilityStore(source._storage);a=ss.export_create(request_id=str(uuid4()));ts=PortabilityStore(BookmarkService(root/'target')._storage);u=ts.upload_create(a['size'],a['digest'],str(uuid4()));offset=0
  while offset<a['size']:
   chunk=ss.export_read(a['id'],offset);ts.upload_chunk(u['id'],offset,chunk['content_base64']);offset=chunk['next_offset']
  p=ts.backup_preview(u['id']);rid=str(uuid4())
  script='''import os,sys
from pathlib import Path
from contextlib import contextmanager
from bookmarks.service import BookmarkService
from bookmarks.portability.store import PortabilityStore
original=PortabilityStore._file
@contextmanager
def interrupted(self,name,mode='rb',folder=None,exclusive=False):
 with original(self,name,mode,folder,exclusive) as f:
  if folder is not None and folder.name=='assets' and exclusive and sys.argv[5]=='write':
   class Writer:
    def __getattr__(self,name):return getattr(f,name)
    def write(self,raw):
     f.write(raw[:8]);f.flush();os.fsync(f.fileno());os._exit(23)
   yield Writer()
  else:yield f
PortabilityStore._file=interrupted
if sys.argv[5]=='link':
 link=os.link
 def crash_link(*args,**kwargs):
  link(*args,**kwargs);os._exit(24)
 os.link=crash_link
PortabilityStore(BookmarkService(Path(sys.argv[1]))._storage).backup_restore(*sys.argv[2:5])
'''
  result=subprocess.run([sys.executable,'-B','-c',script,str(root/'target'),p['preview_id'],p['input_digest'],rid,phase],cwd=Path(__file__).parents[1],timeout=20)
  self.assertEqual(result.returncode,23 if phase=='write' else 24);self.assertEqual(BookmarkService(root/'target').counts()['all'],0)
  return source,asset,item,ss,a,ts,u,p,rid
 def test_mid_asset_write_process_death_retries_same_request_without_partial_final(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);source,asset,item,ss,a,ts,u,p,rid=self.interrupted(root,'write')
   folder=root/'target/assets';self.assertFalse((folder/(asset['id']+'.blob')).exists());self.assertEqual([x.stat().st_size for x in folder.glob('*.asset-part')],[8])
   from bookmarks.errors import ConflictError
   with self.assertRaises(ConflictError):ts.backup_restore(p['preview_id'],p['input_digest'],str(uuid4()))
   self.assertEqual([x.stat().st_size for x in folder.glob('*.asset-part')],[8])
   self.assertEqual(ts.backup_restore(p['preview_id'],p['input_digest'],rid)['state'],'succeeded')
   self.assertEqual(AssetStore(root/'target').read_asset(asset['id'])[0],AssetStore(root/'source').read_asset(asset['id'])[0])
   self.assertEqual(BookmarkService(root/'target').get(item['id'])['notes'],item['notes']);self.assertEqual(list((root/'target/assets').glob('*.asset-part')),[])
 def test_mid_write_expiry_cleanup_releases_only_owned_partial_and_allows_new_restore(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);source,asset,item,ss,a,ts,u,p,rid=self.interrupted(root,'write');folder=root/'target/assets';unrelated=folder/('f'*32+'.asset-part');unrelated.write_bytes(b'Unrelated file')
   with patch('bookmarks.portability.store.time.time',return_value=u['expires_at']+1):ts.upload_create(1,'a'*64,str(uuid4()))
   with ts.storage._transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM portability_asset_claims').fetchone()[0],0)
   self.assertEqual(unrelated.read_bytes(),b'Unrelated file');self.assertFalse((folder/(asset['id']+'.blob')).exists());self.assertEqual(list(folder.glob('*.asset-part')),[unrelated])
   # A new upload/preview/request must now restore the same backup.
   fresh=ts.upload_create(a['size'],a['digest'],str(uuid4()));offset=0
   while offset<a['size']:
    chunk=ss.export_read(a['id'],offset);ts.upload_chunk(fresh['id'],offset,chunk['content_base64']);offset=chunk['next_offset']
   preview=ts.backup_preview(fresh['id']);self.assertEqual(ts.backup_restore(preview['preview_id'],preview['input_digest'],str(uuid4()))['state'],'succeeded')
 def test_crash_between_atomic_publication_and_temp_unlink_recovers_same_request(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);source,asset,item,ss,a,ts,u,p,rid=self.interrupted(root,'link')
   self.assertEqual(ts.backup_restore(p['preview_id'],p['input_digest'],rid)['state'],'succeeded')
   self.assertEqual(AssetStore(root/'target').read_asset(asset['id'])[0],AssetStore(root/'source').read_asset(asset['id'])[0]);self.assertEqual(list((root/'target/assets').glob('*.asset-part')),[])
 def test_claimed_temporary_symlink_never_truncates_or_deletes_unrelated_bytes(self):
  from unittest.mock import patch
  from bookmarks.errors import StorageError
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);source,asset,item,ss,a,ts,u,p,rid=self.interrupted(root,'write');stage=next((root/'target/assets').glob('*.asset-part'));stage.unlink();unrelated=root/'unrelated';unrelated.write_bytes(b'Keep this data');stage.symlink_to(unrelated)
   with self.assertRaises(StorageError):ts.backup_restore(p['preview_id'],p['input_digest'],rid)
   self.assertEqual(unrelated.read_bytes(),b'Keep this data');self.assertTrue(stage.is_symlink());self.assertEqual(BookmarkService(root/'target').counts()['all'],0)
   with patch('bookmarks.portability.store.time.time',return_value=u['expires_at']+1):
    with self.assertRaises(StorageError):ts.upload_create(1,'a'*64,str(uuid4()))
   self.assertEqual(unrelated.read_bytes(),b'Keep this data');self.assertTrue(stage.is_symlink())
 def test_expired_crash_after_link_cleans_known_temporary_and_final_without_orphans(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);source,asset,item,ss,a,ts,u,p,rid=self.interrupted(root,'link')
   with patch('bookmarks.portability.store.time.time',return_value=u['expires_at']+1):ts.upload_create(1,'a'*64,str(uuid4()))
   self.assertEqual(list((root/'target/assets').iterdir()),[])
   with ts.storage._transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM portability_asset_claims').fetchone()[0],0)
 def test_process_death_after_owned_asset_publication_resumes_same_request(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);source=BookmarkService(root/'source');asset=AssetStore(root/'source').store_image((Path(__file__).parent/'fixtures/tiny.png').read_bytes(),'image/png');item=source.capture(kind='image',primary_asset_id=asset['id'],operation_key=str(uuid4()),notes='Synthetic durable image note')['item']
   ss=PortabilityStore(source._storage);a=ss.export_create(request_id=str(uuid4()));ts=PortabilityStore(BookmarkService(root/'target')._storage);u=ts.upload_create(a['size'],a['digest'],str(uuid4()));offset=0
   while offset<a['size']:
    chunk=ss.export_read(a['id'],offset);ts.upload_chunk(u['id'],offset,chunk['content_base64']);offset=chunk['next_offset']
   p=ts.backup_preview(u['id']);rid=str(uuid4())
   script='''import os,sys
from pathlib import Path
from bookmarks.service import BookmarkService
from bookmarks.portability.store import PortabilityStore
import bookmarks.portability.content as content
content.restore_content=lambda *args:os._exit(19)
PortabilityStore(BookmarkService(Path(sys.argv[1]))._storage).backup_restore(*sys.argv[2:])
'''
   result=subprocess.run([sys.executable,'-B','-c',script,str(root/'target'),p['preview_id'],p['input_digest'],rid],cwd=Path(__file__).parents[1],timeout=20)
   self.assertEqual(result.returncode,19);self.assertEqual(BookmarkService(root/'target').counts()['all'],0)
   self.assertTrue((root/'target/assets'/(asset['id']+'.blob')).exists())
   recovered=PortabilityStore(BookmarkService(root/'target')._storage);result=recovered.backup_restore(p['preview_id'],p['input_digest'],rid);self.assertEqual(result['state'],'succeeded');self.assertEqual(BookmarkService(root/'target').get(item['id'])['notes'],'Synthetic durable image note')
   self.assertEqual(recovered.backup_restore_get(rid),result)
