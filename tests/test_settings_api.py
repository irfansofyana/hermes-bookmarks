"""Direct-router/native parity only, not actual-host authentication evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import FastAPI
from httpx import ASGITransport,AsyncClient
import runtime
import native_tools

class SettingsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.cleanups=[];self.tools={}
        ctx=NS(get_config=lambda k,d=None:self.tmp.name if k=='library_root' else d,
            profile_name='owner',on_unload=self.cleanups.append,register_tool=lambda **kw:self.tools.update({kw['name']:kw}))
        runtime.bind_runtime(ctx);native_tools.register_tools(ctx)
        self.addCleanup(lambda:[fn() for fn in reversed(self.cleanups)])
        root=Path(__file__).parents[1]
        spec=importlib.util.spec_from_file_location('settings_api_fixture',root/'dashboard/plugin_api.py')
        self.api=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.api)
        app=FastAPI();app.include_router(self.api.router)
        self.client=AsyncClient(transport=ASGITransport(app=app),base_url='http://fixture.invalid')
        self.addAsyncCleanup(self.client.aclose)
        self.service=runtime.get_service()

    async def native(self,name,body):return json.loads(await self.tools[name]['handler'](body))

    async def test_settings_http_native_parity_and_strict_revision(self):
        got=(await self.client.get('/settings')).json()
        self.assertEqual(got,await self.native('bookmark_settings_get',{}))
        changes={'model':'synthetic','provider':'fixture','image_analysis':True}
        body={'expected_revision':got['result']['revision'],'changes':changes}
        saved=await self.client.post('/settings',json=body)
        self.assertEqual(saved.status_code,200)
        self.assertEqual((await self.native('bookmark_settings_get',{}))['result'],saved.json()['result'])
        stale=await self.client.post('/settings',json=body)
        self.assertEqual(stale.status_code,409);self.assertEqual(stale.json()['error']['current_revision'],saved.json()['result']['revision'])

    async def test_all_read_routes_do_not_activate_or_resume_workers(self):
        with patch.object(runtime,'ensure_enrichment') as activate:
            for route in ('/settings','/health','/library/identity','/counts','/items','/enrichment/requests/'+str(uuid4()),'/enrichment/jobs/missing'):
                await self.client.get(route)
            activate.assert_not_called()
        with patch.object(native_tools,'ensure_enrichment') as activate:
            await self.native('bookmark_settings_get',{})
            await self.native('bookmark_enrichment_request_get',{'request_id':str(uuid4())})
            activate.assert_not_called()

    async def test_invalid_settings_do_not_activate_or_change_state(self):
        before=self.service.settings_get()
        with patch.object(runtime,'ensure_enrichment') as activate:
            for changes in ({'owner_profile':'other'},{'paused':1},{'api_key':'never-accepted'}):
                response=await self.client.post('/settings',json={'expected_revision':before['revision'],'changes':changes})
                self.assertEqual(response.status_code,400)
            activate.assert_not_called()
        self.assertEqual(self.service.settings_get(),before)

    async def test_enrichment_receipt_route_is_static_safe_and_public_projection_is_bounded(self):
        from bookmarks.settings import SettingsStore
        SettingsStore(self.service._storage).seed_route({'provider':'fixture','model':'synthetic','owner_profile':'owner'})
        cfg=self.service.settings_get();self.service.settings_update(cfg['revision'],{'automatic_tags':False,'automatic_summary':False})
        item=self.service.save_link('https://example.org/accepted')
        body={'expected_revision':item['revision'],'request_id':str(uuid4()),'fields':['summary']}
        first=await self.client.post('/items/'+item['id']+'/enrich',json=body)
        self.assertEqual(first.status_code,200)
        read=await self.client.get('/enrichment/requests/'+body['request_id'])
        self.assertEqual(read.json(),first.json())
        job=first.json()['result']['job']
        self.assertNotIn('token',job);self.assertNotIn('settings',job)
        status=await self.native('bookmark_enrichment_get',{'job_id':job['id']})
        self.assertEqual(status['result'],job)
        cancelled=await self.client.post('/enrichment/jobs/'+job['id']+'/cancel',json={})
        self.assertEqual(cancelled.json()['result']['state'],'cancelled')
        again=await self.native('bookmark_enrichment_cancel',{'job_id':job['id']})
        self.assertEqual(again,cancelled.json())

    async def test_native_and_http_settings_writes_drain_repeated_cancellation(self):
        import asyncio
        from threading import Event
        from bookmarks.service import BookmarkService
        for boundary in ('native','http'):
            before=self.service.settings_get();entered=Event();release=Event()
            original=BookmarkService.settings_update
            def held(service,*args,**kwargs):
                entered.set()
                if not release.wait(3):raise TimeoutError('Unreleased synthetic write')
                return original(service,*args,**kwargs)
            params={'expected_revision':before['revision'],'changes':{'guidance':boundary}}
            with patch.object(BookmarkService,'settings_update',held):
                call=self.native('bookmark_settings_update',params) if boundary=='native' else self.client.post('/settings',json=params)
                task=asyncio.create_task(call)
                self.assertTrue(await asyncio.to_thread(entered.wait,2))
                task.cancel();await asyncio.sleep(.02);task.cancel();await asyncio.sleep(.02)
                self.assertFalse(task.done(),'Cancellation abandoned an admitted write')
                release.set()
                with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(self.service.settings_get()['settings']['guidance'],boundary)

    async def test_duplicate_json_keys_and_path_identity_override_rejected(self):
        response=await self.client.post('/settings',content='{"expected_revision":1,"expected_revision":1,"changes":{}}')
        self.assertEqual(response.status_code,400)
        response=await self.client.post('/items/missing/enrich',json={'item_id':'other','expected_revision':1,'request_id':str(uuid4()),'fields':['summary']})
        self.assertEqual(response.status_code,400)

if __name__=='__main__':unittest.main()
