import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from bookmarks.service import BookmarkService

class ImportRunnerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.s=BookmarkService(self.root)
 def admit(self,records,options=None):
  p=self.s.import_preview(records=records,options=options);return self.s.import_start(p['preview_id'],p['input_digest'],str(uuid4()))['id']
 def queue(self):
  from bookmarks.imports.runner import ImportQueue
  return ImportQueue(self.s._storage)
 def drive(self,q,claim):
  while q.step(claim):pass
 def test_counts_provenance_paths_and_no_default_inference(self):
  jid=self.admit([{'url':'https://example.org/a','title':'A','notes':'Keep','tags':['Systems'],'collection_path':['Engineering','Backend'],'source_id':'42','imported_summary':'Imported claim','source_text':'Imported source','provenance':{'source':'Selected list','locator':'row42'}},{'url':'https://example.org/a'},{'url':'javascript:bad'}])
  q=self.queue();claim=q.claim('a');self.drive(q,claim)
  report=self.s.import_job_get(jid);self.assertEqual(report['state'],'succeeded')
  self.assertEqual([report[k] for k in ['total','processed','remaining','imported','skipped','failed']],[3,3,0,1,1,1])
  item=self.s.search()['items'][0];self.assertEqual(item['notes'],'Keep');self.assertEqual(item['summary'],'')
  self.assertEqual(item['tags'],['Systems']);self.assertEqual(item['imported_sources'][0]['imported_summary'],'Imported claim')
  self.assertEqual(self.s.search('Imported source')['total'],1)
  with self.s._storage._transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
 def test_manual_edit_or_trash_after_preview_is_never_overwritten(self):
  jid=self.admit([{'url':'https://example.org/a','notes':'Imported'}])
  item=self.s.save_link('https://example.org/a');edited=self.s.update(item['id'],item['revision'],{'notes':'Manual'})
  trashed=self.s.trash(item['id'],edited['revision'])
  q=self.queue();self.drive(q,q.claim('worker'))
  self.assertEqual(self.s.import_job_get(jid)['skipped'],1);self.assertEqual(self.s.get(item['id']),trashed)
 def test_stale_claim_crash_resume_and_repeated_step_cannot_duplicate(self):
  jid=self.admit([{'url':'https://example.org/a'},{'url':'https://example.org/b'}]);q=self.queue()
  old=q.claim('old',now=100,lease_seconds=1)
  self.assertTrue(q.step(old,now=100.5))
  q.recover_expired(now=222);new=q.claim('new',now=222)
  self.assertFalse(q.step(old,now=222));self.assertTrue(q.step(new,now=222.5));self.assertFalse(q.step(new,now=222.6))
  report=self.s.import_job_get(jid);self.assertEqual((report['imported'],report['remaining']),(2,0));self.assertEqual(self.s.search()['total'],2)
 def test_cancel_after_one_commit_keeps_exact_partial_report(self):
  jid=self.admit([{'url':'https://example.org/a'},{'url':'https://example.org/b'}]);q=self.queue();claim=q.claim('a')
  self.assertTrue(q.step(claim));result=self.s.import_job_cancel(jid)
  self.assertEqual((result['imported'],result['remaining'],result['state']),(1,1,'cancelled'))
  self.assertFalse(q.step(claim));self.assertIsNone(q.claim('b'));self.assertEqual(self.s.search()['total'],1)
 def test_process_death_after_committed_row_resumes_disk_library_without_duplicate(self):
  import subprocess,sys
  jid=self.admit([{'url':'https://example.org/crash-a'},{'url':'https://example.org/crash-b'}])
  code="""import os,sys
from pathlib import Path
from bookmarks.service import BookmarkService
from bookmarks.imports.runner import ImportQueue
q=ImportQueue(BookmarkService(Path(sys.argv[1]))._storage)
claim=q.claim('crashed-process',now=100)
assert q.step(claim,now=100.1)
os._exit(17)
"""
  result=subprocess.run([sys.executable,'-B','-c',code,str(self.root)],timeout=15,cwd=Path(__file__).parents[1])
  self.assertEqual(result.returncode,17);self.assertEqual(self.s.import_job_get(jid)['processed'],1)
  q=self.queue();q.recover_expired(now=300)
  claim=q.claim('replacement',now=300);self.assertIsNotNone(claim)
  self.assertTrue(q.step(claim,now=301));self.assertFalse(q.step(claim,now=302))
  report=self.s.import_job_get(jid);self.assertEqual((report['imported'],report['remaining']),(2,0))
  self.assertEqual(len(set(row['item_id'] for row in report['rows'])),2)

 def test_two_workers_commit_each_row_once(self):
  jid=self.admit([{'url':f'https://example.org/{n}'} for n in range(12)])
  def run(name):
   from bookmarks.imports.runner import ImportQueue
   q=ImportQueue(BookmarkService(self.root)._storage);claim=q.claim(name)
   if claim:self.drive(q,claim)
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,['a','b']))
  r=self.s.import_job_get(jid);self.assertEqual(r['imported'],12);self.assertEqual(len(r['rows']),12)
 def test_result_failure_rolls_back_item_collection_and_cursor_together(self):
  jid=self.admit([{'url':'https://example.org/a','collection_path':['Must rollback']}]);q=self.queue();claim=q.claim('a')
  with self.s._storage._transaction(write=True) as c:c.execute("CREATE TRIGGER reject_import_result BEFORE INSERT ON import_results BEGIN SELECT RAISE(ABORT,'private'); END")
  from bookmarks.errors import StorageError
  with self.assertRaises(StorageError):q.step(claim)
  self.assertEqual(self.s.search()['total'],0);self.assertEqual(self.s.collection_list()['total'],0);self.assertEqual(self.s.import_job_get(jid)['processed'],0)
 def test_explicit_enrichment_queues_only_new_links(self):
  from bookmarks.jobs import JobQueue
  q=JobQueue(self.root);q.configure_route({'provider':'fixture','model':'pinned','owner_profile':'default'})
  jid=self.admit([{'url':'https://example.org/a'},{'url':'https://example.org/a'}],{'enrich':True})
  importer=self.queue();self.drive(importer,importer.claim('a'))
  self.assertEqual(self.s.import_job_get(jid)['imported'],1)
  with self.s._storage._transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
