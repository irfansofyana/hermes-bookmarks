"""Immutable bounded staging and admission, real SQLite, no source/network I/O."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from bookmarks.service import BookmarkService
from bookmarks.errors import ValidationError,ConflictError,NotFoundError,ConfigurationError

class ImportPreviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.s=BookmarkService(self.root)
 def test_preview_counts_warnings_and_no_domain_writes(self):
  self.s.save_link('https://example.org/existing')
  p=self.s.import_preview(records=[{'url':'https://example.org/a?x=1','title':'東京','tags':['AI'],'collection_path':['Engineering','Backend'],'unknown':'not preserved'}, {'url':'https://example.org/a?x=1'}, {'url':'https://example.org/existing'}, {'url':'javascript:bad'}, {'url':'https://example.org/a?x=2'}])
  self.assertEqual([p[k] for k in ['total','valid','invalid','duplicate_in_batch','existing']],[5,2,1,1,1])
  self.assertIn('unsupported_field:unknown',p['rows'][0]['warnings'])
  self.assertEqual(p['options'],{'duplicate_policy':'skip_existing','enrich':False})
  self.assertEqual(self.s.search()['total'],1);self.assertEqual(self.s.collection_list()['total'],0);self.assertEqual(self.s.tag_list()['total'],0)
 def test_limits_invalid_top_level_and_owned_asset_validation(self):
  for records in [[],{},[{}]*501,[{'url':'https://example.org','notes':'x'*(2*1024*1024)}]]:
   with self.subTest(kind=type(records)),self.assertRaises(ValidationError):self.s.import_preview(records=records)
  for options in [{'enrich':'yes'},{'duplicate_policy':'overwrite'},{'secret':'no'}]:
   with self.assertRaises(ValidationError):self.s.import_preview(records=[{'url':'https://example.org'}],options=options)
  p=self.s.import_preview(records=[{'url':'https://example.org','attachment_ids':['a'*32]}])
  self.assertEqual(p['invalid'],1);self.assertEqual(p['rows'][0]['error_code'],'not_found')
 def test_start_is_idempotent_payload_bound_and_readonly_request_lookup(self):
  p=self.s.import_preview(records=[{'url':'https://example.org/a','notes':'Keep'}]);rid=str(uuid4())
  with self.assertRaises(NotFoundError):self.s.import_request_get(rid)
  job=self.s.import_start(p['preview_id'],p['input_digest'],rid)
  self.assertEqual(self.s.import_start(p['preview_id'],p['input_digest'],rid)['id'],job['id'])
  self.assertEqual(self.s.import_request_get(rid)['id'],job['id'])
  with self.assertRaises(ConflictError):self.s.import_start(p['preview_id'],'0'*64,rid)
  self.assertEqual(self.s.search()['total'],0)
  self.assertEqual(job['remaining'],1)
 def test_expired_preview_cannot_start_but_accepted_retry_survives_expiry(self):
  p=self.s.import_preview(records=[{'url':'https://example.org/a'}]);rid=str(uuid4())
  job=self.s.import_start(p['preview_id'],p['input_digest'],rid)
  with patch('bookmarks.imports.preview.time.time',return_value=p['expires_at']+1):
   with self.assertRaises(ConflictError):self.s.import_start(p['preview_id'],p['input_digest'],str(uuid4()))
   self.assertEqual(self.s.import_start(p['preview_id'],p['input_digest'],rid)['id'],job['id'])
 def test_two_starts_return_same_job_and_cancel_reports_remaining(self):
  p=self.s.import_preview(records=[{'url':'https://example.org/a'}]);rid=str(uuid4())
  def start(_):return BookmarkService(self.root).import_start(p['preview_id'],p['input_digest'],rid)['id']
  with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(start,range(2)))
  self.assertEqual(ids[0],ids[1]);result=self.s.import_job_cancel(ids[0])
  self.assertEqual((result['state'],result['processed'],result['remaining']),('cancelled',0,1))
 def test_opt_in_enrichment_requires_complete_route_and_snapshots_it(self):
  p=self.s.import_preview(records=[{'url':'https://example.org/a'}],options={'enrich':True})
  with self.assertRaises(ConfigurationError):self.s.import_start(p['preview_id'],p['input_digest'],str(uuid4()))
  from bookmarks.jobs import JobQueue
  q=JobQueue(self.root);q.configure_route({'provider':'fixture','model':'pinned','owner_profile':'default'})
  j=self.s.import_start(p['preview_id'],p['input_digest'],str(uuid4()))
  with q.storage._transaction() as c:self.assertIn('pinned',c.execute('SELECT settings FROM import_jobs WHERE id=?',(j['id'],)).fetchone()[0])
