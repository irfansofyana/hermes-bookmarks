import asyncio
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import native_tools

class PortabilityCancellationTests(unittest.IsolatedAsyncioTestCase):
 async def test_native_admitted_portability_write_drains_repeated_cancellation(self):
  entered=threading.Event();release=threading.Event();finished=threading.Event();tools={}
  native_tools.register_tools(SimpleNamespace(register_tool=lambda **kw:tools.update({kw['name']:kw})))
  def dispatch(name,params):
   entered.set();release.wait(5);finished.set();return {'ok':True,'result':{}}
  with patch('native_tools.dispatch',dispatch):
   task=asyncio.create_task(tools['bookmark_backup_restore']['handler']({}))
   await asyncio.to_thread(entered.wait,2)
   try:
    task.cancel();await asyncio.sleep(.02);task.cancel();await asyncio.sleep(.02)
    self.assertFalse(task.done(),'Cancellation must drain admitted write before acknowledgement')
   finally:release.set()
   with self.assertRaises(asyncio.CancelledError):await task
   self.assertTrue(finished.is_set())
