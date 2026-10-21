import multiprocessing
from pathlib import Path
import tempfile
import unittest
from bookmarks.assets import AssetStore
from bookmarks.service import BookmarkService
from bookmarks.errors import ConflictError, NotFoundError, ValidationError
from library_fixtures import PNG


def edit_race(root,item_id,barrier,output):
    service=BookmarkService(Path(root)); barrier.wait(timeout=15)
    try: output.put(('ok',service.update(item_id,1,{'notes':'Winner'})['revision']))
    except ConflictError as error: output.put((error.code,error.current_revision))


class ItemUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.service=BookmarkService(self.root)
        self.item=self.service.save_link('https://example.org/item','Original')

    def test_public_update_metadata_move_tags_and_notes_survive_restart(self):
        collection=self.service.collection_create('Reading')
        saved=self.service.update(self.item['id'],1,{'title':'Edited','description':'Descriptionneedle',
            'notes':'# Personalneedle','collection_id':collection['id'],'favorite':True,'read_later':True,'add_tags':[' Manual ','CAFÉ']})
        self.assertEqual(saved['revision'],2)
        self.assertEqual(saved['tag_details'],[{'name':'Manual','source':'manual'},{'name':'CAFÉ','source':'manual'}])
        self.assertEqual(BookmarkService(self.root).get(saved['id']),saved)
        self.assertEqual(self.service.search('Personalneedle',collection_id=collection['id'],tags=['cafe\u0301'])['items'],[saved])
        self.assertEqual(self.service.counts(),{'all':1,'inbox':0,'favorites':1,'read_later':1})

    def test_stale_revision_reports_only_current_revision_without_partial_writes(self):
        saved=self.service.update(self.item['id'],1,{'notes':'Saved private text'})
        with self.assertRaises(ConflictError) as caught:
            self.service.update(saved['id'],1,{'notes':'Losing private text','add_tags':['Lost']})
        self.assertEqual(caught.exception.current_revision,2)
        self.assertNotIn('private',str(caught.exception))
        self.assertEqual(self.service.get(saved['id']),saved)
        self.assertEqual(self.service.tag_list()['total'],0)

    def test_invalid_references_and_unknown_or_source_fields_rollback_all_changes(self):
        for changes in ({'title':'Lost','collection_id':'missing','add_tags':['Lost']},
                        {'title':'Lost','attachment_ids':['a'*32]}, {'url':'https://example.org/replace'},
                        {'kind':'image'},{'primary_asset_id':'a'*32},{'summary':'fake'},{'extra':True}):
            with self.subTest(changes=changes), self.assertRaises((ValidationError,NotFoundError)):
                self.service.update(self.item['id'],1,changes)
            self.assertEqual(self.service.get(self.item['id']),self.item)
        self.assertEqual(self.service.tag_list()['total'],0)

    def test_utf8_byte_limits_nul_surrogates_boolean_and_revision_types(self):
        for changes in ({'notes':'é'*32769},{'description':'é'*8193},{'notes':'a\x00b'},
                        {'title':'x\ud800'},{'favorite':1},{'read_later':'false'},{'add_tags':['x'*81]},
                        {'remove_tags':['']},{'attachment_ids':'a'*32}):
            with self.subTest(changes=str(changes)[:80]), self.assertRaises(ValidationError): self.service.update(self.item['id'],1,changes)
        for revision in (True,0,-1,'1',1.0):
            with self.assertRaises(ValidationError): self.service.update(self.item['id'],revision,{})
        saved=self.service.update(self.item['id'],1,{'notes':'é'*32768,'description':'é'*8192,'favorite':False})
        self.assertEqual(len(saved['notes'].encode('utf-8')),65536)

    def test_notes_replace_append_are_atomic_and_bound_final_text(self):
        saved=self.service.note_update(self.item['id'],1,'First')
        appended=self.service.note_update(saved['id'],saved['revision'],'\nSecond',mode='append')
        self.assertEqual(appended['notes'],'First\nSecond')
        with self.assertRaises(ConflictError): self.service.note_update(saved['id'],1,'Lost',mode='append')
        replaced=self.service.note_update(saved['id'],appended['revision'],'x'*65536)
        with self.assertRaises(ValidationError): self.service.note_update(saved['id'],replaced['revision'],'y',mode='append')
        with self.assertRaises(ValidationError): self.service.note_update(saved['id'],replaced['revision'],'x',mode='merge')
        self.assertEqual(self.service.get(saved['id']),replaced)

    def test_owned_image_associations_restart_unlink_and_shared_bytes(self):
        assets=AssetStore(self.root); asset=assets.store_image(PNG,'image/png')
        saved=self.service.update(self.item['id'],1,{'attachment_ids':[asset['id']]})
        self.assertEqual(saved['attachments'],[{'asset_id':asset['id'],'role':'attachment',**{k:asset[k] for k in ('mime_type','size','width','height')}}])
        other=self.service.capture(url='https://example.org/other',attachment_ids=[asset['id']])['item']
        self.assertEqual(BookmarkService(self.root).get(other['id'])['attachments'],saved['attachments'])
        removed=self.service.update(saved['id'],saved['revision'],{'attachment_ids':[]})
        self.assertEqual(removed['attachments'],[])
        self.assertEqual(len(self.service.get(other['id'])['attachments']),1)
        self.assertTrue(assets.read_asset(asset['id'])[0])
        with self.assertRaises(ValidationError): self.service.update(saved['id'],removed['revision'],{'attachment_ids':['../escape']})

    def test_maximum_ten_images_including_primary_and_noop_form_roundtrip(self):
        from uuid import uuid4
        assets=AssetStore(self.root); ids=[assets.store_image(PNG,'image/png')['id'] for _ in range(11)]
        with self.assertRaises(ValidationError): self.service.capture(kind='image',primary_asset_id=ids[0],attachment_ids=ids[1:],operation_key=str(uuid4()))
        item=self.service.capture(kind='image',primary_asset_id=ids[0],attachment_ids=ids[1:10],operation_key=str(uuid4()))['item']
        unchanged=self.service.update(item['id'],item['revision'],{'title':item['title'],'notes':item['notes'],
            'add_tags':[],'remove_tags':[],'attachment_ids':ids[1:10]})
        self.assertEqual(unchanged,item)
        self.assertEqual([a['role'] for a in unchanged['attachments']],['primary']+['attachment']*9)

    def test_item_child_foreign_keys_cascade_but_assets_are_restricted_and_retained(self):
        from uuid import uuid4
        from bookmarks.errors import StorageError
        assets=AssetStore(self.root); asset=assets.store_image(PNG,'image/png')
        key=str(uuid4())
        image=self.service.capture(kind='image',primary_asset_id=asset['id'],operation_key=key)['item']
        with self.assertRaises(StorageError), self.service._storage._transaction(write=True) as c:
            c.execute('DELETE FROM assets WHERE id=?',(asset['id'],))
        with self.service._storage._transaction(write=True) as c:
            c.execute('DELETE FROM items WHERE id=?',(image['id'],))
        with self.service._storage._transaction() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM item_assets').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM capture_operations').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM assets').fetchone()[0],1)
        self.assertTrue(assets.read_asset(asset['id'])[0])

    def test_tag_overflow_rolls_back_attachments_scalar_edits_and_new_tag_rows(self):
        item=self.service.update(self.item['id'],1,{'add_tags':['Tag'+str(i) for i in range(20)]})
        asset=AssetStore(self.root).store_image(PNG,'image/png')
        with self.assertRaises(ValidationError):
            self.service.update(item['id'],item['revision'],{'title':'Lost','notes':'Lost',
                'attachment_ids':[asset['id']],'add_tags':['Overflow']})
        self.assertEqual(self.service.get(item['id']),item)
        with self.service._storage._transaction() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM tags WHERE identity='overflow'").fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM item_assets').fetchone()[0],0)

    def test_competing_process_revision_writers_have_one_winner(self):
        context=multiprocessing.get_context('spawn'); barrier=context.Barrier(2); output=context.Queue()
        processes=[context.Process(target=edit_race,args=(str(self.root),self.item['id'],barrier,output)) for _ in range(2)]
        try:
            for process in processes: process.start()
            self.assertEqual(sorted(output.get(timeout=20) for _ in processes),[('conflict',2),('ok',2)])
            for process in processes: process.join(10); self.assertEqual(process.exitcode,0)
            self.assertEqual(self.service.get(self.item['id'])['notes'],'Winner')
        finally:
            for process in processes:
                if process.is_alive(): process.terminate()
                process.join(5)
            output.close(); output.join_thread()
