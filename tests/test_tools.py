"""Native/API parity uses real temporary storage, not mocked storage."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from native_tools import register_tools
from runtime import bind_runtime, BRIDGE_NAME

ROOT = Path(__file__).resolve().parents[1]


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cleanups = []
        self.tools = {}
        ctx = NS(get_config=lambda key, default=None: self.temp.name if key == 'library_root' else default,
                 on_unload=self.cleanups.append,
                 register_tool=lambda **kw: self.tools.update({kw['name']: kw}))
        bind_runtime(ctx)
        self.addCleanup(lambda: [f() for f in reversed(self.cleanups)])
        register_tools(ctx)
        spec = importlib.util.spec_from_file_location('bookmark_api_test', ROOT / 'dashboard/plugin_api.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router, prefix='/api/plugins/hermes-bookmarks')
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url='http://fixture.invalid')
        self.addAsyncCleanup(self.client.aclose)

    async def call(self, name, params):
        return json.loads(await self.tools[name]['handler'](params, session_id='fixture'))

    async def test_native_handlers_are_registered_for_the_public_async_lane(self):
        import inspect
        for tool in self.tools.values():
            self.assertIs(tool.get('is_async'),True)
            self.assertTrue(inspect.iscoroutinefunction(tool['handler']))

    async def test_health_reports_registration_startup_without_exposing_paths(self):
        from runtime import record_startup
        cleanups=[]
        ctx=NS(get_config=lambda key,default=None:self.temp.name if key=='library_root' else default,on_unload=cleanups.append)
        token=bind_runtime(ctx)
        try:
            record_startup(token,'fixture','configuration_required')
            response=await self.client.get('/api/plugins/hermes-bookmarks/health')
            payload=response.json()
            self.assertTrue(payload['library_configured'])
            self.assertIsNone(payload['library_ready'])  # Health performs no storage probe.
            self.assertIn({'profile':'fixture','result':'configuration_required'},payload['enrichment_startups'])
            self.assertNotIn(self.temp.name,json.dumps(payload))
        finally:
            for cleanup in reversed(cleanups): cleanup()
        self.assertEqual((await self.client.get('/api/plugins/hermes-bookmarks/health')).json()['enrichment_startups'],[])

    async def test_native_save_http_get_and_search_share_data(self):
        saved = await self.call('bookmark_save', {'url': 'https://example.org/a', 'title': 'Shared'})
        self.assertTrue(saved['ok'])
        item = saved['result']
        response = await self.client.get('/api/plugins/hermes-bookmarks/items/' + item['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), saved)
        found = await self.call('bookmark_search', {'query': 'Shared'})
        self.assertEqual(found['result']['total'], 1)
        self.assertEqual(item['enrichment_status'], 'pending')
        self.assertTrue(item['enrichment_job_id'])

    async def test_http_save_native_get_and_duplicate(self):
        response = await self.client.post('/api/plugins/hermes-bookmarks/items', json={'url': 'https://example.org/b'})
        self.assertEqual(response.status_code, 200)
        item = response.json()['result']
        self.assertEqual((await self.call('bookmark_get', {'item_id': item['id']}))['result'], item)
        self.assertEqual((await self.call('bookmark_save', {'url': item['url']}))['result']['id'], item['id'])

    async def test_both_boundaries_reject_wrong_types_and_unknown_fields(self):
        for params in ({'url': 'file:///secret'}, {'url': 'https://example.org', 'unexpected': True}, {'url': 3}):
            native = await self.call('bookmark_save', params)
            response = await self.client.post('/api/plugins/hermes-bookmarks/items', json=params)
            self.assertFalse(native['ok'])
            self.assertGreaterEqual(response.status_code, 400)
            self.assertEqual(native, response.json())
        for params in ({'query': '', 'limit': True}, {'query': '', 'offset': -1}, {'query': '', 'limit': 101}):
            self.assertFalse((await self.call('bookmark_search', params))['ok'])

    async def test_image_upload_preview_and_native_metadata(self):
        from io import BytesIO
        from PIL import Image
        image=BytesIO(); Image.new('RGB',(2,2),'blue').save(image,format='PNG')
        response=await self.client.post('/api/plugins/hermes-bookmarks/assets',content=image.getvalue(),headers={'Content-Type':'image/png'})
        self.assertEqual(response.status_code,200)
        item=response.json()['result']
        got=await self.call('bookmark_attachment_get',{'asset_id':item['id']})
        self.assertTrue(got['ok']); self.assertEqual(got['result']['width'],2)
        preview=await self.client.get('/api/plugins/hermes-bookmarks/assets/'+item['id']+'/preview')
        self.assertTrue(preview.json()['result']['content_base64'])
        original=await self.client.get('/api/plugins/hermes-bookmarks/assets/'+item['id'])
        self.assertEqual(original.headers['content-type'],'image/png')
        multipart=await self.client.post('/api/plugins/hermes-bookmarks/assets',files={'file':('fixture.png',image.getvalue(),'image/png')})
        self.assertEqual(multipart.status_code,200)
        import base64
        encoded=await self.client.post('/api/plugins/hermes-bookmarks/assets/base64',json={'content_base64':base64.b64encode(image.getvalue()).decode('ascii'),'mime_type':'image/png'})
        self.assertEqual(encoded.status_code,200)
        invalid=await self.client.post('/api/plugins/hermes-bookmarks/assets',content=b'<svg/>',headers={'Content-Type':'image/svg+xml'})
        self.assertEqual(invalid.status_code,400)

    async def test_owned_assets_surface_safe_storage_failures(self):
        from unittest.mock import patch
        from bookmarks.errors import StorageError
        with patch('bookmarks.assets.AssetStore', side_effect=StorageError()):
            response=await self.client.get('/api/plugins/hermes-bookmarks/assets/'+'a'*32+'/preview')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['error']['code'],'storage_error')

    async def test_query_validation_and_not_found(self):
        response = await self.client.get('/api/plugins/hermes-bookmarks/items?limit=true')
        self.assertEqual(response.status_code, 400)
        response = await self.client.get('/api/plugins/hermes-bookmarks/items/missing')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')

    def test_schema_and_runtime_registration_are_bounded(self):
        self.assertEqual(set(self.tools), {'bookmark_attachment_add', 'bookmark_attachment_get', 'bookmark_save', 'bookmark_get', 'bookmark_search'})
        for tool in self.tools.values():
            self.assertIs(tool['schema']['parameters']['additionalProperties'], False)
        self.assertEqual(self.tools['bookmark_search']['schema']['parameters']['properties']['limit']['maximum'], 100)


class RuntimeTests(unittest.TestCase):
    def test_missing_config_fails_without_creating_storage(self):
        from runtime import get_service
        saved = sys.modules.pop(BRIDGE_NAME, None)
        self.addCleanup(lambda: sys.modules.__setitem__(BRIDGE_NAME, saved) if saved else None)
        with self.assertRaises(Exception) as exc:
            get_service()
        self.assertEqual(exc.exception.code, 'configuration_error')

    def test_different_configured_roots_refused_and_unload_is_owned(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            from runtime import get_service
            ca, cb = [], []
            def context(root, cleanup):
                return NS(get_config=lambda key, default=None: root, on_unload=cleanup.append)
            bind_runtime(context(a, ca))
            try:
                with self.assertRaises(Exception):
                    bind_runtime(context(b, cb))
                item = get_service().save_link('https://example.org')
                self.assertEqual(get_service().get(item['id'])['url'], 'https://example.org')
            finally:
                for f in reversed(ca + cb):
                    f()
            self.assertNotIn(BRIDGE_NAME, sys.modules)
