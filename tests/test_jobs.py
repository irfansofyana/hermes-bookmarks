import tempfile
from pathlib import Path
import unittest
from bookmarks.service import BookmarkService
from bookmarks.jobs import JobQueue

def claim_in_process(root, worker, output):
    output.put(JobQueue(Path(root)).claim(worker,100,30))


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.service=BookmarkService(self.root)
        self.item=self.service.save_link('https://example.org','Example')
        self.q=JobQueue(self.root)
        self.settings={'provider':'fixture','model':'fixture-model','owner_profile':'fixture'}
        self.result={'summary':'Synthetic summary','tags':['example'],'provider':'fixture','model':'fixture-model','coverage':'extracted_text'}
    def enqueue(self): return self.q.enqueue(self.item['id'],1,self.settings)
    def test_live_claim_exclusive_across_instances_and_idempotent_enqueue(self):
        job=self.enqueue(); self.assertEqual(self.enqueue(),job)
        a=self.q.claim('a',100,30)
        self.assertEqual(a['id'],job)
        self.assertIsNone(JobQueue(self.root).claim('b',110,30))
    def test_expired_claim_has_new_fence_even_for_same_worker_name(self):
        self.enqueue(); a=self.q.claim('a',100,30)
        self.assertEqual(self.q.recover_expired(131),1)
        b=self.q.claim('a',132,30)
        self.assertNotEqual(a['token'],b['token'])
        self.assertFalse(self.q.complete(a['id'],'a',self.result,token=a['token'],now=133))
        self.assertTrue(self.q.complete(b['id'],'a',self.result,token=b['token'],now=133))
        self.assertEqual(self.service.get(self.item['id'])['summary'],'Synthetic summary')
    def test_completion_rejects_expired_lease_without_recovery(self):
        self.enqueue(); a=self.q.claim('a',100,30)
        self.assertFalse(self.q.complete(a['id'],'a',self.result,token=a['token'],now=130))
    def assert_lock_wait_does_not_extend_lease(self,operation):
        from concurrent.futures import ThreadPoolExecutor
        from contextlib import closing, contextmanager
        from threading import Event
        from unittest.mock import patch
        import sqlite3
        job=self.enqueue(); claim=self.q.claim('worker',100,1)
        clock=[100.0]; attempted=Event()
        transaction=self.q.storage._transaction
        @contextmanager
        def watched(*,write=False):
            attempted.set()
            with transaction(write=write) as connection: yield connection
        with closing(sqlite3.connect(self.q.storage.database_path,isolation_level=None)) as blocker:
            blocker.execute('BEGIN IMMEDIATE')
            with patch('bookmarks.jobs.time.time',side_effect=lambda:clock[0]), patch.object(self.q.storage,'_transaction',watched), ThreadPoolExecutor(max_workers=1) as pool:
                value=self.result if operation=='complete' else 'provider_failed'
                future=pool.submit(getattr(self.q,operation),job,'worker',value,token=claim['token'])
                try:
                    self.assertTrue(attempted.wait(2),'Mutation did not reach the held SQLite lock')
                    clock[0]=102.0
                finally: blocker.commit()
                applied=future.result(timeout=3)
        self.assertFalse(applied,'Expired claim mutated storage after lock acquisition')
        self.assertEqual(self.q.get(job)['state'],'running')
        self.assertEqual(self.service.get(self.item['id'])['summary'],'')

    def test_completion_rechecks_production_clock_after_write_lock(self):
        self.assert_lock_wait_does_not_extend_lease('complete')

    def test_failure_rechecks_production_clock_after_write_lock(self):
        self.assert_lock_wait_does_not_extend_lease('fail')

    def test_restart_recovers_pending_and_completion_only_once(self):
        job=self.enqueue(); q=JobQueue(self.root); a=q.claim('a',100,30)
        self.assertTrue(q.complete(job,'a',self.result,token=a['token'],now=110))
        self.assertFalse(q.complete(job,'a',self.result,token=a['token'],now=111))
        self.assertEqual(self.service.get(self.item['id'])['revision'],2)
    def test_manual_metadata_edit_survives_valid_completion(self):
        self.enqueue(); a=self.q.claim('a',100,30)
        self.service.update(self.item['id'],1,{'title':'Manual','notes':'Keep'})
        self.assertTrue(self.q.complete(a['id'],'a',self.result,token=a['token'],now=110))
        got=self.service.get(self.item['id'])
        self.assertEqual(got['summary'],'Synthetic summary')
        self.assertEqual(got['title'],'Manual')
        self.assertEqual(got['notes'],'Keep')
    def test_cancel_prevents_late_apply(self):
        job=self.enqueue(); a=self.q.claim('a',100,30); self.q.cancel(job)
        self.assertFalse(self.q.complete(job,'a',self.result,token=a['token'],now=110))
        self.assertEqual(self.q.get(job)['state'],'cancelled')
    def test_retry_is_bounded_and_reports_failure(self):
        job=self.enqueue()
        for i in range(3):
            a=self.q.claim('a',100+i,30)
            self.q.fail(job,'a','provider_failed',token=a['token'],now=101+i)
        self.assertEqual(self.q.get(job)['state'],'failed')
        self.assertIsNone(self.q.claim('b',110,30))
    def test_library_route_cannot_follow_a_different_profile_silently(self):
        self.q.configure_route(self.settings)
        with self.assertRaises(ValueError):
            self.q.configure_route({**self.settings,'model':'different-chat-model'})
        self.assertEqual(JobQueue(self.root).route(),self.settings)

    def test_cross_process_claim_is_exclusive(self):
        import multiprocessing
        job=self.enqueue(); context=multiprocessing.get_context('spawn')
        output=context.Queue()
        workers=[context.Process(target=claim_in_process,args=(str(self.root),str(i),output)) for i in range(2)]
        for p in workers: p.start()
        try:
            results=[output.get(timeout=15) for _ in workers]
            self.assertEqual(sum(r is not None for r in results),1)
            self.assertEqual(next(r['id'] for r in results if r),job)
        finally:
            for p in workers:
                p.join(15)
                if p.is_alive(): p.terminate(); p.join()
            output.close(); output.join_thread()

    def test_secret_or_unknown_settings_are_rejected(self):
        with self.assertRaises(ValueError): self.q.enqueue(self.item['id'],1,{'api_key':'secret'})

if __name__=='__main__': unittest.main()
