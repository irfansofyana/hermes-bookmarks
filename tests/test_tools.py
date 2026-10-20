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

    def call(self, name, params):
        return json.loads(self.tools[name]['handler'](params, session_id='fixture'))

    async def test_native_save_http_get_and_search_share_data(self):
        saved = self.call('bookmark_save', {'url': 'https://example.org/a', 'title': 'Shared'})
        self.assertTrue(saved['ok'])
        item = saved['result']
        response = await self.client.get('/api/plugins/hermes-bookmarks/items/' + item['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), saved)
        found = self.call('bookmark_search', {'query': 'Shared'})
        self.assertEqual(found['result']['total'], 1)
        self.assertEqual(item['enrichment_status'], 'not_started')

    async def test_http_save_native_get_and_duplicate(self):
        response = await self.client.post('/api/plugins/hermes-bookmarks/items', json={'url': 'https://example.org/b'})
        self.assertEqual(response.status_code, 200)
        item = response.json()['result']
        self.assertEqual(self.call('bookmark_get', {'item_id': item['id']})['result'], item)
        self.assertEqual(self.call('bookmark_save', {'url': item['url']})['result']['id'], item['id'])

    async def test_both_boundaries_reject_wrong_types_and_unknown_fields(self):
        for params in ({'url': 'file:///secret'}, {'url': 'https://example.org', 'unexpected': True}, {'url': 3}):
            native = self.call('bookmark_save', params)
            response = await self.client.post('/api/plugins/hermes-bookmarks/items', json=params)
            self.assertFalse(native['ok'])
            self.assertGreaterEqual(response.status_code, 400)
            self.assertEqual(native, response.json())
        for params in ({'query': '', 'limit': True}, {'query': '', 'offset': -1}, {'query': '', 'limit': 101}):
            self.assertFalse(self.call('bookmark_search', params)['ok'])

    async def test_query_validation_and_not_found(self):
        response = await self.client.get('/api/plugins/hermes-bookmarks/items?limit=true')
        self.assertEqual(response.status_code, 400)
        response = await self.client.get('/api/plugins/hermes-bookmarks/items/missing')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')

    def test_schema_and_runtime_registration_are_bounded(self):
        self.assertEqual(set(self.tools), {'bookmark_save', 'bookmark_get', 'bookmark_search'})
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
