"""Recoverable deletion with real SQLite, no file/model side effects."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from bookmarks.service import BookmarkService
from bookmarks.errors import ConflictError
from bookmarks.jobs import JobQueue
from bookmarks.assets import AssetStore

class TrashTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.service=BookmarkService(self.root)
    def test_trash_restore_revision_counts_and_noop(self):
        s=self.service
        c=s.collection_create('Engineering')
        item=s.capture(url='https://example.org/a',notes='Keep **notes**',tags=['systems'],collection_id=c['id'],favorite=True,read_later=True)['item']
        trashed=s.trash(item['id'],item['revision'])
        self.assertIsNotNone(trashed['deleted_at'])
        self.assertEqual(s.search()['total'],0)
        self.assertEqual(s.search(view='trash')['items'][0]['notes'],'Keep **notes**')
        self.assertEqual(s.counts(),{'all':0,'inbox':0,'favorites':0,'read_later':0,'trash':1})
        self.assertEqual(s.tag_list()['total'],0)
        self.assertEqual(s.collection_list()['collections'][0]['count'],0)
        self.assertEqual(s.trash(item['id'],trashed['revision']),trashed)
        with self.assertRaises(ConflictError):s.restore(item['id'],item['revision'])
        with self.assertRaises(ConflictError):s.update(item['id'],trashed['revision'],{'notes':'hidden edit'})
        restored=s.restore(item['id'],trashed['revision'])
        self.assertIsNone(restored['deleted_at']);self.assertEqual(restored['notes'],item['notes'])
        self.assertEqual(s.search()['total'],1);self.assertEqual(s.tag_list()['total'],1)
    def test_trash_fences_late_enrichment_and_restore_does_not_requeue(self):
        s=self.service;item=s.save_link('https://example.org/job');q=JobQueue(self.root)
        jid=q.enqueue(item['id'],item['revision'],{'provider':'fixture','model':'never-called'})
        claim=q.claim('worker')
        trashed=s.trash(item['id'],s.get(item['id'])['revision'])
        result={'summary':'Must not apply','tags':['late'],'provider':'fixture','model':'fake','coverage':'extracted_text'}
        self.assertFalse(q.complete(jid,'worker',result,token=claim['token']))
        self.assertEqual(q.get(jid)['state'],'cancelled')
        restored=s.restore(item['id'],trashed['revision'])
        self.assertEqual(restored['summary'],'');self.assertEqual(restored['tags'],[])
        self.assertIsNone(q.claim('other'))
        with self.assertRaises(ValueError):q.enqueue(item['id'],trashed['revision'],{})
    def test_trashed_duplicate_returns_explicit_receipt_without_restoring(self):
        s=self.service;item=s.save_link('https://example.org/duplicate')
        trashed=s.trash(item['id'],item['revision'])
        key=str(uuid4());result=s.capture(url=item['url'],notes='Never overwrite',operation_key=key)
        self.assertEqual(result['receipt']['outcome'],'trashed_duplicate')
        self.assertEqual(result['item'],trashed)
        self.assertEqual(s.capture_status(key),result)
    def test_image_assets_survive_trash_and_collection_move(self):
        s=self.service;c=s.collection_create('Images')
        raw=(Path(__file__).parent/'fixtures/tiny.png').read_bytes()
        asset=AssetStore(self.root).store_image(raw,'image/png')
        item=s.capture(kind='image',primary_asset_id=asset['id'],operation_key=str(uuid4()),collection_id=c['id'])['item']
        trashed=s.trash(item['id'],item['revision'])
        s.collection_delete(c['id'],c['revision'],'move_to_inbox')
        current=s.get(item['id']);restored=s.restore(item['id'],current['revision'])
        self.assertEqual(restored['primary_asset_id'],asset['id']);self.assertIsNone(restored['collection_id'])
        self.assertEqual(AssetStore(self.root).read_asset(asset['id'])[1],'image/png')
