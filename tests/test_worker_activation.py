"""Public async entry activation, not a custom host loop or scheduler."""
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest
from runtime import bind_runtime, record_startup, get_status, ensure_enrichment


class ActivationTests(unittest.IsolatedAsyncioTestCase):
    async def fixture(self,root):
        self.cleanups=[]; self.tasks=[]
        route={'provider':'fixture','model':'not-invoked','owner_profile':'default'}
        def spawn(coro,**kwargs):
            task=asyncio.create_task(coro,name=kwargs['name'])
            self.tasks.append(task); self.cleanups.append(task.cancel); return task
        self.ctx=NS(profile_name='default',get_config=lambda key,default=None:{'library_root':str(root),'enrichment_route':route}.get(key,default),
                    on_unload=self.cleanups.append,spawn_task=spawn,llm=NS(acomplete_structured=lambda **kwargs:None))
        token=bind_runtime(self.ctx)
        record_startup(token,'default','host_loop_unavailable')
    async def unload(self):
        for cleanup in reversed(self.cleanups): cleanup()
        await asyncio.gather(*self.tasks,return_exceptions=True)
    async def test_async_entry_activates_once_and_host_owns_unload(self):
        with tempfile.TemporaryDirectory() as root:
            await self.fixture(root)
            try:
                ensure_enrichment(); ensure_enrichment()
                self.assertEqual(len(self.tasks),1)
                self.assertEqual(get_status()['enrichment_startups'],[{'profile':'default','result':'started'}])
            finally: await self.unload()
            self.assertFalse(get_status()['library_configured'])
            ensure_enrichment(); self.assertEqual(len(self.tasks),1)
    async def test_request_from_another_profile_cannot_start_owner_context(self):
        with tempfile.TemporaryDirectory() as root:
            await self.fixture(root)
            try:
                self.ctx.profile_name='reader'
                ensure_enrichment()
                self.assertEqual(self.tasks,[])
                self.assertFalse((Path(root)/'bookmarks.sqlite3').exists())
            finally: await self.unload()
