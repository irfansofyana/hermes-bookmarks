import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from bookmarks.service import BookmarkService
from bookmarks.errors import BookmarkError
from bookmarks.portability.store import PortabilityStore

class PortabilityStoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.source=BookmarkService(self.root/'source');self.store=PortabilityStore(self.source._storage)
 def export(self,format='bundle'):
  return self.store.export_create(format=format,request_id=str(uuid4()))
 def transfer(self,artifact,target):
  upload=target.upload_create(size=artifact['size'],digest=artifact['digest'],request_id=str(uuid4()));offset=0;parts=[]
  while offset<artifact['size']:
   chunk=self.store.export_read(artifact['id'],offset);raw=base64.b64decode(chunk['content_base64']);self.assertLessEqual(len(raw),32768);parts.append(raw)
   upload=target.upload_chunk(upload['id'],offset,chunk['content_base64']);offset=chunk['next_offset']
  self.assertEqual(hashlib.sha256(b''.join(parts)).hexdigest(),artifact['digest']);return upload
 def test_export_request_and_chunks_are_durable_idempotent_bounded(self):
  self.source.capture(url='https://example.org',notes='Synthetic notes '+('a'*60000))
  request=str(uuid4());a=self.store.export_create(format='bundle',request_id=request);self.assertEqual(a['state'],'ready');self.assertEqual(a,self.store.export_create(format='bundle',request_id=request))
  self.assertEqual(a,PortabilityStore(self.source._storage).export_get(request));self.assertNotIn(str(self.root),str(a))
  with self.assertRaises(BookmarkError):self.store.export_create(format='html',request_id=request)
  with self.assertRaises(BookmarkError):self.store.export_read('../bad',0)
  with self.assertRaises(BookmarkError):self.store.export_read(a['id'],-1)
  chunk=self.store.export_read(a['id'],a['size']);self.assertTrue(chunk['eof']);self.assertEqual(chunk['content_base64'],'')
 def test_empty_target_restore_is_atomic_and_receipt_retry_keeps_identity(self):
  row=self.source.capture(url='https://example.org',notes='Synthetic personal note')['item'];self.source.collection_create('Empty nested collection')
  target=BookmarkService(self.root/'target');identity=target.identity();ts=PortabilityStore(target._storage);a=self.export();upload=self.transfer(a,ts)
  preview=ts.backup_preview(upload['id']);self.assertEqual(target.counts()['all'],0)
  rid=str(uuid4());result=ts.backup_restore(preview['preview_id'],preview['input_digest'],rid)
  self.assertEqual(result['state'],'succeeded');self.assertEqual(ts.backup_restore(preview['preview_id'],preview['input_digest'],rid),result)
  self.assertEqual(PortabilityStore(target._storage).backup_restore_get(rid),result);self.assertEqual(target.identity(),identity)
  self.assertEqual(target.get(row['id'])['notes'],row['notes']);self.assertEqual(target.counts()['all'],1)
  with target._storage._transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
 def test_concurrent_target_writer_after_preview_prevents_all_restore_effects(self):
  self.source.capture(url='https://example.org/source');a=self.export();target=BookmarkService(self.root/'target');ts=PortabilityStore(target._storage);upload=self.transfer(a,ts);p=ts.backup_preview(upload['id'])
  keep=target.capture(url='https://example.org/concurrent')['item']
  with self.assertRaises(BookmarkError):ts.backup_restore(p['preview_id'],p['input_digest'],str(uuid4()))
  self.assertEqual(target.counts()['all'],1);self.assertEqual(target.get(keep['id'])['url'],keep['url'])
 def test_chunks_reject_gaps_and_changed_replays_and_preview_rejects_tamper(self):
  data=b'Synthetic invalid archive';digest=hashlib.sha256(data).hexdigest();rid=str(uuid4());u=self.store.upload_create(len(data),digest,rid)
  self.assertEqual(u,self.store.upload_create(len(data),digest,rid))
  encoded=base64.b64encode(data).decode();u=self.store.upload_chunk(u['id'],0,encoded);self.assertEqual(self.store.upload_chunk(u['id'],0,encoded),u)
  for off,content in [(1,encoded),(len(data)+1,encoded),(0,base64.b64encode(b'changed').decode())]:
   with self.assertRaises(BookmarkError):self.store.upload_chunk(u['id'],off,content)
  with self.assertRaises(BookmarkError):self.store.backup_preview(u['id'])
 def test_preview_rejects_nonempty_target_without_deleting_anything(self):
  a=self.export();target=BookmarkService(self.root/'target');target.collection_create('Keep me');ts=PortabilityStore(target._storage);u=self.transfer(a,ts)
  with self.assertRaises(BookmarkError):ts.backup_preview(u['id'])
  self.assertEqual(target.collection_list()['total'],1)
 def test_html_is_labeled_lossy_and_never_contains_private_notes(self):
  self.source.capture(url='https://example.org',notes='SYNTHETIC_PRIVATE_NOTE',title='Synthetic')
  a=self.export('html');self.assertTrue(a['limitations']);raw=base64.b64decode(self.store.export_read(a['id'],0)['content_base64']);self.assertNotIn(b'SYNTHETIC_PRIVATE_NOTE',raw);self.assertIn(b'example.org',raw)
 def test_failed_content_commit_rolls_back_and_same_request_recovers_owned_asset(self):
  from unittest.mock import patch
  from bookmarks.assets import AssetStore
  asset=AssetStore(self.source._storage.database_path.parent).store_image((Path(__file__).parent/'fixtures/tiny.png').read_bytes(),'image/png')
  row=self.source.capture(kind='image',primary_asset_id=asset['id'],operation_key=str(uuid4()),notes='Synthetic image notes')['item']
  target=BookmarkService(self.root/'target');ts=PortabilityStore(target._storage);u=self.transfer(self.export(),ts);p=ts.backup_preview(u['id']);rid=str(uuid4())
  with patch('bookmarks.portability.content.restore_content',side_effect=RuntimeError('synthetic commit failure')):
   with self.assertRaises(RuntimeError):ts.backup_restore(p['preview_id'],p['input_digest'],rid)
  self.assertEqual(target.counts()['all'],0);self.assertEqual(ts.backup_restore_get(rid)['state'],'failed')
  result=ts.backup_restore(p['preview_id'],p['input_digest'],rid);self.assertEqual(result['state'],'succeeded')
  self.assertEqual(target.get(row['id'])['notes'],'Synthetic image notes');self.assertEqual(AssetStore(target._storage.database_path.parent).read_asset(asset['id'])[0],AssetStore(self.source._storage.database_path.parent).read_asset(asset['id'])[0])
 def test_preexisting_unclaimed_asset_file_never_overwritten(self):
  from bookmarks.assets import AssetStore
  asset=AssetStore(self.source._storage.database_path.parent).store_image((Path(__file__).parent/'fixtures/tiny.png').read_bytes(),'image/png')
  target=BookmarkService(self.root/'target');ts=PortabilityStore(target._storage);u=self.transfer(self.export(),ts);p=ts.backup_preview(u['id']);folder=target._storage.database_path.parent/'assets';folder.mkdir(exist_ok=True);path=folder/(asset['id']+'.blob');path.write_bytes(b'Keep this unrelated orphan')
  with self.assertRaises(BookmarkError):ts.backup_restore(p['preview_id'],p['input_digest'],str(uuid4()))
  self.assertEqual(path.read_bytes(),b'Keep this unrelated orphan');self.assertEqual(target.counts()['all'],0)
 def test_expired_failed_restore_claim_cleanup_removes_only_owned_unregistered_files(self):
  from unittest.mock import patch
  from bookmarks.assets import AssetStore
  asset=AssetStore(self.source._storage.database_path.parent).store_image((Path(__file__).parent/'fixtures/tiny.png').read_bytes(),'image/png')
  target=BookmarkService(self.root/'target');ts=PortabilityStore(target._storage);u=self.transfer(self.export(),ts);p=ts.backup_preview(u['id'])
  with patch('bookmarks.portability.content.restore_content',side_effect=RuntimeError('synthetic failure')):
   with self.assertRaises(RuntimeError):ts.backup_restore(p['preview_id'],p['input_digest'],str(uuid4()))
  claimed=self.root/'target/assets'/(asset['id']+'.blob');unrelated=self.root/'target/assets'/('f'*32+'.blob');unrelated.write_bytes(b'Keep unrelated')
  self.assertTrue(claimed.exists())
  with patch('bookmarks.portability.store.time.time',return_value=u['expires_at']+1):ts.upload_create(1,'a'*64,str(uuid4()))
  self.assertFalse(claimed.exists());self.assertEqual(unrelated.read_bytes(),b'Keep unrelated')
 def test_expired_export_and_upload_are_not_readable(self):
  from unittest.mock import patch
  a=self.export();u=self.store.upload_create(1,hashlib.sha256(b'x').hexdigest(),str(uuid4()))
  with patch('bookmarks.portability.store.time.time',return_value=a['expires_at']+1):
   with self.assertRaises(BookmarkError):self.store.export_read(a['id'],0)
   with self.assertRaises(BookmarkError):self.store.upload_chunk(u['id'],0,'eA==')
if __name__=='__main__':unittest.main()
