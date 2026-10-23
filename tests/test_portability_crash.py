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
