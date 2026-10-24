import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from bookmarks.service import BookmarkService
from bookmarks.jobs import JobQueue
from bookmarks.errors import ConflictError, ValidationError

ROUTE={'provider':'fixture','model':'synthetic','owner_profile':'owner'}
RESULT={'summary':'Generated','tags':['Generated'],'provider':'fixture','model':'synthetic','coverage':'extracted_text'}

class RequestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.service=BookmarkService(self.root)
        from bookmarks.settings import SettingsStore
        store=SettingsStore(self.service._storage);store.seed_route(ROUTE)
        cfg=store.get();store.update(cfg['revision'],{'automatic_summary':False,'automatic_tags':False})
        self.item=self.service.save_link('https://example.org/synthetic')
        self.request=str(uuid4());self.q=JobQueue(self.root)

    def admit(self,fields=None):
        return self.service.enrich(self.item['id'],self.item['revision'],self.request,fields or ['summary','tags'])

    def test_receipt_first_replay_retains_original_settings_and_revision(self):
        first=self.admit()
        self.service.update(self.item['id'],self.item['revision'],{'notes':'Keep'})
        cfg=self.service.settings_get();self.service.settings_update(cfg['revision'],{'model':'other'})
        again=self.admit(['tags','summary'])
        self.assertEqual(first['receipt'],again['receipt'])
        self.assertEqual(self.service.enrichment_request_get(self.request)['receipt'],first['receipt'])
        with self.assertRaises(ConflictError):self.admit(['tags'])
        self.assertEqual(self.q.get(first['job']['id'])['settings']['route']['model'],'synthetic')

    def test_cancel_then_explicit_new_request_same_revision_has_fresh_generation(self):
        first=self.admit();job=self.q.claim('worker',now=100)
        self.service.enrichment_cancel(first['job']['id'])
        self.request=str(uuid4());second=self.admit()
        self.assertNotEqual(first['job']['id'],second['job']['id'])
        self.assertGreater(second['job']['generation'],first['job']['generation'])
        self.assertFalse(self.q.complete(job['id'],'worker',RESULT,token=job['token'],now=101))
        self.assertEqual(self.service.get(self.item['id'])['summary'],'')

    def test_concurrent_receipt_admission_is_exactly_once(self):
        def run(_):return BookmarkService(self.root).enrich(self.item['id'],1,self.request,['summary'])
        with ThreadPoolExecutor(max_workers=2) as pool:answers=list(pool.map(run,range(2)))
        self.assertEqual(answers[0]['receipt'],answers[1]['receipt'])
        with self.service._storage._transaction() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM enrichment_requests').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],1)

    def test_pause_stops_claims_but_does_not_mutate_accepted_snapshot(self):
        first=self.admit()
        cfg=self.service.settings_get();self.service.settings_update(cfg['revision'],{'paused':True,'model':'new'})
        self.assertIsNone(self.q.claim('worker',now=100))
        cfg=self.service.settings_get();self.service.settings_update(cfg['revision'],{'paused':False})
        job=self.q.claim('worker',now=101)
        self.assertEqual(job['id'],first['job']['id'])
        self.assertEqual(job['settings']['route']['model'],'synthetic')

    def test_capture_reads_persisted_settings_not_legacy_service_cache(self):
        old=BookmarkService(self.root,enrichment_settings=ROUTE)
        cfg=self.service.settings_get();updated=self.service.settings_update(cfg['revision'],{'automatic_summary':True,'model':'new'})
        item=old.save_link('https://example.org/after-update')
        accepted=self.q.get(item['enrichment_job_id'])
        self.assertEqual(accepted['settings']['route']['model'],'new')
        self.assertEqual(accepted['settings']['settings_revision'],updated['revision'])
        self.assertEqual(accepted['settings']['fields'],['summary'])

    def test_pending_duplicate_request_conflicts_and_read_projection_hides_leases(self):
        first=self.admit();self.request=str(uuid4())
        with self.assertRaises(ConflictError):self.admit()
        self.q.claim('worker',now=100)
        public=self.service.enrichment_get(first['job']['id'])
        self.assertNotIn('token',public);self.assertNotIn('settings',public);self.assertNotIn('worker',public)
        self.assertEqual(public['state'],'running')

    def test_bad_fields_and_uuid_rejected_without_jobs(self):
        for fields in ([],['summary','summary'],['notes'],'summary'):
            with self.assertRaises(ValidationError):self.service.enrich(self.item['id'],1,self.request,fields)
        with self.assertRaises(ValidationError):self.service.enrich(self.item['id'],True,self.request,['summary'])
        with self.assertRaises(ValidationError):self.service.enrich(self.item['id'],1,'not-a-uuid',['summary'])

