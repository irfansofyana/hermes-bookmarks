from pathlib import Path
import tempfile
import unittest
from bookmarks.service import BookmarkService
from bookmarks.jobs import JobQueue
from bookmarks.errors import ValidationError, NotFoundError


class LibraryQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.service=BookmarkService(self.root)
        self.queue=JobQueue(self.root)

    def generated(self,item,tags):
        job=self.queue.enqueue(item['id'],item['revision'],{'provider':'fixture','model':'fixture','owner_profile':'fixture'})
        claim=self.queue.claim('fixture',100,30)
        self.assertEqual(claim['id'],job)
        self.assertTrue(self.queue.complete(job,'fixture',{'summary':'Summaryneedle','tags':tags,'provider':'fixture','model':'fixture','coverage':'extracted_text'},token=claim['token'],now=110))

    def test_queue_tags_cache_discovery_search_and_provenance_agree(self):
        item=self.service.save_link('https://example.org/generated')
        self.generated(item,['AI','Reading'])
        got=self.service.get(item['id'])
        self.assertEqual(got['tags'],['AI','Reading'])
        self.assertEqual(got['tag_details'],[{'name':'AI','source':'generated'},{'name':'Reading','source':'generated'}])
        self.assertEqual(self.service.tag_list()['tags'],[{'name':'AI','count':1},{'name':'Reading','count':1}])
        self.assertEqual(self.service.search('Reading',tags=['ai'])['items'],[got])
        self.assertEqual(self.service.search('Summaryneedle')['total'],1)

    def test_search_view_descendants_and_tags_are_and_predicates(self):
        parent=self.service.collection_create('Parent'); child=self.service.collection_create('Child',parent['id'])
        for index in range(4):
            item=self.service.save_link('https://example.org/'+str(index),'Needle' if index!=2 else 'Other')
            self.generated(item,['AI','Reading'] if index!=1 else ['AI'])
            with self.service._storage._transaction(write=True) as c:
                c.execute('UPDATE items SET favorite=?,read_later=?,collection_id=?,notes=?,description=? WHERE id=?',
                    (index!=3,index==3,child['id'] if index<3 else None,'Personalneedle','Descriptionneedle',item['id']))
        page=self.service.search('Needle',view='favorites',collection_id=parent['id'],tags=[' ai ','READING'])
        self.assertEqual(page['total'],1)
        self.assertEqual(page['items'][0]['url'],'https://example.org/0')
        self.assertEqual(self.service.counts(),{'all':4,'inbox':1,'favorites':3,'read_later':1})
        self.assertEqual(self.service.search('Personalneedle')['total'],4)
        self.assertEqual(self.service.search('Descriptionneedle')['total'],4)
        self.assertEqual(self.service.search('',view='inbox')['total'],1)
        self.assertEqual(self.service.search('',view='read_later')['total'],1)
        self.assertEqual(self.service.collection_list()['collections'][0]['count'],3)
        self.assertEqual(self.service.search('',tags=['unknown'])['total'],0)

    def test_item_and_tag_pages_reach_beyond_fifty_with_stable_restart(self):
        for index in range(57):
            self.generated(self.service.save_link('https://example.org/page/'+str(index),'Alpha OR Beta'),['Tag'+str(index)])
        first=self.service.search('',limit=50); last=BookmarkService(self.root).search('',limit=50,offset=50)
        self.assertEqual((first['total'],last['total'],len(last['items'])),(57,57,7))
        self.assertEqual(len({item['id'] for item in first['items']+last['items']}),57)
        tags=self.service.tag_list(); rest=self.service.tag_list(offset=50)
        self.assertEqual((tags['total'],len(tags['tags']),len(rest['tags'])),(57,50,7))
        self.assertEqual(self.service.tag_list(query='tag5')['total'],8)
        self.assertEqual(self.service.search('Alpha OR Beta')['total'],57)
        self.assertEqual(self.service.search('title:Alpha')['total'],0)
        self.assertEqual(self.service.search('',offset=10**100)['items'],[])
        self.assertEqual(self.service.tag_list(offset=10**100)['tags'],[])

    def test_empty_reads_are_library_scoped_and_never_enqueue(self):
        identity=self.service.identity()
        self.assertEqual(set(identity),{'library_id'})
        self.assertEqual(BookmarkService(self.root).identity(),identity)
        self.assertEqual(self.service.counts(),{'all':0,'inbox':0,'favorites':0,'read_later':0})
        self.service.search(); self.service.tag_list(); self.service.collection_list()
        with self.service._storage._transaction() as c: self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
        with tempfile.TemporaryDirectory() as other: self.assertNotEqual(BookmarkService(Path(other)).identity(),identity)

    def test_invalid_filter_types_and_unknown_collection_are_rejected(self):
        for kwargs in ({'view':'trash'},{'view':False},{'tags':'AI'},{'tags':['']},{'collection_id':False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError): self.service.search('',**kwargs)
        with self.assertRaises(NotFoundError): self.service.search('',collection_id='missing')
        for method in (self.service.tag_list,self.service.collection_list):
            with self.assertRaises(ValidationError): method(limit=True)
