import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bookmarks.errors import ConflictError, ValidationError
from bookmarks.service import BookmarkService


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = BookmarkService(self.root)

    def store(self):
        from bookmarks.settings import SettingsStore
        return SettingsStore(self.service._storage)

    def test_defaults_are_nonsecret_and_get_is_read_only(self):
        store = self.store()
        with self.service._storage._transaction() as c:
            before = list(map(tuple, c.execute('SELECT * FROM library_config ORDER BY key')))
        first = store.get()
        self.assertEqual(first['revision'], 1)
        self.assertFalse(first['route_ready'])
        self.assertTrue(first['settings']['automatic_tags'])
        self.assertTrue(first['settings']['automatic_summary'])
        self.assertFalse(first['settings']['image_analysis'])
        self.assertFalse(first['settings']['retain_extracted_text'])
        self.assertEqual(store.get(), first)
        with self.service._storage._transaction() as c:
            self.assertEqual(list(map(tuple, c.execute('SELECT * FROM library_config ORDER BY key'))), before)

    def test_settings_survive_new_instances_and_stale_bootstrap(self):
        store = self.store()
        store.seed_route({'provider':'fixture','model':'old','owner_profile':'owner'})
        before = store.get()
        after = store.update(before['revision'], {'model':'new','image_analysis':True})
        store.seed_route({'provider':'fixture','model':'old','owner_profile':'owner'})
        from bookmarks.settings import SettingsStore
        self.assertEqual(SettingsStore(BookmarkService(self.root)._storage).get(), after)
        self.assertEqual(after['settings']['owner_profile'], 'owner')
        with self.assertRaises(ConflictError):
            store.update(before['revision'], {'model':'third'})
        with self.assertRaises(ConflictError):
            store.seed_route({'provider':'fixture','model':'other','owner_profile':'foreign'})

    def test_unknown_fields_credentials_and_wrong_types_are_rejected_atomically(self):
        store = self.store()
        before = store.get()
        bad = [{'owner_profile':'other'}, {'api_key':'x'}, {'url':'https://example.org'},
               {'paused':1}, {'image_analysis':'true'}, {'provider':'  '}, {'model':'https://example.org'},
               {'model':'test\x00'}, {'model':'\ud800'}, {'summary_language':''}, {'summary_length':'huge'},
               {'guidance':'a'*2001}, {'preferred_tags':['a']*21}, {'automatic_tags':None}]
        for changes in bad:
            with self.subTest(changes=repr(changes)):
                with self.assertRaises(ValidationError): store.update(before['revision'], changes)
                self.assertEqual(store.get(), before)
        for revision in (True, 0, -1, 2**63, '1'):
            with self.assertRaises(ValidationError): store.update(revision, {})

    def test_noop_does_not_increase_revision_and_stale_noop_conflicts(self):
        store = self.store()
        first = store.get()
        self.assertEqual(store.update(1, {}), first)
        second = store.update(1, {'summary_language':'Indonesian','preferred_tags':['Café','CAFÉ']})
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['settings']['preferred_tags'], ['CAFÉ'])
        self.assertEqual(store.update(2, {'summary_language':'Indonesian'}), second)
        with self.assertRaises(ConflictError): store.update(1, {})

    def test_owner_seed_after_ui_save_cannot_overwrite_edited_options(self):
        store = self.store()
        after = store.update(1, {'model':'chosen','provider':'fixture','paused':True})
        store.seed_route({'provider':'fixture','model':'bootstrap','owner_profile':'owner'})
        got = store.get()
        self.assertEqual(got['settings']['model'], 'chosen')
        self.assertTrue(got['settings']['paused'])
        self.assertEqual(got['settings']['owner_profile'], 'owner')
        self.assertGreater(got['revision'], after['revision'])

    def test_competing_expected_revision_saves_have_exactly_one_winner(self):
        def save(value):
            from bookmarks.settings import SettingsStore
            try:
                return SettingsStore(BookmarkService(self.root)._storage).update(1, {'model':value})['settings']['model']
            except ConflictError:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save, ['one','two']))
        self.assertEqual(outcomes.count('conflict'), 1)
        self.assertEqual(self.store().get()['revision'], 2)

    def test_full_replacement_retires_both_inert_keys_even_when_options_match(self):
        store=self.store();before=store.get()
        with self.service._storage._transaction(write=True) as c:
            c.execute("INSERT INTO library_config VALUES('restored_enrichment_settings',?)",(json.dumps(before['settings']),))
            c.execute("INSERT INTO library_config VALUES('restored_enrichment_route',?)",(json.dumps({'provider':'fixture','model':'old','owner_profile':'foreign'}),))
        self.assertIsNotNone(store.get()['restored_intent'])
        # Partial edits and bootstrap are not approval to replace imported intent.
        partial=store.update(before['revision'],{'paused':True})
        self.assertIsNotNone(partial['restored_intent'])
        full={key:value for key,value in partial['settings'].items() if key!='owner_profile'}
        after=store.update(partial['revision'],full)
        self.assertIsNone(after['restored_intent'])
        self.assertEqual(after['revision'],partial['revision']+1)
        with self.service._storage._transaction() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM library_config WHERE key LIKE 'restored_enrichment_%'").fetchone()[0],0)
        self.assertEqual(store.update(after['revision'],full),after)

    def test_live_legacy_route_can_seed_but_restored_route_cannot(self):
        from bookmarks.settings import read_settings
        with self.service._storage._transaction(write=True) as c:
            c.execute("INSERT OR REPLACE INTO library_config VALUES('restored_enrichment_route',?)", (json.dumps({'provider':'fixture','model':'restored','owner_profile':'other'}),))
            self.assertFalse(read_settings(c)['route_ready'])

if __name__ == '__main__': unittest.main()
