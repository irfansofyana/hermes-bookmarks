"""Real SQLite faults, public async activation and lifecycle status; no inference."""
import asyncio
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from bookmarks.errors import StorageError, StorageBusyError
from bookmarks.jobs import JobQueue
from bookmarks.service import BookmarkService
from runtime import bind_runtime, record_startup, ensure_enrichment, get_status


class WorkerRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='bookmarks-recovery-')
        self.root = Path(self.temporary.name)
        self.cleanups, self.tasks = [], []
        route = {'provider':'fixture', 'model':'never-called', 'owner_profile':'default'}
        def spawn(coro, **kwargs):
            task = asyncio.create_task(coro, name=kwargs['name'])
            self.tasks.append(task)
            self.cleanups.append(task.cancel)
            return task
        async def forbidden(*args, **kwargs):
            raise AssertionError('This lifecycle probe must not fetch or call a model')
        self.no_fetch = patch('worker_host.extract_text', forbidden)
        self.no_fetch.start()
        self.ctx = NS(profile_name='default', get_config=lambda key,default=None:{'library_root':str(self.root),'enrichment_route':route}.get(key,default),
                      on_unload=self.cleanups.append, spawn_task=spawn, llm=NS(acomplete_structured=forbidden))
        token = bind_runtime(self.ctx)
        record_startup(token, 'default', 'host_loop_unavailable')

    async def asyncTearDown(self):
        for cleanup in reversed(self.cleanups):
            cleanup()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.no_fetch.stop()
        self.temporary.cleanup()

    def start_with_incomplete_job(self):
        ensure_enrichment()
        service = BookmarkService(self.root)
        queue = JobQueue(self.root)
        item = service.save_link('https://example.org/fixture')
        job = queue.enqueue(item['id'], 1, {})
        return queue, job

    def short_busy_timeout(self):
        connect = sqlite3.connect
        def real_connect(*args, **kwargs):
            kwargs['timeout'] = 0.03
            return connect(*args, **kwargs)
        return patch('bookmarks.storage.sqlite3.connect', real_connect)

    async def await_job(self, queue, job):
        async with asyncio.timeout(2):
            while True:
                try:
                    if queue.get(job)['state'] == 'failed': break
                except StorageBusyError:
                    # The observing connection shares the intentionally shortened
                    # timeout; let the real worker finish its current write.
                    pass
                if self.tasks[-1].done():
                    self.fail('Worker terminated before processing the queued job')
                await asyncio.sleep(0.01)
        self.assertEqual(queue.get(job)['error'], 'configuration_required')

    async def test_real_transient_lock_recovers_without_losing_the_worker(self):
        queue, job = self.start_with_incomplete_job()
        connection = sqlite3.connect(queue.storage.database_path)
        connection.execute('BEGIN IMMEDIATE')
        saw_busy = asyncio.Event()
        loop = asyncio.get_running_loop()
        original = JobQueue.recover_expired
        def recover(actual, *args, **kwargs):
            try:
                return original(actual, *args, **kwargs)
            except StorageError:
                loop.call_soon_threadsafe(saw_busy.set)
                raise
        try:
            with self.short_busy_timeout(), patch.object(JobQueue, 'recover_expired', recover):
                await asyncio.wait_for(saw_busy.wait(), 2)
                connection.rollback()
                await self.await_job(queue, job)
            self.assertFalse(self.tasks[0].done())
            ensure_enrichment()
            self.assertEqual(len(self.tasks), 1)
            self.assertEqual(get_status()['enrichment_startups'][0]['result'], 'started')
        finally:
            connection.rollback()
            connection.close()

    async def test_exhausted_lock_budget_reports_failure_and_owner_can_restart_after_cooldown(self):
        queue, job = self.start_with_incomplete_job()
        connection = sqlite3.connect(queue.storage.database_path)
        connection.execute('BEGIN IMMEDIATE')
        try:
            with self.short_busy_timeout():
                await asyncio.wait({self.tasks[0]}, timeout=2)
            self.assertTrue(self.tasks[0].done(), 'Persistent contention must have a bounded retry budget')
            await asyncio.sleep(0)
            self.assertEqual(get_status()['enrichment_startups'][0]['result'], 'storage_unavailable')
            ensure_enrichment()
            ensure_enrichment()
            self.assertEqual(len(self.tasks), 1, 'Foreground calls must not cause an immediate restart storm')
            connection.rollback()
            with patch('runtime.monotonic', return_value=time.monotonic()+31):
                self.ctx.profile_name = 'reader'
                ensure_enrichment()
                self.assertEqual(len(self.tasks), 1, 'Another profile must not restart the original owner')
                self.ctx.profile_name = 'default'
                ensure_enrichment()
                ensure_enrichment()
                self.assertEqual(len(self.tasks), 2)
            await self.await_job(queue, job)
            self.assertEqual(get_status()['enrichment_startups'][0]['result'], 'started')
        finally:
            connection.rollback()
            connection.close()

    async def test_corrupt_storage_terminates_visibly_without_retrying_or_reviving_unloaded_metadata(self):
        queue, _ = self.start_with_incomplete_job()
        queue.storage.database_path.write_bytes(b'not a sqlite database: private-fault-marker')
        await asyncio.wait({self.tasks[0]}, timeout=0.2)
        self.assertTrue(self.tasks[0].done(), 'Permanent storage faults must not be retried as busy locks')
        await asyncio.sleep(0)
        status = get_status()
        self.assertEqual(status['enrichment_startups'][0]['result'], 'storage_unavailable')
        self.assertNotIn('private-fault-marker', str(status))
        for cleanup in reversed(self.cleanups):
            cleanup()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.assertEqual(get_status()['enrichment_startups'], [])
        with patch('runtime.monotonic', return_value=time.monotonic()+31):
            ensure_enrichment()
        self.assertEqual(len(self.tasks), 1)
