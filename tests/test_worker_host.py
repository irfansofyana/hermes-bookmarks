import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from worker_host import start_enrichment

class LiveLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_spawns_host_owned_task_and_unload_cancels_it(self):
        from unittest.mock import patch
        tasks=[]
        with tempfile.TemporaryDirectory() as d:
            route={'provider':'fixture','model':'pinned','owner_profile':'owner'}
            async def complete(**kwargs): return NS(parsed={'summary':'Synthetic','tags':[]},provider='fixture',model='pinned')
            def spawn(coro,**kwargs):
                task=asyncio.create_task(coro); tasks.append(task); return task
            ctx=NS(get_config=lambda key,default=None:{'library_root':d,'enrichment_route':route}.get(key,default),profile_name='owner',spawn_task=spawn,llm=NS(acomplete_structured=complete))
            self.assertEqual(start_enrichment(ctx),'started')
            self.assertEqual(len(tasks),1)
            tasks[0].cancel()
            with self.assertRaises(asyncio.CancelledError): await tasks[0]


class WorkerHostTests(unittest.TestCase):
    def context(self,root,profile):
        self.calls=[]
        self.route={'provider':'fixture','model':'pinned','owner_profile':'owner'}
        def config(key,default=None): return {'library_root':root,'enrichment_route':self.route}.get(key,default)
        return NS(get_config=config,profile_name=profile,spawn_task=lambda *a,**k:self.calls.append(a),llm=NS(acomplete_structured=lambda **k:None))
    def test_missing_running_loop_never_creates_unowned_worker(self):
        with tempfile.TemporaryDirectory() as d:
            ctx=self.context(d,'owner')
            self.assertEqual(start_enrichment(ctx),'host_loop_unavailable')
            self.assertEqual(self.calls,[])
    def test_persisted_model_edit_survives_stale_owner_bootstrap(self):
        with tempfile.TemporaryDirectory() as d:
            ctx=self.context(d,'owner')
            self.assertEqual(start_enrichment(ctx),'host_loop_unavailable')
            from bookmarks.service import BookmarkService
            service=BookmarkService(Path(d));cfg=service.settings_get()
            service.settings_update(cfg['revision'],{'model':'new-library-model','image_analysis':True})
            self.assertEqual(start_enrichment(ctx),'host_loop_unavailable')
            self.assertEqual(service.settings_get()['settings']['model'],'new-library-model')
            self.assertTrue(service.settings_get()['settings']['image_analysis'])

    def test_nonowner_profile_cannot_change_execution_identity(self):
        with tempfile.TemporaryDirectory() as d:
            ctx=self.context(d,'other')
            self.route['model']='stale-nonowner-model'
            self.assertEqual(start_enrichment(ctx),'not_owner')
            self.assertEqual(self.calls,[])
            self.assertFalse((Path(d)/'bookmarks.sqlite3').exists())
            owner=self.context(d,'owner')
            self.assertEqual(start_enrichment(owner),'host_loop_unavailable')
            from bookmarks.jobs import JobQueue
            self.assertEqual(JobQueue(Path(d)).route()['model'],'pinned')