class OwnershipTests(RequestTests):
    def test_late_summary_cannot_overwrite_manual_but_safe_tags_are_reported(self):
        first=self.admit();job=self.q.claim('worker',now=100)
        self.service.update(self.item['id'],1,{'summary':'My words','notes':'Keep notes','add_tags':['Manual']})
        self.q.complete(job['id'],'worker',RESULT,token=job['token'],now=101)
        item=self.service.get(self.item['id'])
        self.assertEqual(item['summary'],'My words');self.assertEqual(item['summary_source'],'manual')
        self.assertEqual(item['notes'],'Keep notes');self.assertIn('Manual',item['tags'])
        status=self.service.enrichment_get(first['job']['id'])
        self.assertEqual(status['state'],'failed');self.assertEqual(status['error_code'],'manual_summary_conflict')
        self.assertEqual(status['applied_fields'],['tags']);self.assertEqual(status['conflicted_fields'],['summary'])

    def test_tags_only_preserves_summary_and_summary_only_preserves_tags(self):
        self.service.update(self.item['id'],1,{'summary':'Manual summary','add_tags':['Manual']})
        self.item=self.service.get(self.item['id']);first=self.admit(['tags']);job=self.q.claim('worker',now=100)
        self.assertTrue(self.q.complete(job['id'],'worker',{k:v for k,v in RESULT.items() if k!='summary'},token=job['token'],now=101))
        self.assertEqual(self.service.get(self.item['id'])['summary'],'Manual summary')
        self.item=self.service.get(self.item['id']);self.request=str(uuid4());self.admit(['summary']);job=self.q.claim('worker',now=102)
        self.assertTrue(self.q.complete(job['id'],'worker',{k:v for k,v in RESULT.items() if k!='tags'},token=job['token'],now=103))
        item=self.service.get(self.item['id']);self.assertEqual(item['summary'],'Generated');self.assertIn('Generated',item['tags'])

    def test_retention_flag_and_source_clear_preserve_notes_and_imported_source(self):
        cfg=self.service.settings_get();self.service.settings_update(cfg['revision'],{'retain_extracted_text':True})
        self.admit(['summary']);job=self.q.claim('worker',now=100)
        self.q.complete(job['id'],'worker',{k:v for k,v in RESULT.items() if k!='tags'},token=job['token'],now=101,extracted_text='Synthetic retained body')
        item=self.service.get(self.item['id']);self.assertEqual(item['extracted_text'],'Synthetic retained body')
        item=self.service.update(item['id'],item['revision'],{'notes':'Keep'})
        with self.service._storage._transaction(write=True) as c:
            c.execute('INSERT INTO content_sources VALUES(?,?,?,?,?,?)',(item['id'],'source','fixture','row','','Imported text'))
        cleared=self.service.source_clear(item['id'],item['revision'])
        self.assertEqual(cleared['extracted_text'],'');self.assertEqual(cleared['notes'],'Keep')
        self.assertEqual(cleared['imported_sources'][0]['source_text'],'Imported text')
        self.assertEqual(self.service.source_clear(item['id'],cleared['revision'])['revision'],cleared['revision'])

class AdmissionSnapshotTests(RequestTests):
    def test_opt_in_import_uses_start_snapshot_for_all_rows(self):
        from bookmarks.imports.runner import ImportQueue
        cfg=self.service.settings_get()
        self.service.settings_update(cfg['revision'],{'automatic_tags':True,'automatic_summary':True})
        preview=self.service.import_preview(records=[{'url':'https://example.org/import1'},{'url':'https://example.org/import2'}],options={'enrich':True})
        accepted=self.service.import_start(preview['preview_id'],preview['input_digest'],str(uuid4()))
        cfg=self.service.settings_get();self.service.settings_update(cfg['revision'],{'model':'changed','automatic_tags':False,'automatic_summary':False})
        queue=ImportQueue(self.service._storage);claim=queue.claim('importer')
        while queue.step(claim):pass
        rows=self.service.import_job_get(accepted['id'])['rows']
        self.assertEqual(len(rows),2)
        for row in rows:
            saved=self.service.get(row['item_id']);job=self.q.get(saved['enrichment_job_id'])
            self.assertEqual(job['settings']['route']['model'],'synthetic')
            self.assertEqual(job['settings']['fields'],['summary','tags'])

    def test_capture_waiting_for_settings_transaction_gets_one_whole_snapshot(self):
        from bookmarks.settings import persist,read_settings
        service=BookmarkService(self.root,enrichment_settings=ROUTE)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.service._storage._transaction(write=True) as c:
                before=read_settings(c)
                future=pool.submit(service.save_link,'https://example.org/serialized')
                persist(c,{**before['settings'],'model':'serialized','automatic_summary':True,'automatic_tags':False},before['revision']+1)
            saved=future.result(timeout=5)
        snap=self.q.get(saved['enrichment_job_id'])['settings']
        self.assertEqual(snap['route']['model'],'serialized');self.assertEqual(snap['fields'],['summary'])
        self.assertEqual(snap['settings_revision'],before['revision']+1)

if __name__=='__main__':unittest.main()
