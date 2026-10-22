"""Importer activation is independent of inference configuration."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4
from bookmarks.service import BookmarkService
import runtime

class ImportWorkerTests(unittest.IsolatedAsyncioTestCase):
 async def test_public_async_activation_imports_after_request_returns_and_unload_stops(self):
  with tempfile.TemporaryDirectory() as d:
   cleanups=[];tasks=[]
   def spawn(coro,**kwargs):
    task=asyncio.create_task(coro);tasks.append(task);cleanups.append(task.cancel);return task
   ctx=NS(profile_name='default',get_config=lambda k,default=None:d if k=='library_root' else default,on_unload=cleanups.append,spawn_task=spawn)
   runtime.bind_runtime(ctx)
   try:
    s=BookmarkService(Path(d));p=s.import_preview(records=[{'url':'https://example.org/async'}]);j=s.import_start(p['preview_id'],p['input_digest'],str(uuid4()))
    runtime.ensure_imports();runtime.ensure_imports()
    self.assertEqual(len(tasks),1)
    async with asyncio.timeout(3):
     while s.import_job_get(j['id'])['state']!='succeeded':await asyncio.sleep(.02)
    self.assertEqual(s.search()['total'],1)
    ctx.profile_name='other';runtime.ensure_imports();self.assertEqual(len(tasks),1)
   finally:
    for cleanup in reversed(cleanups):cleanup()
    await asyncio.gather(*tasks,return_exceptions=True)
   runtime.ensure_imports();self.assertEqual(len(tasks),1)
