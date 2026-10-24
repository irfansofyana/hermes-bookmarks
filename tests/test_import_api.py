import unittest
from uuid import uuid4
import test_tools as fixtures
PREFIX='/api/plugins/hermes-bookmarks'
class ImportAPITests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ToolTests.asyncSetUp
 call=fixtures.ToolTests.call
 async def test_normalized_preview_start_lookup_cancel_native_http_parity(self):
  p=await self.call('bookmark_import_preview',{'records':[{'url':'https://example.org/import','notes':'Keep','unknown':'warn'}]})
  self.assertTrue(p['ok'],p)
  preview=p['result'];rid=str(uuid4());params={'preview_id':preview['preview_id'],'input_digest':preview['input_digest'],'request_id':rid}
  native=await self.call('bookmark_import_start',params);self.assertTrue(native['ok'],native)
  result=await self.client.post(PREFIX+'/imports/start',json=params)
  self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['result']['id'],native['result']['id'])
  lookup=await self.client.get(PREFIX+'/imports/requests/'+rid);self.assertEqual(lookup.status_code,200)
  self.assertEqual(lookup.json(),await self.call('bookmark_import_request_get',{'request_id':rid}))
  jid=native['result']['id'];cancel=await self.call('bookmark_job_cancel',{'job_id':jid})
  self.assertEqual(cancel['result']['state'],'cancelled')
  self.assertEqual((await self.client.get(PREFIX+'/imports/'+jid)).json(),await self.call('bookmark_job_get',{'job_id':jid}))
 async def test_html_bad_json_size_stale_digest_and_scope_rejection(self):
  html='<DL><DT><A HREF="https://example.org/a">A</A></DL>'
  p=await self.client.post(PREFIX+'/imports/preview',json={'html':html});self.assertEqual(p.status_code,200,p.text)
  params={'preview_id':p.json()['result']['preview_id'],'input_digest':'0'*64,'request_id':str(uuid4())}
  self.assertEqual((await self.client.post(PREFIX+'/imports/start',json=params)).status_code,409)
  for content in ['{"html":"x","html":"y"}','{"options":{"enrich":NaN},"html":"x"}']:
   self.assertEqual((await self.client.post(PREFIX+'/imports/preview',content=content)).status_code,400)
  self.assertEqual((await self.client.post(PREFIX+'/imports/preview',content=b' '*(2*1024*1024+128*1024+1))).status_code,413)
  self.assertEqual((await self.client.get(PREFIX+'/imports/missing?profile=other')).status_code,400)
  self.assertFalse((await self.call('bookmark_import_preview',{'records':[{'url':'https://example.org'}],'library_root':'private'}))['ok'])
 async def test_trash_http_native_parity_and_no_identity_override(self):
  item=(await self.call('bookmark_save',{'url':'https://example.org/trash'}))['result']
  response=await self.client.post(PREFIX+'/items/'+item['id']+'/trash',json={'expected_revision':item['revision']})
  self.assertEqual(response.status_code,200);trashed=response.json()['result']
  restored=await self.call('bookmark_restore',{'item_id':item['id'],'expected_revision':trashed['revision']})
  self.assertIsNone(restored['result']['deleted_at'])
  response=await self.client.post(PREFIX+'/items/'+item['id']+'/trash',json={'expected_revision':restored['result']['revision'],'item_id':'other'})
  self.assertEqual(response.status_code,400)
