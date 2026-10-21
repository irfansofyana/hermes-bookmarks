import multiprocessing
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from bookmarks.assets import AssetStore
from bookmarks.errors import ConflictError, NotFoundError, ValidationError
from bookmarks.service import BookmarkService
from library_fixtures import PNG


def capture_race(root,asset_id,key,barrier,output):
    service=BookmarkService(Path(root)); barrier.wait(timeout=15)
    try: output.put(('ok',service.capture(kind='image',primary_asset_id=asset_id,notes='Synthetic',operation_key=key)))
    except Exception as error: output.put(('error',type(error).__name__))


def capture_changed_payload(root,key,note,barrier,output):
    service=BookmarkService(Path(root)); barrier.wait(timeout=15)
    try:
        saved=service.capture(url='https://example.org/contended',notes=note,operation_key=key)
        output.put(('ok',saved['item']['id']))
    except ConflictError:
        output.put(('conflict',None))


class CaptureReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.service=BookmarkService(self.root)

    def test_same_operation_payload_defaults_retry_and_read_only_status(self):
        key=str(uuid4())
        saved=self.service.capture(url='https://example.org/receipt',notes='Synthetic',operation_key=key)
        retry=self.service.capture(kind='link',url='https://example.org/receipt',title='',description='',notes='Synthetic',
            collection_id=None,tags=[],favorite=False,read_later=False,primary_asset_id=None,attachment_ids=[],operation_key=key)
        self.assertEqual(retry,saved)
        self.assertEqual(saved['receipt'],{'operation_key':key,'item_id':saved['item']['id'],'accepted_revision':1,'outcome':'created'})
        self.assertEqual(BookmarkService(self.root).capture_status(key),saved)
        self.assertEqual(self.service.search()['total'],1)
        with self.service._storage._transaction() as c:
            operation=dict(c.execute('SELECT * FROM capture_operations').fetchone())
            self.assertEqual(set(operation),{'operation_key','payload_hash','item_id','accepted_revision','outcome'})
            self.assertNotIn('Synthetic',str(operation))
            self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],0)

    def test_reused_key_different_payload_conflicts_and_missing_lookup_does_not_write(self):
        key=str(uuid4()); first=self.service.capture(url='https://example.org/one',operation_key=key)
        with self.assertRaises(ConflictError): self.service.capture(url='https://example.org/one',notes='Different',operation_key=key)
        with self.assertRaises(ConflictError): self.service.capture(url='https://example.org/two',operation_key=key)
        with self.assertRaises(NotFoundError): self.service.capture_status(str(uuid4()))
        self.assertEqual(self.service.get(first['item']['id']),first['item'])
        self.assertEqual(self.service.search()['total'],1)

    def test_duplicate_url_receipt_never_changes_notes_tags_flags_or_associations(self):
        assets=AssetStore(self.root); a=assets.store_image(PNG,'image/png'); b=assets.store_image(PNG,'image/png')
        first=self.service.capture(url='https://example.org/same',notes='Keep',tags=['Manual'],attachment_ids=[a['id']])
        duplicate=self.service.capture(url=first['item']['url'],title='Lost',notes='Lost',tags=['Lost'],favorite=True,
            attachment_ids=[b['id']],operation_key=str(uuid4()))
        self.assertEqual(duplicate['item'],first['item']); self.assertEqual(duplicate['receipt']['outcome'],'duplicate')
        self.assertEqual(self.service.tag_list()['tags'],[{'name':'Manual','count':1}])
        self.assertEqual(self.service.save_link(first['item']['url'],'Lost'),first['item'])
        with self.service._storage._transaction() as c: self.assertEqual(c.execute('SELECT count(*) FROM capture_operations').fetchone()[0],1)

    def test_standalone_image_primary_receipt_retry_and_no_extraction_jobs(self):
        asset=AssetStore(self.root).store_image(PNG,'image/png'); key=str(uuid4())
        service=BookmarkService(self.root,enrichment_settings={})
        saved=service.capture(kind='image',primary_asset_id=asset['id'],title='Image',operation_key=key)
        self.assertEqual(service.capture(kind='image',primary_asset_id=asset['id'],title='Image',operation_key=key),saved)
        item=saved['item']; self.assertIsNone(item['url']); self.assertEqual(item['kind'],'image')
        self.assertEqual(item['primary_asset_id'],asset['id']); self.assertEqual(item['enrichment_status'],'not_configured')
        self.assertEqual(item['attachments'][0]['role'],'primary')
        self.assertEqual(BookmarkService(self.root).get(item['id']),item)
        with service._storage._transaction() as c: self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],0)

    def test_invalid_sources_asset_references_and_operation_keys_never_mutate(self):
        for kwargs in ({'kind':'image'},{'kind':'image','operation_key':str(uuid4()),'primary_asset_id':'a'*32},
                       {'kind':'image','url':'https://example.org','primary_asset_id':'a'*32,'operation_key':str(uuid4())},
                       {'url':'https://example.org','primary_asset_id':'a'*32},{'kind':'video','url':'https://example.org'},
                       {'url':'https://example.org','favorite':1},{'url':'https://example.org','operation_key':'not-a-uuid'},
                       {'url':'https://example.org','operation_key':' '+str(uuid4())}):
            with self.subTest(kwargs=kwargs),self.assertRaises((ValidationError,NotFoundError)): self.service.capture(**kwargs)
        self.assertEqual(self.service.search()['total'],0)

    def test_legacy_duplicate_can_queue_previously_unprocessed_link_without_overwrite(self):
        first=self.service.capture(url='https://example.org/preexisting',notes='Keep',tags=['Manual'])['item']
        configured=BookmarkService(self.root,enrichment_settings={})
        saved=configured.save_link(first['url'],'Do not overwrite')
        self.assertEqual(saved['id'],first['id']); self.assertEqual(saved['notes'],'Keep')
        self.assertEqual(saved['title'],first['title']); self.assertEqual(saved['tags'],['Manual'])
        self.assertEqual(saved['enrichment_status'],'pending')
        with self.service._storage._transaction() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM capture_operations').fetchone()[0],0)

    def test_receipt_keys_are_scoped_to_selected_library(self):
        key=str(uuid4()); first=self.service.capture(url='https://example.org/local',operation_key=key)
        with tempfile.TemporaryDirectory() as directory:
            other=BookmarkService(Path(directory))
            with self.assertRaises(NotFoundError): other.capture_status(key)
            second=other.capture(url='https://example.org/other',operation_key=key)
            self.assertNotEqual(second['item']['id'],first['item']['id'])
        self.assertEqual(self.service.capture_status(key),first)

    def test_competing_same_key_different_payloads_have_one_accepted_receipt(self):
        key=str(uuid4()); context=multiprocessing.get_context('spawn'); barrier=context.Barrier(2); output=context.Queue()
        processes=[context.Process(target=capture_changed_payload,args=(str(self.root),key,note,barrier,output)) for note in ('First','Second')]
        try:
            for process in processes: process.start()
            responses=[output.get(timeout=20) for _ in processes]
            self.assertEqual(sorted(r[0] for r in responses),['conflict','ok'])
            accepted=self.service.capture_status(key)
            self.assertEqual(accepted['item']['id'],next(r[1] for r in responses if r[0]=='ok'))
            self.assertIn(accepted['item']['notes'],('First','Second'))
            self.assertEqual(self.service.search()['total'],1)
            for process in processes: process.join(10); self.assertEqual(process.exitcode,0)
        finally:
            for process in processes:
                if process.is_alive(): process.terminate()
                process.join(5)
            output.close(); output.join_thread()

    def test_competing_image_captures_same_key_create_one_item_receipt(self):
        asset=AssetStore(self.root).store_image(PNG,'image/png'); key=str(uuid4())
        context=multiprocessing.get_context('spawn'); barrier=context.Barrier(2); output=context.Queue()
        processes=[context.Process(target=capture_race,args=(str(self.root),asset['id'],key,barrier,output)) for _ in range(2)]
        try:
            for process in processes: process.start()
            responses=[output.get(timeout=20) for _ in processes]
            self.assertEqual([r[0] for r in responses],['ok','ok'])
            self.assertEqual(responses[0][1],responses[1][1])
            for process in processes: process.join(10); self.assertEqual(process.exitcode,0)
            self.assertEqual(self.service.search()['total'],1)
        finally:
            for process in processes:
                if process.is_alive(): process.terminate()
                process.join(5)
            output.close(); output.join_thread()
