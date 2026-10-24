"""Pinned old-writer fixture: 85161559263424c4bb4e0ecc66309a78043733ca."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest
from bookmarks.service import BookmarkService


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'bookmarks.sqlite3'
        import shutil
        shutil.copyfile(Path(__file__).parent/'fixtures/enrichment-v10.sqlite3', self.db)
        with closing(sqlite3.connect(self.db)) as c:
            self.before = [dict(zip([v[0] for v in c.execute('SELECT rowid,* FROM jobs').description], row)) for row in c.execute('SELECT rowid,* FROM jobs ORDER BY rowid')]

    def test_real_old_jobs_preserve_all_fields_and_summary_protection(self):
        service = BookmarkService(self.root)
        with service._storage._transaction() as c:
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 11)
            after = [dict(row) for row in c.execute('SELECT rowid,* FROM jobs ORDER BY rowid')]
            self.assertEqual([{k:row[k] for k in old} for row,old in zip(after,self.before)], self.before)
            self.assertEqual(len(after), len(self.before))
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            legacy = c.execute("SELECT * FROM items WHERE summary!=''").fetchone()
            self.assertEqual(legacy['summary_source'], 'legacy')
            self.assertEqual(legacy['summary_revision'], 0)
        self.assertEqual(service.settings_get()['settings']['model'], 'old-model')

    def test_two_independent_migrators_preserve_schema_and_content(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            services = list(pool.map(lambda _: BookmarkService(self.root), range(2)))
        self.assertEqual(services[0].settings_get(), services[1].settings_get())
        self.assertEqual(services[0].search()['total'], 4)

    def test_failed_upgrade_rolls_back_every_statement(self):
        from bookmarks.enrichment_schema import upgrade_enrichment
        from bookmarks.migrations import migrate
        from unittest.mock import patch
        from bookmarks import migrations
        def fail(c):
            upgrade_enrichment(c)
            raise RuntimeError('synthetic migration failure')
        with closing(sqlite3.connect(self.db,isolation_level=None)) as c:
            c.row_factory=sqlite3.Row
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('BEGIN IMMEDIATE')
            with patch.object(migrations,'MIGRATIONS',migrations.MIGRATIONS[:-1]+((fail,),)):
                with self.assertRaisesRegex(RuntimeError,'synthetic migration failure'): migrate(c)
            c.rollback()
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],10)
            self.assertNotIn('summary_source',[r[1] for r in c.execute('PRAGMA table_info(items)')])
            self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],len(self.before))

if __name__ == '__main__': unittest.main()
