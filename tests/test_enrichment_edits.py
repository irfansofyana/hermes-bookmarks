from pathlib import Path
import tempfile
import unittest
from bookmarks.service import BookmarkService
from bookmarks.jobs import JobQueue
from bookmarks.errors import ValidationError
from library_fixtures import frozen_v5

SETTINGS={'provider':'fixture','model':'fixture','owner_profile':'fixture'}
RESULT={'summary':'Saved summary','tags':['AI','Reading'],'provider':'fixture','model':'fixture','coverage':'extracted_text'}


class EnrichmentEditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.service=BookmarkService(self.root)
        self.item=self.service.save_link('https://example.org/queued','Original'); self.queue=JobQueue(self.root)

    def test_late_result_merges_without_clobbering_manual_content(self):
        job=self.queue.enqueue(self.item['id'],1,SETTINGS); lease=self.queue.claim('worker',100,30)
        saved=self.service.update(self.item['id'],1,{'title':'Manual title','description':'Manual description',
            'notes':'My private note','add_tags':['Manual'],'remove_tags':['AI'],'favorite':True})
        self.assertTrue(self.queue.complete(job,'worker',RESULT,token=lease['token'],now=110))
        got=self.service.get(self.item['id'])
        for field in ('title','description','notes','favorite'): self.assertEqual(got[field],saved[field])
        self.assertEqual(got['tags'],['Manual','Reading']); self.assertEqual(got['enrichment_status'],'succeeded')
        self.assertEqual(got['revision'],3); self.assertEqual(got['summary'],'Saved summary')
        self.assertEqual(got['tag_details'],[{'name':'Manual','source':'manual'},{'name':'Reading','source':'generated'}])
        self.assertEqual(self.service.search('Reading',tags=['Manual'])['items'],[got])
        self.assertEqual(self.service.tag_list()['tags'],[{'name':'Manual','count':1},{'name':'Reading','count':1}])

    def test_noop_form_does_not_promote_generated_tags_and_explicit_removal_persists(self):
        job=self.queue.enqueue(self.item['id'],1,SETTINGS); lease=self.queue.claim('worker',100,30)
        self.queue.complete(job,'worker',RESULT,token=lease['token'],now=110)
        item=self.service.get(self.item['id'])
        saved=self.service.update(item['id'],item['revision'],{'title':item['title'],'notes':item['notes'],'add_tags':[],'remove_tags':[]})
        self.assertEqual(saved,item)
        removed=self.service.update(item['id'],item['revision'],{'remove_tags':[' ai ']})
        job=self.queue.enqueue(item['id'],removed['revision'],SETTINGS); lease=self.queue.claim('worker',200,30)
        self.assertTrue(self.queue.complete(job,'worker',RESULT,token=lease['token'],now=210))
        self.assertEqual(self.service.get(item['id'])['tags'],['Reading'])

    def test_new_generation_fences_old_complete_fail_cancel_and_recovery(self):
        for action in ('complete','fail','cancel','recover_expired'):
            with self.subTest(action=action):
                item=self.service.save_link('https://example.org/'+action)
                old=self.queue.enqueue(item['id'],1,SETTINGS); lease=self.queue.claim('worker',100,30)
                edited=self.service.update(item['id'],1,{'notes':'Keep'})
                new=self.queue.enqueue(item['id'],edited['revision'],SETTINGS)
                before=self.service.get(item['id'])
                if action=='complete': self.assertFalse(self.queue.complete(old,'worker',RESULT,token=lease['token'],now=110))
                elif action=='fail': self.assertFalse(self.queue.fail(old,'worker','provider_failed',token=lease['token'],now=110))
                elif action=='cancel': self.queue.cancel(old)
                else: self.queue.recover_expired(131)
                self.assertEqual(self.service.get(item['id']),before)
                self.assertEqual(before['enrichment_job_id'],new)
                # Retire this case's new job so next case claims its own job.
                self.queue.cancel(new)

    def test_exact_active_job_identity_is_required_even_when_generation_matches(self):
        for action in ('complete','fail','cancel','recover_expired'):
            with self.subTest(action=action):
                item=self.service.save_link('https://example.org/identity/'+action)
                job=self.queue.enqueue(item['id'],1,SETTINGS); claim=self.queue.claim('worker',100,30)
                with self.service._storage._transaction(write=True) as c:
                    c.execute("UPDATE items SET enrichment_job_id='replacement',enrichment_status='pending' WHERE id=?",(item['id'],))
                before=self.service.get(item['id'])
                if action=='complete': self.assertFalse(self.queue.complete(job,'worker',RESULT,token=claim['token'],now=110))
                elif action=='fail': self.assertFalse(self.queue.fail(job,'worker','provider_failed',token=claim['token'],now=110))
                elif action=='cancel': self.queue.cancel(job)
                else: self.queue.recover_expired(131)
                self.assertEqual(self.service.get(item['id']),before)
                self.queue.cancel(job)

    def test_enqueue_reuse_does_not_resurrect_cancelled_or_superseded_job(self):
        job=self.queue.enqueue(self.item['id'],1,SETTINGS)
        self.queue.cancel(job)
        self.assertEqual(self.queue.enqueue(self.item['id'],1,SETTINGS),job)
        self.assertEqual(self.service.get(self.item['id'])['enrichment_status'],'cancelled')
        with self.assertRaises(ValueError): self.queue.enqueue(self.item['id'],1,{**SETTINGS,'model':'other'})

    def test_manual_tags_win_bound_generated_search_and_counts_agree(self):
        item=self.service.update(self.item['id'],1,{'add_tags':['Manual'+str(i) for i in range(19)]})
        job=self.queue.enqueue(item['id'],item['revision'],SETTINGS); lease=self.queue.claim('worker',100,30)
        result={**RESULT,'tags':['G'+str(i) for i in range(20)]}
        self.assertTrue(self.queue.complete(job,'worker',result,token=lease['token'],now=110))
        got=self.service.get(item['id']); self.assertEqual(len(got['tags']),20)
        self.assertEqual(got['tags'][-1],'G0'); self.assertEqual(self.service.tag_list()['total'],20)
        self.assertEqual(self.service.search('',tags=['G1'])['total'],0)
        with self.assertRaises(ValidationError): self.service.update(item['id'],got['revision'],{'add_tags':['Overflow','Overflow2']})

    def test_manual_display_spelling_is_retained_over_same_identity_suggestions(self):
        saved=self.service.update(self.item['id'],1,{'add_tags':['ai']})
        job=self.queue.enqueue(saved['id'],saved['revision'],SETTINGS); lease=self.queue.claim('worker',100,30)
        self.assertTrue(self.queue.complete(job,'worker',RESULT,token=lease['token'],now=110))
        got=self.service.get(saved['id'])
        self.assertEqual(got['tags'],['ai','Reading'])
        self.assertEqual(got['tag_details'][0],{'name':'ai','source':'manual'})

    def test_image_queue_admission_is_explicitly_unavailable(self):
        from uuid import uuid4
        from bookmarks.assets import AssetStore
        from library_fixtures import PNG
        asset=AssetStore(self.root).store_image(PNG,'image/png')
        image=self.service.capture(kind='image',primary_asset_id=asset['id'],operation_key=str(uuid4()))['item']
        with self.assertRaises(ValueError): self.queue.enqueue(image['id'],image['revision'],SETTINGS)
        self.assertEqual(self.service.get(image['id']),image)

    def test_migration_does_not_revive_stale_revision_snapshot_or_cancelled_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); frozen_v5(root)
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(root/'bookmarks.sqlite3')) as c,c:
                c.execute('UPDATE items SET revision=8')
            service=BookmarkService(root); queue=JobQueue(root)
            lease=queue.claim('worker',100,30)
            self.assertFalse(queue.complete(lease['id'],'worker',RESULT,token=lease['token'],now=110))
            self.assertEqual(service.get('legacy')['revision'],8)
            self.assertEqual(queue.get('cancelled-job')['state'],'cancelled')
