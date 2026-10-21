import multiprocessing
from pathlib import Path
import tempfile
import unittest
from bookmarks.service import BookmarkService
from bookmarks.errors import BookmarkError, NotFoundError, ValidationError


def reciprocal_move(root, source, parent, barrier, output):
    service=BookmarkService(Path(root))
    barrier.wait(timeout=15)
    try:
        service.collection_update(source,1,{'parent_id':parent})
        output.put('ok')
    except BookmarkError as error:
        output.put(error.code)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.service=BookmarkService(self.root)

    def assert_conflict(self, function, *args):
        with self.assertRaises(BookmarkError) as caught: function(*args)
        self.assertEqual(caught.exception.code,'conflict')

    def test_parent_filter_includes_descendants_and_move_rejects_cycle(self):
        parent=self.service.collection_create('Engineering')
        child=self.service.collection_create('AI',parent['id'])
        item=self.service.save_link('https://example.org/a','One')
        with self.service._storage._transaction(write=True) as c:
            c.execute('UPDATE items SET collection_id=? WHERE id=?',(child['id'],item['id']))
        self.assertEqual(self.service.search('',collection_id=parent['id'])['total'],1)
        self.assert_conflict(self.service.collection_update,parent['id'],1,{'parent_id':child['id']})
        page=self.service.collection_list()
        self.assertEqual((page['total'],page['collections'][0]['count']),(1,1))
        self.assertEqual(page['collections'][0]['path'],[{'id':parent['id'],'name':'Engineering'}])
        self.assertEqual(BookmarkService(self.root).collection_list(parent_id=parent['id'])['collections'][0]['id'],child['id'])

    def test_nfc_casefold_siblings_root_uniqueness_and_name_bounds(self):
        first=self.service.collection_create('  Café  ')
        self.assertEqual(first['name'],'Café')
        self.assert_conflict(self.service.collection_create,'CAFE\u0301')
        self.assertEqual(self.service.collection_create('CAFÉ',first['id'])['parent_id'],first['id'])
        for name in ('','  ','x'*101,'a\x00b','a\ud800'):
            with self.subTest(name=repr(name)), self.assertRaises(ValidationError): self.service.collection_create(name)

    def test_subtree_depth_is_validated_before_move(self):
        chain=[]
        for index in range(16):
            chain.append(self.service.collection_create(str(index),chain[-1]['id'] if chain else None))
        self.assert_conflict(self.service.collection_create,'too deep',chain[-1]['id'])
        branch=self.service.collection_create('branch'); leaf=self.service.collection_create('leaf',branch['id'])
        self.assert_conflict(self.service.collection_update,branch['id'],1,{'parent_id':chain[-2]['id']})
        self.assertEqual(self.service.collection_list(parent_id=branch['id'])['collections'][0]['id'],leaf['id'])

    def test_revision_and_unknown_identifiers_fail_without_partial_rename(self):
        item=self.service.collection_create('Before')
        saved=self.service.collection_update(item['id'],1,{'name':'After'})
        self.assertEqual(saved['revision'],2)
        self.assert_conflict(self.service.collection_update,item['id'],1,{'name':'Lost'})
        self.assert_conflict(self.service.collection_delete,item['id'],1,'move_to_parent')
        for method,args in ((self.service.collection_update,('missing',1,{'name':'x'})),(self.service.collection_delete,('missing',1,'move_to_inbox')),(self.service.collection_create,('x','missing'))):
            with self.assertRaises(NotFoundError): method(*args)
        for changes in ({'url':'bad'},{'parent_id':True},{'name':None}):
            with self.assertRaises(ValidationError): self.service.collection_update(item['id'],2,changes)
        self.assertEqual(self.service.collection_list()['collections'][0]['name'],'After')

    def test_delete_preserves_items_children_and_increments_affected_revisions(self):
        parent=self.service.collection_create('Parent'); folder=self.service.collection_create('Folder',parent['id'])
        child=self.service.collection_create('Child',folder['id'])
        item=self.service.save_link('https://example.org/delete')
        with self.service._storage._transaction(write=True) as c: c.execute('UPDATE items SET collection_id=? WHERE id=?',(folder['id'],item['id']))
        self.assertEqual(self.service.collection_delete(folder['id'],1,'move_to_parent'),{'deleted_id':folder['id']})
        moved=self.service.get(item['id'])
        self.assertEqual((moved['collection_id'],moved['revision']),(parent['id'],2))
        moved_child=self.service.collection_list(parent_id=parent['id'])['collections'][0]
        self.assertEqual((moved_child['id'],moved_child['revision']),(child['id'],2))
        self.service.collection_delete(parent['id'],1,'move_to_inbox')
        self.assertIsNone(self.service.get(item['id'])['collection_id'])
        self.assertIsNone(self.service.collection_list()['collections'][0]['parent_id'])

    def test_delete_preflights_all_collisions_and_rolls_back(self):
        folder=self.service.collection_create('Folder'); self.service.collection_create('Same')
        child=self.service.collection_create('same',folder['id'])
        item=self.service.save_link('https://example.org/keep')
        with self.service._storage._transaction(write=True) as c: c.execute('UPDATE items SET collection_id=? WHERE id=?',(folder['id'],item['id']))
        self.assert_conflict(self.service.collection_delete,folder['id'],1,'move_to_inbox')
        self.assertEqual(self.service.get(item['id'])['collection_id'],folder['id'])
        self.assertEqual(self.service.collection_list(parent_id=folder['id'])['collections'][0]['id'],child['id'])
        with self.assertRaises(ValidationError): self.service.collection_delete(folder['id'],1,'recursive')

    def test_paged_paths_and_counts_ignore_item_text_search(self):
        root=self.service.collection_create('Root')
        for index in range(53): self.service.collection_create('Match '+str(index),root['id'])
        first=self.service.collection_list(limit=50,query='match'); rest=self.service.collection_list(limit=50,offset=50,query='MATCH')
        self.assertEqual((first['total'],len(first['collections']),len(rest['collections'])),(53,50,3))
        self.assertEqual(rest['collections'][0]['path'][0],{'id':root['id'],'name':'Root'})
        self.assertEqual(self.service.collection_list(offset=10**100)['collections'],[])

    def test_reciprocal_cross_process_moves_cannot_create_cycle(self):
        a=self.service.collection_create('A'); b=self.service.collection_create('B')
        context=multiprocessing.get_context('spawn'); output=context.Queue(); barrier=context.Barrier(2)
        processes=[context.Process(target=reciprocal_move,args=(str(self.root),s,p,barrier,output)) for s,p in ((a['id'],b['id']),(b['id'],a['id']))]
        try:
            for process in processes: process.start()
            self.assertEqual(sorted(output.get(timeout=20) for _ in processes),['conflict','ok'])
            for process in processes: process.join(10); self.assertEqual(process.exitcode,0)
            self.assertEqual(self.service.collection_list()['total'],1)
        finally:
            for process in processes:
                if process.is_alive(): process.terminate()
                process.join(5)
            output.close(); output.join_thread()
