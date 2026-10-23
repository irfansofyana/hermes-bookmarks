import base64
import hashlib
import unittest
from uuid import uuid4
from unittest.mock import patch
import test_tools as fixtures
PREFIX='/api/plugins/hermes-bookmarks'

class PortabilityAPITests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ToolTests.asyncSetUp
 call=fixtures.ToolTests.call
 async def test_export_native_http_parity_and_no_inference_activation(self):
  params={'format':'bundle','request_id':str(uuid4())}
  with patch('runtime.ensure_enrichment') as worker,patch('native_tools.ensure_enrichment') as native_worker:
   native=await self.call('bookmark_export_create',params);self.assertTrue(native['ok'],native);self.assertEqual(native['result'].get('format_version'),1)
   result=await self.client.post(PREFIX+'/exports',json=params);self.assertEqual(result.json(),native)
   status=await self.client.get(PREFIX+'/exports/requests/'+params['request_id']);self.assertEqual(status.json(),native)
   read=await self.client.get(PREFIX+'/exports/'+native['result']['id']+'?offset=0');self.assertEqual(read.json(),await self.call('bookmark_export_read',{'artifact_id':native['result']['id'],'offset':0}))
   self.assertLessEqual(len(base64.b64decode(read.json()['result']['content_base64'])),32768);worker.assert_not_called();native_worker.assert_not_called()
 async def test_failed_http_restore_is_read_back_and_recovers_exact_request(self):
  from bookmarks.errors import StorageError
  exported=(await self.call('bookmark_export_create',{'request_id':str(uuid4())}))['result']
  raw=base64.b64decode((await self.call('bookmark_export_read',{'artifact_id':exported['id']}))['result']['content_base64'])
  u=(await self.client.post(PREFIX+'/backups/uploads',json={'size':len(raw),'digest':hashlib.sha256(raw).hexdigest(),'request_id':str(uuid4())})).json()['result']
  await self.client.post(PREFIX+'/backups/uploads/'+u['id']+'/chunks',json={'offset':0,'content_base64':base64.b64encode(raw).decode()})
  preview=(await self.client.post(PREFIX+'/backups/preview',json={'upload_id':u['id']})).json()['result']
  params={'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':str(uuid4())}
  with patch('bookmarks.portability.content.restore_content',side_effect=StorageError()):
   self.assertEqual((await self.client.post(PREFIX+'/backups/restore',json=params)).status_code,503)
  failed=(await self.client.get(PREFIX+'/backups/requests/'+params['request_id'])).json()['result'];self.assertEqual(failed['state'],'failed')
  recovered=(await self.client.post(PREFIX+'/backups/restore',json=params)).json()['result'];self.assertEqual(recovered['state'],'succeeded');self.assertEqual(recovered['id'],failed['id'])
  self.assertEqual((await self.client.get(PREFIX+'/backups/requests/'+params['request_id'])).json()['result'],recovered)
 async def test_upload_strict_types_offsets_and_restore_empty_bundle(self):
  exported=(await self.call('bookmark_export_create',{'format':'bundle','request_id':str(uuid4())}))['result'];raw=base64.b64decode((await self.call('bookmark_export_read',{'artifact_id':exported['id']}))['result']['content_base64'])
  params={'size':len(raw),'digest':hashlib.sha256(raw).hexdigest(),'request_id':str(uuid4())}
  response=await self.client.post(PREFIX+'/backups/uploads',json=params);self.assertEqual(response.status_code,200,response.text);upload=response.json()['result']
  body={'offset':0,'content_base64':base64.b64encode(raw).decode()};response=await self.client.post(PREFIX+'/backups/uploads/'+upload['id']+'/chunks',json=body);self.assertEqual(response.status_code,200,response.text)
  p=await self.client.post(PREFIX+'/backups/preview',json={'upload_id':upload['id']});self.assertEqual(p.status_code,200,p.text);preview=p.json()['result']
  rid=str(uuid4());params={'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':rid};restored=await self.call('bookmark_backup_restore',params);self.assertTrue(restored['ok'],restored)
  self.assertEqual((await self.client.get(PREFIX+'/backups/requests/'+rid)).json(),restored)
  for endpoint,content in [('/exports','{"format":"html","format":"bundle"}'),('/backups/uploads','{"size":NaN}')]:
   self.assertEqual((await self.client.post(PREFIX+endpoint,content=content)).status_code,400)
  for endpoint in ['/exports/'+exported['id']+'?offset=-1','/exports/'+exported['id']+'?offset=0&offset=1','/backups/requests/'+rid+'?profile=other']:
   self.assertEqual((await self.client.get(PREFIX+endpoint)).status_code,400)
  self.assertFalse((await self.call('bookmark_backup_upload_create',{'size':True,'digest':'a'*64,'request_id':str(uuid4())}))['ok'])
