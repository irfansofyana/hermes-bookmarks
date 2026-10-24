"""Lossless content boundaries, exercised against synthetic service writers."""
from contextlib import closing
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from bookmarks.errors import ConflictError, ValidationError, StorageError
from bookmarks.service import BookmarkService
from library_fixtures import frozen_v5, PNG


class PortableContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = BookmarkService(self.root / 'source')
        self.target = BookmarkService(self.root / 'target')

    def content(self, service=None, version=2):
        from bookmarks.portability.content import snapshot
        with (service or self.source)._storage._transaction() as c:
            return snapshot(c, version=version)

    def restore(self, data, service=None, version=2):
        from bookmarks.portability.content import restore_content
        with (service or self.target)._storage._transaction(write=True) as c:
            restore_content(c, data, version=version)

    def fixture(self):
        s = self.source
        folder = s.collection_create('空の Café')
        nested = s.collection_create('Nested', folder['id'])
        s.collection_create('Empty')
        with s._storage._transaction(write=True) as c:
            for key in ('a'*32, 'b'*32):
                c.execute('INSERT INTO assets VALUES(?,?,?,?,?)', (key, 'image/png', len(PNG), 1, 1))
        item = s.capture(url='https://example.org/日本?q=1', title='Unicode 🌍', notes='Note\n'*1000,
                         description='Description', tags=['Manual'], favorite=True, read_later=True,
                         collection_id=nested['id'], attachment_ids=['a'*32])['item']
        from bookmarks.tags import merge_generated
        with s._storage._transaction(write=True) as c:
            merge_generated(c, item['id'], ['Generated', 'Suppressed'])
            c.execute('UPDATE items SET summary=?,revision=17 WHERE id=?', ('Saved summary', item['id']))
        item = s.update(item['id'], 17, {'remove_tags':['Suppressed']})
        s.capture(kind='image', primary_asset_id='a'*32, operation_key=str(uuid4()), title='Image')
        trash = s.save_link('https://example.org/trash', 'Trash')
        s.trash(trash['id'], trash['revision'])
        p = s.import_preview(records=[{'url':'https://example.org/import', 'source_id':'original-42',
            'source_text':'独立 source needle', 'imported_summary':'Imported summary',
            'provenance':{'source':'Fixture', 'locator':'row42'}}])
        s.import_start(p['preview_id'], p['input_digest'], str(uuid4()))
        from bookmarks.imports.runner import ImportQueue
        q = ImportQueue(s._storage)
        claim = q.claim('fixture')
        while q.step(claim):
            pass
        return item

    def test_service_content_roundtrip_exact_rows_search_and_identity(self):
        from bookmarks.portability.content import validate_content, empty
        item = self.fixture()
        before = self.content()
        self.assertEqual(set(before), {'items','collections','tags','item_tags','item_assets','assets','sources','settings'})
        self.assertEqual([len(before[k]) for k in ('items','collections','assets','sources')], [4,3,2,1])
        self.assertEqual(before['sources'][0]['source_id'], 'original-42')
        self.assertNotIn('enrichment_job_id', before['items'][0])
        self.assertNotIn('enrichment_generation', before['items'][0])
        validate_content(before)
        identity = self.target.identity()
        self.restore(before)
        self.assertEqual(self.content(self.target), before)
        self.assertEqual(self.target.identity(), identity)
        self.assertNotEqual(identity, self.source.identity())
        self.assertEqual(self.target.get(item['id']), self.source.get(item['id']))
        self.assertEqual(self.target.search('独立 source needle')['total'], 1)
        self.assertEqual(self.target.counts()['trash'], 1)
        with self.target._storage._transaction() as c:
            self.assertFalse(empty(c))
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            for table in ('jobs','import_jobs','capture_operations','chat_threads'):
                self.assertEqual(c.execute('SELECT count(*) FROM '+table).fetchone()[0], 0)

    def test_pending_running_restored_inert_with_history_and_route_intent(self):
        from bookmarks.jobs import JobQueue
        route = {'provider':'fixture','model':'fixture-model','owner_profile':'fixture-owner'}
        JobQueue(self.root/'source').configure_route(route)
        pending = BookmarkService(self.root/'source', enrichment_settings=route).save_link('https://example.org/pending')
        running = BookmarkService(self.root/'source', enrichment_settings=route).save_link('https://example.org/running')
        with self.source._storage._transaction(write=True) as c:
            c.execute("UPDATE items SET enrichment_status='running',processing_history=? WHERE id=?", ('["failed"]',running['id']))
            c.execute("INSERT INTO library_config VALUES('secret_fixture','DO NOT COPY')")
        data = self.content(version=1)
        self.assertEqual(data['settings'], {'enrichment_route':route})
        self.assertNotIn('DO NOT COPY', json.dumps(data))
        self.restore(data, version=1)
        for key, history in [(pending['id'], ['pending']), (running['id'], ['failed','running'])]:
            item = self.target.get(key)
            self.assertEqual(item['enrichment_status'], 'needs_review')
            self.assertIsNone(item['enrichment_job_id'])
            self.assertEqual(json.loads(item['processing_history']), history)
        with self.target._storage._transaction() as c:
            self.assertIsNone(c.execute("SELECT value FROM library_config WHERE key='enrichment_route'").fetchone())
            self.assertEqual(json.loads(c.execute("SELECT value FROM library_config WHERE key='restored_enrichment_route'").fetchone()[0]),route)
        self.assertEqual(self.content(self.target, version=1)['settings'], data['settings'])
        from bookmarks.portability.content import validate_content
        validate_content(self.content(self.target, version=1), version=1)

    def test_empty_target_final_recheck_and_caller_rollback(self):
        from bookmarks.portability.content import restore_content, empty
        self.fixture()
        data = self.content()
        with self.target._storage._transaction() as c:
            self.assertTrue(empty(c))
        concurrent = self.target.save_link('https://example.org/concurrent')
        with self.assertRaises(ConflictError):
            self.restore(data)
        self.assertEqual(self.target.search()['items'], [concurrent])
        clean = BookmarkService(self.root/'rollback')
        with self.assertRaisesRegex(RuntimeError, 'caller rollback'):
            with clean._storage._transaction(write=True) as c:
                restore_content(c, data)
                self.assertTrue(c.in_transaction)
                raise RuntimeError('caller rollback')
        with clean._storage._transaction() as c:
            self.assertTrue(empty(c))
        self.restore(data, clean)
        self.assertEqual(self.content(clean), data)

    def test_empty_content_and_any_content_table_blocks_restore(self):
        from bookmarks.portability.content import empty
        data = self.content()
        self.restore(data)
        self.assertEqual(self.content(self.target), data)
        self.target.collection_create('Empty but content')
        with self.target._storage._transaction() as c:
            self.assertFalse(empty(c))
        with self.assertRaises(ConflictError):
            self.restore(data)
        with self.source._storage._transaction(write=True) as c:
            c.execute('INSERT INTO assets VALUES(?,?,?,?,?)', ('a'*32,'image/png',10,1,1))
            self.assertFalse(empty(c))

    def test_legacy_aliases_raw_cache_and_membership_spelling_survive(self):
        from bookmarks.portability.content import validate_content
        for i, aliases in enumerate((['AI','ai'],['Café','Cafe\u0301'],['reading',' reading '])):
            root = self.root/('legacy'+str(i)); root.mkdir()
            frozen_v5(root, tags=json.dumps(aliases, ensure_ascii=False))
            legacy = BookmarkService(root)
            data = self.content(legacy)
            validate_content(data)
            self.assertEqual(data['items'][0]['rowid'], 42)
            self.assertEqual(json.loads(data['items'][0]['tags']), aliases)
            target = BookmarkService(self.root/('alias-target'+str(i)))
            self.restore(data, target)
            self.assertEqual(target.get('legacy')['tags'], aliases)
            self.assertEqual(target.get('legacy')['tag_details'], [{'name':aliases[0],'source':'generated'}])
            self.assertEqual(target.search(tags=[aliases[-1]])['total'], 1)

    def test_restore_collection_parent_may_have_later_rowid(self):
        child = self.source.collection_create('Same')
        parent = self.source.collection_create('Other')
        self.source.collection_update(child['id'],1,{'parent_id':parent['id']})
        self.source.collection_update(parent['id'],1,{'name':'Same'})
        data = self.content()
        self.restore(data)
        self.assertEqual(self.content(self.target), data)

    def test_source_projection_survives_removal_of_operational_history(self):
        self.fixture()
        with self.source._storage._transaction(write=True) as c:
            c.execute('DELETE FROM import_provenance')
            c.execute('DELETE FROM import_results')
            c.execute('DELETE FROM import_jobs')
            c.execute('DELETE FROM import_previews')
        item = self.source.search('独立 source needle')['items'][0]
        self.assertEqual(item['imported_sources'][0]['source_id'], 'original-42')
        self.assertEqual(len(self.content()['sources']),1)

    def test_migration_eight_backfills_ordered_sources_and_is_atomic(self):
        from bookmarks.migrations import MIGRATIONS, migrate
        from bookmarks.portability.schema import upgrade_content
        self.assertEqual(MIGRATIONS[8], (upgrade_content,))
        c = sqlite3.connect(':memory:', isolation_level=None)
        self.addCleanup(c.close); c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON'); c.execute('BEGIN')
        for migration in MIGRATIONS[:8]:
            for step in migration:
                step(c) if callable(step) else c.execute(step)
        c.execute('PRAGMA user_version=8')
        c.execute("INSERT INTO items(id,url,title) VALUES('legacy','https://example.org/legacy','Legacy')")
        c.execute("INSERT INTO import_previews VALUES('p','d','{}','{}','{}',1,2)")
        c.execute("INSERT INTO import_jobs(id,preview_id,request_id,digest,total,created_at) VALUES('j','p','r','d',2,1)")
        for n in (7,19):
            c.execute('INSERT INTO import_provenance(rowid,item_id,job_id,row_index,source_id,source,locator,imported_summary,source_text) VALUES(?,?,?,?,?,?,?,?,?)',
                      (n,'legacy','j',n,str(n),'Source','row'+str(n),'Summary','Needle '+str(n)))
        c.commit(); c.execute('BEGIN'); upgrade_content(c); c.rollback()
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='content_sources'").fetchone())
        self.assertNotIn('processing_history', [r['name'] for r in c.execute('PRAGMA table_info(items)')])
        c.execute('BEGIN'); migrate(c); c.commit()
        self.assertEqual([tuple(r) for r in c.execute('SELECT rowid,source_id,source_text FROM content_sources ORDER BY rowid')],
                         [(7,'7','Needle 7'),(19,'19','Needle 19')])
        self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_validation_rejects_unknown_fields_types_references_and_invariants(self):
        from bookmarks.portability.content import validate_content
        self.fixture()
        original = self.content()
        cases = [
            lambda d: d.update(unknown=[]),
            lambda d: d['items'][0].update(secret='x'),
            lambda d: d['items'][0].pop('title'),
            lambda d: d['items'][0].update(revision=True),
            lambda d: d['items'][0].update(rowid=0),
            lambda d: d['items'][0].update(favorite=2),
            lambda d: d['items'][0].update(created_at=float('nan')),
            lambda d: d['items'][0].update(notes='\ud800'),
            lambda d: d['items'][0].update(collection_id='missing'),
            lambda d: d['items'][0].update(tags='[1]'),
            lambda d: d['items'][0].update(processing_history='{}'),
            lambda d: d['collections'][0].update(parent_id=d['collections'][1]['id']),
            lambda d: d['tags'][0].update(identity='wrong'),
            lambda d: d['item_tags'][0].update(tag_id='missing'),
            lambda d: d['item_tags'][0].update(label='wrong'),
            lambda d: d['item_assets'][0].update(asset_id='missing'),
            lambda d: d['item_assets'][0].update(role='executable'),
            lambda d: d['assets'][0].update(id='../unsafe'),
            lambda d: d['assets'][0].update(width=-1),
            lambda d: d['assets'][0].update(size=10*1024*1024+1),
            lambda d: d['sources'][0].update(item_id='missing'),
            lambda d: d['settings'].update(enrichment_route={'api_key':'secret'}),
            lambda d: d['items'].append(copy.deepcopy(d['items'][0])),
            lambda d: d['items'].reverse(),
        ]
        for mutate in cases:
            with self.subTest(case=cases.index(mutate)):
                data = copy.deepcopy(original); mutate(data)
                with self.assertRaises(ValidationError):
                    validate_content(data)
                with self.assertRaises(ValidationError):
                    self.restore(data)
                self.assertEqual(self.content(self.target)['items'], [])

    def test_validation_limits_and_primary_asset_graph(self):
        from bookmarks.portability.content import validate_content
        self.fixture(); data = self.content()
        for mutate in (
            lambda d: d.update(items=d['items']*2501),
            lambda d: d['assets'][0].update(width=20_000_001),
            lambda d: d['items'][0].update(notes='a'*65537),
            lambda d: d['sources'][0].update(source_text='a'*30001),
            lambda d: d['item_assets'].pop(1),
            lambda d: d['items'][0].update(processing_history='["unknown"]'),
        ):
            bad = copy.deepcopy(data); mutate(bad)
            with self.assertRaises(ValidationError):
                validate_content(bad)

    def test_legacy_url_is_preserved_as_data_not_revalidated_as_new_capture(self):
        self.source.save_link('https://example.org/old')
        with self.source._storage._transaction(write=True) as c:
            c.execute("UPDATE items SET url='javascript:legacy'")
        data = self.content()
        self.restore(data)
        self.assertEqual(self.target.search()['items'][0]['url'], 'javascript:legacy')

    def test_legacy_unbounded_title_remains_portable(self):
        root = self.root/'long-title'; root.mkdir()
        frozen_v5(root)
        title = 'Historically accepted title ' * 100
        with closing(sqlite3.connect(root/'bookmarks.sqlite3')) as c, c:
            c.execute('UPDATE items SET title=?', (title,))
        legacy = BookmarkService(root)
        data = self.content(legacy)
        self.restore(data)
        self.assertEqual(self.target.get('legacy')['title'], title)

    def test_snapshot_is_consistent_across_concurrent_content_commit(self):
        from bookmarks.portability.content import snapshot
        item = self.source.capture(url='https://example.org/concurrent', tags=['Before'])['item']
        with closing(sqlite3.connect(self.source._storage.database_path)) as c:
            c.execute('PRAGMA journal_mode=WAL')
        with self.source._storage._transaction() as reader:
            before = snapshot(reader)
            self.source.update(item['id'], item['revision'], {'notes':'After', 'add_tags':['After']})
            self.assertEqual(snapshot(reader), before)
        after = self.content()
        self.assertEqual(after['items'][0]['notes'], 'After')
        self.assertEqual(json.loads(after['items'][0]['tags']), ['Before','After'])

    def test_every_row_field_rejects_container_types_and_unknown_fields(self):
        from bookmarks.portability.content import validate_content
        self.fixture(); original = self.content()
        for table in ('items','collections','tags','item_tags','item_assets','assets','sources'):
            for field in original[table][0]:
                with self.subTest(table=table, field=field):
                    data = copy.deepcopy(original); data[table][0][field] = []
                    with self.assertRaises(ValidationError):
                        validate_content(data)
            data = copy.deepcopy(original); data[table][0]['unknown'] = 'must not drop'
            with self.assertRaises(ValidationError):
                validate_content(data)

    def test_all_table_and_json_quotas_fail_without_truncation(self):
        from bookmarks.portability.content import validate_content, MAX_JSON_BYTES
        self.fixture(); original = self.content()
        for table, maximum in (('items',10000),('collections',10000),('tags',20000),
                               ('item_tags',200000),('item_assets',100000),('assets',10000),('sources',200000)):
            with self.subTest(table=table):
                data = copy.deepcopy(original); data[table] = [original[table][0]] * (maximum+1)
                with self.assertRaises(ValidationError):
                    validate_content(data)
        data = copy.deepcopy(original); data['items'][0]['title'] = 'a'*MAX_JSON_BYTES
        with self.assertRaises(ValidationError):
            validate_content(data)

    def test_excessive_depth_associations_and_invalid_cache_graph_are_refused(self):
        from bookmarks.portability.content import validate_content
        self.fixture(); original = self.content()
        data = copy.deepcopy(original)
        first = data['collections'][0]
        for index in range(3,19):
            data['collections'].append({**first, 'rowid':index+1, 'id':'depth'+str(index),
                'name':'Depth'+str(index), 'identity':'depth'+str(index),
                'parent_id':data['collections'][-1]['id']})
        with self.assertRaises(ValidationError):
            validate_content(data)
        data = copy.deepcopy(original)
        for index in range(10):
            asset_id = format(index,'032x')
            data['assets'].append({**data['assets'][0], 'rowid':index+3, 'id':asset_id})
            data['item_assets'].append({'rowid':index+3,'item_id':data['items'][0]['id'],
                'asset_id':asset_id,'role':'attachment'})
        with self.assertRaises(ValidationError):
            validate_content(data)
        data = copy.deepcopy(original); data['items'][0]['tags']='["not a membership"]'
        with self.assertRaises(ValidationError):
            validate_content(data)

    def test_restore_requires_caller_transaction_without_partial_autocommits(self):
        from bookmarks.portability.content import restore_content
        data = self.content()
        with closing(sqlite3.connect(self.target._storage.database_path, isolation_level=None)) as c:
            c.row_factory = sqlite3.Row
            with self.assertRaises(ValidationError):
                restore_content(c, data)
            self.assertFalse(c.in_transaction)

    def test_statement_failure_can_be_caught_without_losing_outer_transaction(self):
        from bookmarks.portability.content import restore_content, empty
        self.fixture(); data = self.content()
        with self.target._storage._transaction(write=True) as c:
            c.execute("INSERT INTO library_config VALUES('caller_marker','kept')")
            c.execute("CREATE TRIGGER reject_source BEFORE INSERT ON content_sources BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                restore_content(c, data)
            self.assertTrue(c.in_transaction)
            self.assertTrue(empty(c))
        with self.target._storage._transaction() as c:
            self.assertEqual(c.execute("SELECT value FROM library_config WHERE key='caller_marker'").fetchone()[0], 'kept')

    def test_content_insert_failure_leaves_no_partial_rows(self):
        from bookmarks.portability.content import empty
        self.fixture(); data = self.content()
        with self.target._storage._transaction(write=True) as c:
            c.execute("CREATE TRIGGER reject_restored_source BEFORE INSERT ON content_sources BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(StorageError):
            self.restore(data)
        with self.target._storage._transaction() as c:
            self.assertTrue(empty(c))
