"""Real SQLite/API conversation ownership; no model or personal sessions."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from runtime import bind_runtime


class ChatApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = 'default'
        self.cleanups = []
        test = self

        class Context:
            @property
            def profile_name(self):
                return test.profile

            def get_config(self, key, default=None):
                return test.temp.name if key == 'library_root' else default

            def on_unload(self, cleanup):
                test.cleanups.append(cleanup)

        self.context = Context()
        bind_runtime(self.context)
        self.addCleanup(lambda: [f() for f in reversed(self.cleanups)])
        path = Path(__file__).resolve().parents[1] / 'dashboard/plugin_api.py'
        spec = importlib.util.spec_from_file_location('bookmarks_chat_api_test', path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = FastAPI()
        app.include_router(module.router, prefix='/bookmarks')
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url='http://fixture.invalid')
        self.addAsyncCleanup(self.client.aclose)

    async def identity(self):
        response = await self.client.get('/bookmarks/chat/identity')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['result']

    async def test_library_identity_survives_reopen_but_not_different_library(self):
        first = await self.identity()
        self.assertRegex(first['library_id'], r'^[a-f0-9]{32}$')
        self.assertEqual(first['profile'], 'default')
        self.assertNotIn(self.temp.name, str(first))
        for cleanup in reversed(self.cleanups):
            cleanup()
        self.cleanups.clear()
        bind_runtime(self.context)
        self.assertEqual(await self.identity(), first)
        with tempfile.TemporaryDirectory() as other:
            for cleanup in reversed(self.cleanups):
                cleanup()
            self.cleanups.clear()
            context = SimpleNamespace(profile_name='default', get_config=lambda key, default=None: other if key == 'library_root' else default, on_unload=self.cleanups.append)
            bind_runtime(context)
            self.assertNotEqual((await self.identity())['library_id'], first['library_id'])

    async def test_bind_is_durable_idempotent_and_cannot_retarget_existing_thread(self):
        body = {'id': 'thread-one', 'session_id': '20261021_fixture_a', 'title': 'Reading list', 'model': None}
        first = await self.client.post('/bookmarks/chat/threads', json=body)
        self.assertEqual(first.status_code, 200, first.text)
        again = await self.client.post('/bookmarks/chat/threads', json=body)
        self.assertEqual(again.json(), first.json())
        changed = await self.client.post('/bookmarks/chat/threads', json={**body, 'session_id': 'foreign-session'})
        self.assertEqual(changed.status_code, 400)
        for cleanup in reversed(self.cleanups):
            cleanup()
        self.cleanups.clear()
        bind_runtime(self.context)
        result = (await self.client.get('/bookmarks/chat/threads')).json()['result']
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['threads'][0]['session_id'], '20261021_fixture_a')
        self.assertEqual(result['threads'][0]['profile'], 'default')

    async def test_active_profile_is_server_derived_and_foreign_thread_is_not_disclosed(self):
        body = {'id': 'thread-one', 'session_id': '20261021_default', 'title': 'Private conversation'}
        self.assertEqual((await self.client.post('/bookmarks/chat/threads', json=body)).status_code, 200)
        self.profile = 'work'
        self.assertEqual((await self.client.get('/bookmarks/chat/identity')).status_code, 503, 'An unregistered active profile must fail closed')
        bind_runtime(self.context)
        self.assertEqual((await self.identity())['profile'], 'work')
        response = await self.client.get('/bookmarks/chat/threads')
        self.assertEqual(response.json()['result']['threads'], [])
        self.assertNotIn('20261021_default', response.text)
        self.assertEqual((await self.client.post('/bookmarks/chat/threads', json=body)).status_code, 400)
        self.assertEqual((await self.client.post('/bookmarks/chat/threads', json={**body, 'id': 'thread-work', 'session_id': '20261021_work'})).status_code, 200)
        self.profile = 'default'
        self.assertEqual((await self.client.get('/bookmarks/chat/threads')).json()['result']['total'], 1)

    async def test_payload_validation_and_pagination_are_bounded(self):
        invalid = [None, [], {'id': '../escape', 'session_id': 'safe', 'title': 'x'},
                   {'id': 'safe', 'session_id': 'safe', 'profile': 'other'},
                   {'id': 'safe', 'session_id': 'safe', 'title': 'x' * 161},
                   {'id': 'safe', 'session_id': 'safe', 'model': {'provider': 'p', 'model': 'm', 'api_key': 'not-a-secret'}}]
        for body in invalid:
            with self.subTest(body=body):
                response = await self.client.post('/bookmarks/chat/threads', json=body)
                self.assertEqual(response.status_code, 400)
        for query in ['limit=101', 'limit=true', 'offset=-1', 'unexpected=x']:
            self.assertEqual((await self.client.get('/bookmarks/chat/threads?' + query)).status_code, 400)
        for i in range(3):
            response = await self.client.post('/bookmarks/chat/threads', json={'id': f'thread-{i}', 'session_id': f'session-{i}', 'title': f'Thread {i}'})
            self.assertEqual(response.status_code, 200)
        page = (await self.client.get('/bookmarks/chat/threads?limit=2&offset=1')).json()['result']
        self.assertEqual(page['total'], 3)
        self.assertEqual(len(page['threads']), 2)
        self.assertEqual([t['id'] for t in page['threads']], ['thread-1', 'thread-0'])
        huge = await self.client.post('/bookmarks/chat/threads', content=b'x' * 16385)
        self.assertEqual(huge.status_code, 413)


if __name__ == '__main__':
    unittest.main()
