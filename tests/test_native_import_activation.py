"""Cold public registration -> native async lane -> real supervised workers."""
import asyncio
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'native_import_activation_plugin'
spec = importlib.util.spec_from_file_location(PACKAGE, ROOT / '__init__.py',
                                              submodule_search_locations=[str(ROOT)])
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE] = plugin
spec.loader.exec_module(plugin)
runtime = importlib.import_module(PACKAGE + '.runtime')
worker_host = importlib.import_module(PACKAGE + '.worker_host')


class NativeImportActivationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # unittest runs synchronous setUp outside the async host lane. Exercise
        # the actual plugin entry point, not a fabricated startup status.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cleanups, self.tasks, self.tools, self.completions = [], [], {}, []
        self.route = {'provider': 'synthetic', 'model': 'fixture', 'owner_profile': 'owner'}

        def spawn(coro, *, name):
            task = asyncio.create_task(coro, name=name)
            self.tasks.append(task)
            self.cleanups.append(task.cancel)
            return task

        async def complete(**kwargs):
            self.completions.append(kwargs)
            return NS(parsed={'summary': 'Synthetic imported article', 'tags': ['Fixture']},
                      provider='synthetic', model='fixture')

        async def fetch(url):
            return 'Supplied synthetic article text for ' + url

        run_worker = worker_host.run_worker

        def fast_worker(*args):
            return run_worker(*args, poll_seconds=0.005)

        self.enterContext(patch.object(worker_host, 'extract_text', fetch))
        self.enterContext(patch.object(worker_host, 'run_worker', fast_worker))
        ctx = NS(profile_name='owner',
                 get_config=lambda key, default=None: {
                     'library_root': self.temp.name, 'enrichment_route': self.route,
                 }.get(key, default),
                 on_unload=self.cleanups.append, spawn_task=spawn,
                 register_command=lambda **kwargs: None,
                 register_tool=lambda **kwargs: self.tools.update({kwargs['name']: kwargs}),
                 llm=NS(acomplete_structured=complete))
        plugin.register(ctx)
        self.assertEqual(runtime.get_status()['enrichment_startups'],
                         [{'profile': 'owner', 'result': 'host_loop_unavailable'}])
        self.assertEqual(self.tasks, [])

    async def asyncTearDown(self):
        for cleanup in reversed(self.cleanups):
            cleanup()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.assertEqual(runtime.get_status()['enrichment_startups'], [])

    async def call(self, name, params):
        response = json.loads(await self.tools[name]['handler'](params))
        self.assertTrue(response['ok'], response)
        return response['result']

    async def preview(self, options=None):
        params = {'records': [{'url': 'https://example.org/' + uuid4().hex}]}
        if options is not None:
            params['options'] = options
        preview = await self.call('bookmark_import_preview', params)
        self.assertEqual(self.tasks, [], 'Staging alone must not activate inference')
        return {'preview_id': preview['preview_id'], 'input_digest': preview['input_digest'],
                'request_id': str(uuid4())}

    async def wait_import(self, job_id):
        async with asyncio.timeout(4):
            while True:
                job = await self.call('bookmark_job_get', {'job_id': job_id})
                if job['state'] == 'succeeded':
                    return job
                await asyncio.sleep(0.01)

    async def test_opt_in_start_activates_cold_owner_and_enrichment_progresses(self):
        params = await self.preview({'enrich': True})
        job = await self.call('bookmark_import_start', params)
        self.assertEqual([t.get_name() for t in self.tasks].count('bookmarks-enrichment'), 1)
        job = await self.wait_import(job['id'])
        self.assertEqual(job['imported'], 1)
        item_id = job['rows'][0]['item_id']
        async with asyncio.timeout(4):
            while True:
                item = await self.call('bookmark_get', {'item_id': item_id})
                if item['enrichment_status'] == 'succeeded':
                    break
                await asyncio.sleep(0.01)
        self.assertEqual(item['summary'], 'Synthetic imported article')
        self.assertEqual(len(self.completions), 1)
        self.assertEqual(self.completions[0]['provider'], 'synthetic')
        self.assertEqual(self.completions[0]['model'], 'fixture')
        # Idempotent retries and all import read/cancel entries reuse the owner.
        await self.call('bookmark_import_start', params)
        await self.call('bookmark_import_request_get', {'request_id': params['request_id']})
        await self.call('bookmark_job_cancel', {'job_id': job['id']})
        self.assertEqual([t.get_name() for t in self.tasks].count('bookmarks-enrichment'), 1)

    async def test_default_and_explicit_false_imports_do_not_activate_inference(self):
        for options in (None, {'enrich': False}):
            with self.subTest(options=options):
                # The second preview is still cold for enrichment, but the
                # independent importer has already been supervised.
                params: dict = {'records': [{'url': 'https://example.org/' + uuid4().hex}]}
                if options is not None:
                    params['options'] = options
                preview = await self.call('bookmark_import_preview', params)
                start = {'preview_id': preview['preview_id'], 'input_digest': preview['input_digest'],
                         'request_id': str(uuid4())}
                job = await self.call('bookmark_import_start', start)
                job = await self.wait_import(job['id'])
                await self.call('bookmark_import_request_get', {'request_id': start['request_id']})
                await self.call('bookmark_job_cancel', {'job_id': job['id']})
                item = await self.call('bookmark_get', {'item_id': job['rows'][0]['item_id']})
                self.assertIsNone(item['enrichment_job_id'])
                self.assertEqual([t.get_name() for t in self.tasks], ['bookmarks-imports'])
                self.assertEqual(self.completions, [])
                self.assertEqual(runtime.get_status()['enrichment_startups'][0]['result'],
                                 'host_loop_unavailable')

    async def assert_cold_reentry_activates(self, name):
        params = await self.preview({'enrich': True})
        # Simulate an accepted Start whose acknowledgement/host generation was
        # lost. No handler-local preview cache can establish this job's opt-in.
        job = await asyncio.to_thread(runtime.get_service().import_start, **params)
        self.assertEqual(self.tasks, [])
        arguments = ({'request_id': params['request_id']}
                     if name == 'bookmark_import_request_get' else {'job_id': job['id']})
        await self.call(name, arguments)
        self.assertEqual([t.get_name() for t in self.tasks].count('bookmarks-enrichment'), 1)
        self.assertEqual(runtime.get_status()['enrichment_startups'][0]['result'], 'started')

    async def test_cold_job_poll_activates_persisted_opt_in(self):
        await self.assert_cold_reentry_activates('bookmark_job_get')

    async def test_cold_request_lookup_activates_persisted_opt_in(self):
        await self.assert_cold_reentry_activates('bookmark_import_request_get')

    async def test_cold_cancel_activates_persisted_opt_in_for_committed_rows(self):
        params = await self.preview({'enrich': True})
        service = runtime.get_service()
        job = await asyncio.to_thread(service.import_start, **params)
        # Commit the opted-in import before returning to the native async lane.
        # Cancellation must still wake enrichment for already committed rows.
        queue_module = importlib.import_module(PACKAGE + '.bookmarks.imports.runner')
        storage_module = importlib.import_module(PACKAGE + '.bookmarks.storage')
        queue = queue_module.ImportQueue(storage_module.Storage(Path(self.temp.name)))
        claim = await asyncio.to_thread(queue.claim, 'prior-host')
        self.assertTrue(await asyncio.to_thread(queue.step, claim))
        await self.call('bookmark_job_cancel', {'job_id': job['id']})
        self.assertEqual([t.get_name() for t in self.tasks].count('bookmarks-enrichment'), 1)

    async def test_rejected_import_requests_do_not_activate_inference(self):
        params = await self.preview({'enrich': True})
        for name, arguments in (
            ('bookmark_import_start', {**params, 'input_digest': '0' * 64}),
            ('bookmark_job_get', {'job_id': 'missing'}),
            ('bookmark_job_cancel', {'job_id': 'missing'}),
            ('bookmark_import_request_get', {'request_id': str(uuid4())}),
        ):
            with self.subTest(name=name):
                result = json.loads(await self.tools[name]['handler'](arguments))
                self.assertFalse(result['ok'], result)
                self.assertEqual([t.get_name() for t in self.tasks], ['bookmarks-imports'])
                self.assertEqual(self.completions, [])
                self.assertEqual(runtime.get_status()['enrichment_startups'][0]['result'],
                                 'host_loop_unavailable')
