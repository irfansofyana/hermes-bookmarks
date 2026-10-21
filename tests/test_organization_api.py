"""Native/real-ASGI organization parity; not a host-auth middleware test."""
import base64
import json
import unittest
from uuid import uuid4
import test_tools as fixtures
from library_fixtures import PNG

PREFIX='/api/plugins/hermes-bookmarks'


class OrganizationAPITests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ToolTests.asyncSetUp
    call = fixtures.ToolTests.call

    async def test_conflict_is_409_and_notes_are_shared(self):
        item=(await self.call('bookmark_save',{'url':'https://example.org/shared'}))['result']
        body={'expected_revision':item['revision'],'changes':{'notes':'A saved note','favorite':True}}
        updated=await self.client.post(PREFIX+'/items/'+item['id']+'/update',json=body)
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual((await self.call('bookmark_get',{'item_id':item['id']}))['result']['notes'],'A saved note')
        stale=await self.client.post(PREFIX+'/items/'+item['id']+'/update',json=body)
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json()['error']['code'],'conflict')
        self.assertEqual(stale.json()['error']['current_revision'],2)
        self.assertNotIn('A saved note',stale.text)
        appended=await self.client.post(PREFIX+'/items/'+item['id']+'/notes',json={'expected_revision':2,'text':'\nAppended','mode':'append'})
        self.assertEqual(appended.json()['result']['notes'],'A saved note\nAppended')

    async def test_collections_native_http_deletion_policy_and_paths(self):
        parent=(await self.call('bookmark_collection_create',{'name':'Parent'}))['result']
        child=(await self.client.post(PREFIX+'/collections',json={'name':'Child','parent_id':parent['id']})).json()['result']
        item=(await self.call('bookmark_save',{'url':'https://example.org/organized','collection_id':child['id']}))['result']
        renamed=await self.client.post(PREFIX+'/collections/'+child['id']+'/update',json={'expected_revision':1,'changes':{'name':'Renamed'}})
        self.assertEqual(renamed.status_code,200)
        found=(await self.call('bookmark_collection_list',{'query':'renamed'}))['result']
        self.assertEqual([part['name'] for part in found['collections'][0]['path']],['Parent','Renamed'])
        result=await self.client.post(PREFIX+'/collections/'+child['id']+'/delete',json={'expected_revision':2,'contents_policy':'move_to_parent'})
        self.assertEqual(result.json()['result'],{'deleted_id':child['id']})
        self.assertEqual((await self.call('bookmark_get',{'item_id':item['id']}))['result']['collection_id'],parent['id'])
        deleted=await self.call('bookmark_collection_delete',{'collection_id':parent['id'],'expected_revision':1,'contents_policy':'move_to_inbox'})
        self.assertTrue(deleted['ok'])
        self.assertIsNone((await self.client.get(PREFIX+'/items/'+item['id'])).json()['result']['collection_id'])

    async def test_image_receipt_save_shape_status_and_owned_associations(self):
        asset=(await self.call('bookmark_attachment_add',{'content_base64':base64.b64encode(PNG).decode(),'mime_type':'image/png'}))['result']
        key=str(uuid4()); params={'kind':'image','primary_asset_id':asset['id'],'title':'Image','notes':'Saved','operation_key':key}
        native=await self.call('bookmark_save',params)
        self.assertTrue(native['ok'],native)
        self.assertEqual(set(native),{'ok','result','receipt'})
        self.assertEqual(native['result']['url'],None)
        retry=await self.client.post(PREFIX+'/items',json=params)
        self.assertEqual(retry.json(),native)
        status=await self.client.get(PREFIX+'/captures/'+key)
        self.assertEqual(status.json()['result'],{'item':native['result'],'receipt':native['receipt']})
        self.assertEqual((await self.call('bookmark_capture_status',{'operation_key':key})),status.json())
        missing=await self.client.get(PREFIX+'/captures/'+str(uuid4()))
        self.assertEqual(missing.status_code,404)
        invalid=await self.client.post(PREFIX+'/items',json={**params,'operation_key':str(uuid4()),'primary_asset_id':'b'*32})
        self.assertEqual(invalid.status_code,404)

    async def test_repeated_tag_and_predicates_counts_and_profile_free_identity(self):
        first=await self.call('bookmark_save',{'url':'https://example.org/both','tags':['AI','Reading'],'favorite':True})
        await self.call('bookmark_save',{'url':'https://example.org/one','tags':['AI']})
        response=await self.client.get(PREFIX+'/items',params=[('tag','ai'),('tag','READING'),('view','favorites')])
        self.assertEqual(response.json()['result']['items'],[first['result']])
        self.assertEqual((await self.call('bookmark_search',{'tags':['AI','Reading'],'view':'favorites'})),response.json())
        counts=await self.client.get(PREFIX+'/counts')
        self.assertEqual(counts.json()['result'],{'all':2,'inbox':2,'favorites':1,'read_later':0})
        self.assertEqual(await self.call('bookmark_counts',{}),counts.json())
        tags=await self.client.get(PREFIX+'/tags?query=read')
        self.assertEqual(tags.json()['result']['tags'],[{'name':'Reading','count':1}])
        identity=(await self.client.get(PREFIX+'/library/identity')).json()
        self.assertEqual(set(identity['result']),{'library_id'})
        self.assertEqual(await self.call('bookmark_library_identity',{}),identity)

    async def test_unknown_nested_fields_bad_boolean_and_secret_scope_arguments_rejected(self):
        item=(await self.call('bookmark_save',{'url':'https://example.org/strict'}))['result']
        for changes in ({'favorite':1},{'notes':{'text':'bad'}},{'add_tags':[{'name':'bad'}]},
                        {'unknown':'bad'},{'attachment_ids':['../bad']},{'collection_id':False}):
            params={'item_id':item['id'],'expected_revision':1,'changes':changes}
            native=await self.call('bookmark_update',params)
            response=await self.client.post(PREFIX+'/items/'+item['id']+'/update',json={k:v for k,v in params.items() if k!='item_id'})
            self.assertFalse(native['ok']); self.assertEqual(response.status_code,400)
            self.assertEqual(native,response.json())
        for field in ('profile','library_root','api_key','credentials'):
            params={'name':'Bad',field:'never-accepted'}
            response=await self.client.post(PREFIX+'/collections',json=params)
            self.assertEqual(response.status_code,400)
            self.assertEqual(await self.call('bookmark_collection_create',params),response.json())
        nested=await self.call('bookmark_collection_update',{'collection_id':'missing','expected_revision':1,'changes':{'name':'x','profile':'other'}})
        self.assertEqual(nested['error']['code'],'invalid_argument')

    async def test_route_identities_cannot_be_overridden_and_scalar_repeats_reject(self):
        item=(await self.call('bookmark_save',{'url':'https://example.org/route'}))['result']
        for suffix in ('update','notes'):
            body={'item_id':'other','expected_revision':1,**({'changes':{'notes':'Lost'}} if suffix=='update' else {'text':'Lost'})}
            response=await self.client.post(PREFIX+'/items/'+item['id']+'/'+suffix,json=body)
            self.assertEqual(response.status_code,400)
        for route in ('/items?limit=1&limit=2','/items?query=x&query=y','/collections?parent_id=x&parent_id=y',
                      '/tags?query=a&query=b','/items?tags=AI','/collections?tag=AI','/library/identity?profile=other',
                      '/counts?library_root=other','/items/'+item['id']+'?item_id=other'):
            with self.subTest(route=route): self.assertEqual((await self.client.get(PREFIX+route)).status_code,400)
        self.assertEqual((await self.call('bookmark_get',{'item_id':item['id']}))['result']['notes'],'')

    async def test_duplicate_json_keys_nested_and_nonfinite_never_write(self):
        item=(await self.call('bookmark_save',{'url':'https://example.org/json'}))['result']
        for text in ('{"url":"https://example.org/a","url":"https://example.org/b"}',
                     '{"url":"https://example.org/a","favorite":NaN}'):
            response=await self.client.post(PREFIX+'/items',content=text)
            self.assertEqual(response.status_code,400)
        response=await self.client.post(PREFIX+'/items/'+item['id']+'/update',content='{"expected_revision":1,"changes":{"notes":"One","notes":"Two"}}')
        self.assertEqual(response.status_code,400)
        self.assertEqual((await self.call('bookmark_get',{'item_id':item['id']}))['result']['revision'],1)

    async def test_metadata_limit_streamed_bytes_not_content_length_and_chat_unchanged(self):
        large={'url':'https://example.org/large','notes':'N'*65536,'description':'D'*16384}
        response=await self.client.post(PREFIX+'/items',json=large)
        self.assertEqual(response.status_code,200,response.text)
        async def chunks():
            yield b'{"url":"https://example.org/over","notes":"'
            for _ in range(5): yield b'x'*30000
            yield b'"}'
        response=await self.client.post(PREFIX+'/items',content=chunks(),headers={'Content-Length':'1'})
        self.assertEqual(response.status_code,413)
        response=await self.client.post(PREFIX+'/collections',content=b' '*131073)
        self.assertEqual(response.status_code,413)
        response=await self.client.post(PREFIX+'/chat/threads',content=b' '*16385)
        self.assertEqual(response.status_code,413)
        self.assertEqual((await self.call('bookmark_search',{}))['result']['total'],1)

    async def test_native_image_receipts_require_key_and_preserve_legacy_result_shape(self):
        invalid=await self.call('bookmark_save',{'kind':'image','primary_asset_id':'a'*32})
        self.assertEqual(invalid['error']['code'],'invalid_argument')
        for params in ({'kind':'link','url':'https://example.org/source','primary_asset_id':'a'*32},
                       {'kind':'image','url':'https://example.org/source','primary_asset_id':'a'*32,'operation_key':str(uuid4())}):
            native=await self.call('bookmark_save',params)
            response=await self.client.post(PREFIX+'/items',json=params)
            self.assertEqual(native,response.json()); self.assertEqual(response.status_code,400)
        saved=await self.call('bookmark_save',{'url':'https://example.org/legacy-shape'})
        self.assertEqual(set(saved),{'ok','result'})
        self.assertEqual(await self.call('bookmark_get',{'item_id':saved['result']['id']}),saved)

    async def test_metadata_storage_failure_is_sanitized_503(self):
        from unittest.mock import patch
        from bookmarks.errors import StorageError
        with patch('runtime.get_service',side_effect=StorageError()):
            response=await self.client.get(PREFIX+'/counts')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['error']['code'],'storage_error')

    async def test_schema_objects_are_recursively_strict_and_registration_inventory_expands(self):
        for name in ('bookmark_update','bookmark_collection_update'):
            rule=self.tools[name]['schema']['parameters']['properties']['changes']
            self.assertEqual(rule['type'],'object'); self.assertIs(rule['additionalProperties'],False)
        self.assertEqual(self.tools['bookmark_save']['schema']['parameters']['properties']['tags']['maxItems'],20)
        self.assertEqual(self.tools['bookmark_save']['schema']['parameters']['properties']['attachment_ids']['maxItems'],10)
