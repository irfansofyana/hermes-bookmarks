from contextlib import closing
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from bookmarks.errors import StorageError
from bookmarks.service import BookmarkService
from library_fixtures import frozen_v5, PNG


def upgrade(root, output):
    try:
        service=BookmarkService(Path(root))
        output.put(('ok',service.get('legacy')['id']))
    except Exception as error:
        output.put(('error',type(error).__name__))


class LibraryMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        frozen_v5(self.root)

    def test_populated_upgrade_preserves_ids_sources_and_related_state(self):
        service=BookmarkService(self.root)
        item=service.get('legacy')
        self.assertEqual(item['kind'],'link')
        self.assertEqual((item['revision'],item['tags'],item['summary']),(7,['AI','Reading'],'Saved summary'))
        self.assertEqual(item['tag_details'],[{'name':'AI','source':'generated'},{'name':'Reading','source':'generated'}])
        self.assertEqual((item['notes'],item['description'],item['collection_id'],item['primary_asset_id']),('','',None,None))
        self.assertIs(item['favorite'],False); self.assertIs(item['read_later'],False)
        with service._storage._transaction() as c:
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],6)
            self.assertEqual(c.execute('SELECT rowid,enrichment_generation FROM items').fetchone()[:],(42,7))
            self.assertEqual(c.execute("SELECT generation,token,expires FROM jobs WHERE id='pending-job'").fetchone()[:],(7,'old-token',123.0))
            self.assertEqual(c.execute("SELECT state,generation FROM jobs WHERE id='cancelled-job'").fetchone()[:],('cancelled',6))
            self.assertEqual(c.execute("SELECT value FROM library_config WHERE key='library_id'").fetchone()[0],'1'*32)
            self.assertEqual(c.execute('SELECT session_id FROM chat_threads').fetchone()[0],'session')
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual((self.root/'assets'/('a'*32+'.blob')).read_bytes(),PNG)
        self.assertEqual(service.search('Saved summary')['total'],1)
        self.assertEqual(service.search('AI')['total'],1)
        self.assertEqual(service.search('title:Legacy')['total'],0)

    def test_invalid_legacy_tags_rollback_every_ddl(self):
        for tags in ('not-json','{}','[3]','["bad\\u0000tag"]','["AI","ai"]'):
            with self.subTest(tags=tags):
                with closing(sqlite3.connect(self.root/'bookmarks.sqlite3')) as c, c:
                    c.execute('UPDATE items SET tags=?',(tags,))
                with self.assertRaises(StorageError): BookmarkService(self.root)
                with closing(sqlite3.connect(self.root/'bookmarks.sqlite3')) as c:
                    self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],5)
                    self.assertEqual(c.execute('SELECT rowid,tags FROM items').fetchone(),(42,tags))
                    self.assertEqual(c.execute("SELECT name FROM sqlite_master WHERE name='collections'").fetchall(),[])

    def test_failed_ddl_rolls_back_replacement(self):
        with closing(sqlite3.connect(self.root/'bookmarks.sqlite3')) as c, c:
            c.execute('CREATE TABLE item_tags(marker TEXT)')
        with self.assertRaises(StorageError): BookmarkService(self.root)
        with closing(sqlite3.connect(self.root/'bookmarks.sqlite3')) as c:
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],5)
            self.assertEqual(c.execute('SELECT rowid,url FROM items').fetchone(),(42,'https://example.org/legacy'))
            self.assertEqual(c.execute("SELECT count(*) FROM items_fts WHERE items_fts MATCH 'Legacy'").fetchone()[0],1)

    def test_legacy_per_item_spelling_survives_shared_normalized_identity(self):
        with closing(sqlite3.connect(self.root/'bookmarks.sqlite3')) as c,c:
            c.execute("INSERT INTO items(id,url,title,tags) VALUES('other','https://example.org/other','Other',?)", ('["ai","Cafe\\u0301"]',))
        service=BookmarkService(self.root)
        got=service.get('other')
        self.assertEqual(got['tags'],['ai','Cafe\u0301'])
        self.assertEqual([tag['name'] for tag in got['tag_details']],['ai','Cafe\u0301'])
        saved=service.update('other',1,{'notes':'Retain original tag spelling'})
        self.assertEqual(saved['tags'],['ai','Cafe\u0301'])
        self.assertEqual(service.tag_list(query='AI')['tags'],[{'name':'AI','count':2}])

    def test_foreign_keys_on_every_fresh_connection(self):
        service=BookmarkService(self.root)
        for _ in range(2):
            with service._storage._transaction() as c:
                self.assertEqual(c.execute('PRAGMA foreign_keys').fetchone()[0],1)
            with self.assertRaises(StorageError), service._storage._transaction(write=True) as c:
                c.execute("UPDATE items SET collection_id='missing'")
        self.assertIsNone(service.get('legacy')['collection_id'])

    def test_populated_concurrent_migrators(self):
        context=multiprocessing.get_context('spawn'); output=context.Queue()
        processes=[context.Process(target=upgrade,args=(str(self.root),output)) for _ in range(3)]
        try:
            for process in processes: process.start()
            results=[output.get(timeout=20) for _ in processes]
            self.assertEqual(results,[('ok','legacy')]*3)
            for process in processes:
                process.join(10); self.assertEqual(process.exitcode,0)
            self.assertEqual(BookmarkService(self.root).search('')['total'],1)
        finally:
            for process in processes:
                if process.is_alive(): process.terminate()
                process.join(5)
            output.close(); output.join_thread()
