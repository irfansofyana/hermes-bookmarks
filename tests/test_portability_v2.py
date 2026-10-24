"""Synthetic strict-version/full-fidelity regressions; no provider or host calls."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4
import zipfile

from bookmarks.errors import ConflictError, StorageError, ValidationError
from bookmarks.portability import archive
from bookmarks.portability.content import snapshot, validate_content, restore_content
from bookmarks.portability.store import PortabilityStore
from bookmarks.service import BookmarkService
from bookmarks.settings import SettingsStore
from test_portable_archive import empty_data, raw_bundle

FIXTURES = Path(__file__).parent / 'fixtures'
PINNED_WRITER = '85161559263424c4bb4e0ecc66309a78043733ca'
NEW_FIELDS = {'summary_source', 'summary_revision', 'extracted_text', 'generated_provenance'}
SOURCE_SETTINGS = {
    'provider': 'synthetic-provider', 'model': 'synthetic-source-model',
    'owner_profile': 'synthetic-source-owner',
    'automatic_tags': False, 'automatic_summary': True, 'image_analysis': True,
    'summary_language': 'Indonesian', 'summary_length': 'long',
    'preferred_tags': ['Synthetic', 'Café'], 'guidance': 'Synthetic guidance only.',
    'retain_extracted_text': True, 'paused': True,
}
TARGET_SETTINGS = {
    **SOURCE_SETTINGS, 'model': 'synthetic-target-model',
    'owner_profile': 'synthetic-target-owner', 'paused': False,
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def frozen_data():
    with zipfile.ZipFile(FIXTURES / 'frozen-writer-v1.zip') as bundle:
        return json.loads(bundle.read('library.json'))


def v2_data():
    data = frozen_data()
    data['settings'] = {'enrichment_settings': deepcopy(SOURCE_SETTINGS)}
    for row in data['items']:
        row.update(summary_source='none', summary_revision=0, extracted_text='', generated_provenance=None)
        if row['summary']:
            row.update(summary_source='generated', summary_revision=7,
                       extracted_text='Synthetic retained article body — 雪.',
                       generated_provenance=canonical({'provider': 'synthetic-actual-provider',
                           'model': 'synthetic-actual-model', 'coverage': 'extracted_text',
                           'applied_fields': ['summary', 'tags'], 'conflicted_fields': []}))
        if row['kind'] == 'image':
            row.update(summary='My synthetic image words', summary_source='manual', summary_revision=9,
                       generated_provenance=canonical({'provider': 'synthetic-vision-provider',
                           'model': 'synthetic-vision-model', 'coverage': 'owned_image', 'applied_fields': ['tags'], 'conflicted_fields': []}))
        row['enrichment_status'] = 'succeeded'
    return data


class PortabilityV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = BookmarkService(self.root / 'source')
        self.target = BookmarkService(self.root / 'target')
        for service in (self.source, self.target):
            with service._storage._transaction() as c:
                self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0], 11)

    def restore(self, data, service=None, version=2):
        with (service or self.target)._storage._transaction(write=True) as c:
            restore_content(c, data, version=version)

    def content(self, service=None, version=2):
        with (service or self.target)._storage._transaction() as c:
            return snapshot(c, version=version)

    def set_config(self, service, key, value):
        with service._storage._transaction(write=True) as c:
            c.execute('INSERT INTO library_config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                      (key, canonical(value)))

    def config(self, service, key):
        with service._storage._transaction() as c:
            row = c.execute('SELECT value FROM library_config WHERE key=?', (key,)).fetchone()
            return json.loads(row['value']) if row else None

    def upload(self, target, raw):
        store = PortabilityStore(target._storage)
        result = store.upload_create(len(raw), sha256(raw).hexdigest(), str(uuid4()))
        for offset in range(0, len(raw), 32768):
            store.upload_chunk(result['id'], offset, base64.b64encode(raw[offset:offset + 32768]).decode())
        return store, store.backup_preview(result['id'])

    def bundle_bytes(self, service):
        store = PortabilityStore(service._storage)
        artifact = store.export_create(request_id=str(uuid4()))
        pieces = []
        offset = 0
        while offset < artifact['size']:
            chunk = store.export_read(artifact['id'], offset)
            pieces.append(base64.b64decode(chunk['content_base64']))
            offset = chunk['next_offset']
        return artifact, b''.join(pieces)

    def test_new_writer_records_v2_and_never_offers_lossy_v1_export(self):
        output = self.root / 'new.zip'
        archive.write_bundle(output, empty_data(), lambda key: self.fail('No assets'), 'synthetic-source')
        with zipfile.ZipFile(output) as bundle:
            self.assertEqual(json.loads(bundle.read('manifest.json'))['version'], 2)
        artifact, raw = self.bundle_bytes(self.source)
        self.assertEqual(artifact['format_version'], 2)
        store, preview = self.upload(self.target, raw)
        self.assertEqual(preview['format_version'], 2)
        receipt = store.backup_restore(preview['preview_id'], preview['input_digest'], str(uuid4()))
        self.assertEqual(receipt['state'], 'succeeded')

    def test_frozen_archive_is_unchanged_genuine_pinned_writer_v1(self):
        raw = (FIXTURES / 'frozen-writer-v1.zip').read_bytes()
        provenance = json.loads((FIXTURES / 'frozen-writer-v1.provenance.json').read_text())
        self.assertEqual(provenance['writer_commit'], PINNED_WRITER)
        self.assertIs(provenance['synthetic_only'], True)
        self.assertEqual(sha256(raw).hexdigest(), provenance['fixture_sha256'])
        self.assertEqual(provenance['writer_source_sha256']['bookmarks/portability/content.py'],
                         '9a2e4714c2e2da07319a1d7a33454f4530dc4c5241e8b338a003069b353539f1')
        data, assets, manifest = archive.read_bundle(FIXTURES / 'frozen-writer-v1.zip')
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(len(data['items']), 3)
        self.assertEqual(len(assets), 1)
        self.assertEqual({row['kind'] for row in data['items']}, {'link', 'image'})
        self.assertTrue(any(row['suppressed'] for row in data['item_tags']))
        self.assertTrue(any(row['manual'] for row in data['item_tags']))
        self.assertTrue(any(row['generated'] for row in data['item_tags']))
        self.assertFalse(NEW_FIELDS & set(data['items'][0]))
        validate_content(data, version=1)

    def test_v1_restore_adapts_legacy_summary_and_preserves_inert_history(self):
        self.set_config(self.target, 'enrichment_settings', TARGET_SETTINGS)
        before = SettingsStore(self.target._storage).get()
        identity = self.target.identity()
        store, preview = self.upload(self.target, (FIXTURES / 'frozen-writer-v1.zip').read_bytes())
        self.assertEqual(preview['format_version'], 1)
        rid = str(uuid4())
        receipt = store.backup_restore(preview['preview_id'], preview['input_digest'], rid)
        self.assertEqual(store.backup_restore_get(rid), receipt)
        self.assertEqual(self.target.identity(), identity)
        self.assertEqual(self.config(self.target, 'enrichment_settings'), TARGET_SETTINGS)
        after = SettingsStore(self.target._storage).get()
        self.assertEqual(after['settings'], before['settings'])
        self.assertEqual(after['revision'], before['revision'])
        self.assertEqual(after['restored_intent']['model'], 'frozen-v1-model')
        with self.target._storage._transaction() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0], 0)
            for row in c.execute('SELECT * FROM items'):
                self.assertEqual(row['summary_source'], 'legacy' if row['summary'] else 'none')
                self.assertEqual(row['summary_revision'], 0)
                self.assertEqual(row['extracted_text'], '')
                self.assertIsNone(row['generated_provenance'])
                self.assertIsNone(row['enrichment_job_id'])
                self.assertEqual(row['enrichment_generation'], 1)
                self.assertNotIn(row['enrichment_status'], ('pending', 'running'))
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        projected = self.content(version=1)
        self.assertFalse(NEW_FIELDS & set(projected['items'][0]))
        validate_content(projected, version=1)

    def test_v1_validator_rejects_new_fields_and_v2_settings(self):
        data = frozen_data()
        validate_content(data, version=1)
        for name, value in [('summary_source', 'legacy'), ('extracted_text', ''),
                            ('summary_revision', 0), ('generated_provenance', None)]:
            with self.subTest(field=name):
                bad = deepcopy(data)
                bad['items'][0][name] = value
                with self.assertRaises(ValidationError):
                    validate_content(bad, version=1)
        with self.assertRaises(ValidationError):
            validate_content(v2_data(), version=1)
        with self.assertRaises(ValidationError):
            validate_content(data, version=2)

    def test_dispatch_rejects_coercible_or_unknown_versions_before_storage(self):
        for version in (True, False, 0, 3, 1.0, 2.0, '1', '2', None):
            with self.subTest(version=version):
                with self.assertRaises(ValidationError):
                    validate_content(empty_data(), version=version)
                with self.target._storage._transaction(write=True) as c:
                    with self.assertRaises(ValidationError):
                        snapshot(c, version=version)
                    with self.assertRaises(ValidationError):
                        restore_content(c, empty_data(), version=version)

    def test_v2_content_roundtrip_preserves_metadata_order_sources_and_settings_intent(self):
        data = v2_data()
        validate_content(data)
        self.set_config(self.target, 'enrichment_settings', TARGET_SETTINGS)
        self.set_config(self.target, 'enrichment_settings_revision', 17)
        before = SettingsStore(self.target._storage).get()
        identity = self.target.identity()
        self.restore(data)
        self.assertEqual(self.content(), data)
        self.assertEqual(self.target.identity(), identity)
        self.assertEqual(self.config(self.target, 'enrichment_settings'), TARGET_SETTINGS)
        self.assertEqual(self.config(self.target, 'enrichment_settings_revision'), 17)
        self.assertEqual(self.config(self.target, 'restored_enrichment_settings'), SOURCE_SETTINGS)
        after = SettingsStore(self.target._storage).get()
        self.assertEqual(after['settings'], before['settings'])
        self.assertEqual(after['revision'], before['revision'])
        self.assertEqual(after['restored_intent'], SOURCE_SETTINGS)
        with self.target._storage._transaction() as c:
            for row in c.execute('SELECT enrichment_job_id,enrichment_generation FROM items'):
                self.assertEqual(tuple(row), (None, 1))
            for table in ('jobs', 'capture_operations', 'import_jobs'):
                self.assertEqual(c.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
        with self.assertRaises(ConflictError):
            self.restore(data)

    def test_v2_archive_roundtrip_keeps_asset_bytes_and_receipt_tuple(self):
        data = v2_data()
        _, assets, _ = archive.read_bundle(FIXTURES / 'frozen-writer-v1.zip')
        self.restore(data, self.source)
        folder = self.root / 'source' / 'assets'
        folder.mkdir(exist_ok=True)
        for key, raw in assets.items():
            (folder / (key + '.blob')).write_bytes(raw)
        self.set_config(self.target, 'enrichment_settings', TARGET_SETTINGS)
        artifact, raw = self.bundle_bytes(self.source)
        self.assertEqual(artifact['format_version'], 2)
        store, preview = self.upload(self.target, raw)
        self.assertEqual(preview['format_version'], 2)
        rid = str(uuid4())
        first = store.backup_restore(preview['preview_id'], preview['input_digest'], rid)
        self.assertEqual(store.backup_restore(preview['preview_id'], preview['input_digest'], rid), first)
        self.assertEqual(store.backup_restore_get(rid), first)
        with self.assertRaises(ConflictError):
            store.backup_restore(preview['preview_id'], '0' * 64, rid)
        self.assertEqual(self.content(), data)
        for key, expected in assets.items():
            self.assertEqual((self.root / 'target' / 'assets' / (key + '.blob')).read_bytes(), expected)
        self.assertEqual(self.config(self.target, 'enrichment_settings'), TARGET_SETTINGS)

    def test_restored_intent_wins_over_destination_defaults_on_reexport(self):
        self.set_config(self.target, 'enrichment_settings', TARGET_SETTINGS)
        self.restore(v2_data())
        self.assertEqual(self.content()['settings'], {'enrichment_settings': SOURCE_SETTINGS})
        with self.target._storage._transaction(write=True) as c:
            c.execute("DELETE FROM library_config WHERE key='restored_enrichment_settings'")
        self.assertEqual(self.content()['settings'], {'enrichment_settings': TARGET_SETTINGS})

    def test_explicit_settings_adoption_retires_inert_intent_before_later_reexport(self):
        for version, data in ((1, frozen_data()), (2, v2_data())):
            with self.subTest(version=version):
                service = BookmarkService(self.root / ('adoption-' + str(version)))
                settings = SettingsStore(service._storage)
                settings.seed_route({'provider':'synthetic-target-provider', 'model':'synthetic-target-model',
                                     'owner_profile':'synthetic-target-owner'})
                self.restore(data, service, version=version)
                cfg = settings.get()
                # Approved adoption is an ordinary explicit settings Save,
                # excluding the source owner; it must retire both inert keys.
                adopted = settings.update(cfg['revision'],
                    {key:value for key,value in cfg['restored_intent'].items() if key != 'owner_profile'})
                current = settings.update(adopted['revision'], {'model':'synthetic-after-adoption-model'})
                self.assertEqual(current['settings']['owner_profile'], 'synthetic-target-owner')
                self.assertEqual(self.content(service)['settings']['enrichment_settings'], current['settings'])

    def test_v2_pending_history_becomes_review_without_activating_work(self):
        data = v2_data()
        data['items'][0]['enrichment_status'] = 'running'
        self.restore(data)
        row = self.content()['items'][0]
        self.assertEqual(row['enrichment_status'], 'needs_review')
        self.assertEqual(json.loads(row['processing_history']), ['failed', 'running'])
        for name in NEW_FIELDS:
            self.assertEqual(row[name], data['items'][0][name])

    def test_actual_generated_summary_and_retained_body_can_be_backed_up_without_mask_reordering(self):
        from bookmarks.jobs import JobQueue
        settings = SettingsStore(self.source._storage)
        cfg = settings.seed_route({'provider':'synthetic-provider', 'model':'synthetic-model',
                                   'owner_profile':'synthetic-owner'})
        settings.update(cfg['revision'], {'retain_extracted_text':True})
        item = self.source.save_link('https://example.org/synthetic-produced')
        queue = JobQueue(self.root / 'source')
        job = queue.claim('synthetic-worker')
        self.assertIsNotNone(job)
        assert job is not None
        self.assertTrue(queue.complete(job['id'], 'synthetic-worker',
            {'summary':'Synthetic queue-produced summary', 'tags':['Synthetic'],
             'provider':'synthetic-actual-provider', 'model':'synthetic-actual-model',
             'coverage':'extracted_text'}, token=job['token'],
             extracted_text='Synthetic queue-produced retained body'))
        with self.source._storage._transaction() as c:
            raw = c.execute('SELECT generated_provenance FROM items WHERE id=?', (item['id'],)).fetchone()[0]
        data = self.content(self.source)
        self.assertEqual(data['items'][0]['generated_provenance'], raw)
        self.assertEqual(data['items'][0]['summary_source'], 'generated')
        self.assertEqual(data['items'][0]['extracted_text'], 'Synthetic queue-produced retained body')
        self.restore(data)
        self.assertEqual(self.content(), data)

    def test_canonical_applied_and_conflicted_field_sets_allow_partial_conflicts(self):
        for applied, conflicted in ((['summary','tags'], []), (['tags'], ['summary']),
                                    ([], ['summary']), ([], ['summary','tags'])):
            with self.subTest(applied=applied, conflicted=conflicted):
                data = v2_data()
                original = json.loads(data['items'][0]['generated_provenance'])
                raw = canonical({**original, 'applied_fields':applied, 'conflicted_fields':conflicted})
                data['items'][0]['generated_provenance'] = raw
                validate_content(data)

    def test_compatible_v1_intent_survives_modern_default_settings_on_v2_reexport(self):
        self.restore(frozen_data(), version=1)
        settings = self.content()['settings']['enrichment_settings']
        self.assertEqual(settings['model'], 'frozen-v1-model')
        self.assertEqual(settings['owner_profile'], 'synthetic-v1-owner')
        self.assertIs(settings['image_analysis'], False)
        self.assertIs(settings['retain_extracted_text'], False)
        # Libraries restored by the previous client only have its inert key.
        with self.target._storage._transaction(write=True) as c:
            c.execute("DELETE FROM library_config WHERE key='restored_enrichment_settings'")
        self.assertEqual(self.content()['settings']['enrichment_settings'], settings)

    def test_incompatible_old_route_is_readable_but_cannot_be_silently_dropped_on_reexport(self):
        data = frozen_data()
        data['settings']['enrichment_route']['provider'] = 'https://legacy.example.org'
        validate_content(data, version=1)
        self.restore(data, version=1)
        self.assertEqual(self.content(version=1)['settings'], data['settings'])
        with self.assertRaises(ValidationError):
            self.content()

    def test_snapshot_never_defaults_malformed_persisted_settings_or_discards_future_columns(self):
        for key, value in (('enrichment_settings', {'api_key':'secret'}),
                           ('restored_enrichment_settings', {'model':'incomplete'})):
            with self.subTest(key=key):
                service = BookmarkService(self.root / key)
                self.set_config(service, key, value)
                with self.assertRaises(StorageError):
                    self.content(service)
        self.source.save_link('https://example.org/future-column')
        with self.source._storage._transaction(write=True) as c:
            c.execute('ALTER TABLE items ADD COLUMN future_content TEXT')
        for version in (1, 2):
            with self.assertRaises(ValidationError):
                self.content(self.source, version=version)

    def test_v2_settings_reject_unknowns_secrets_owner_types_and_bounds(self):
        cases = [
            lambda s: s.update(api_key='secret'), lambda s: s.update(token='secret'),
            lambda s: s.update(endpoint='https://example.org'), lambda s: s.update(revision=3),
            lambda s: s.update(provider='https://example.org'), lambda s: s.update(model='x@y'),
            lambda s: s.update(owner_profile=1), lambda s: s.update(automatic_summary=1),
            lambda s: s.update(paused=0), lambda s: s.update(retain_extracted_text='false'),
            lambda s: s.update(image_analysis=None), lambda s: s.update(model=' '),
            lambda s: s.update(provider='x' * 301), lambda s: s.update(model='\ud800'),
            lambda s: s.update(summary_language=' '), lambda s: s.update(summary_language='x' * 81),
            lambda s: s.update(summary_length='huge'), lambda s: s.update(guidance='x' * 2001),
            lambda s: s.update(guidance='\ud800'), lambda s: s.update(preferred_tags=['x'] * 21),
            lambda s: s.update(preferred_tags=['x' * 81]), lambda s: s.pop('paused'),
        ]
        for mutate in cases:
            with self.subTest(case=cases.index(mutate)):
                data = v2_data()
                mutate(data['settings']['enrichment_settings'])
                with self.assertRaises(ValidationError):
                    validate_content(data)
        for settings in ({'enrichment_route': {}}, {'enrichment_settings': {}, 'secret': 'x'},
                         {'enrichment_settings': None}, {'enrichment_settings': []}):
            data = v2_data()
            data['settings'] = settings
            with self.assertRaises(ValidationError):
                validate_content(data)

    def test_v2_item_metadata_and_provenance_are_bounded_exact_and_canonical(self):
        mutations = [
            lambda r: r.update(summary_source='untrusted'), lambda r: r.update(summary_source=[]),
            lambda r: r.update(summary_revision=True), lambda r: r.update(summary_revision=-1),
            lambda r: r.update(summary_revision=2**63), lambda r: r.update(extracted_text='x' * 30001),
            lambda r: r.update(extracted_text=None), lambda r: r.update(extracted_text='\ud800'),
            lambda r: r.update(generated_provenance={}), lambda r: r.update(generated_provenance='{}'),
            lambda r: r.update(generated_provenance='[]'), lambda r: r.update(generated_provenance='{"provider":NaN}'),
            lambda r: r.update(generated_provenance='{"provider":"a","provider":"b"}'),
            lambda r: r.update(generated_provenance=' ' + r['generated_provenance']),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'coverage':'other'})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'applied_fields':[]})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'applied_fields':['tags','summary']})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'applied_fields':['summary','summary']})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'applied_fields':['notes']})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'raw_response':'secret'})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'provider':'p' * 301})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'model':7})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'conflicted_fields':['summary']})),
            lambda r: r.update(generated_provenance=canonical({**json.loads(r['generated_provenance']), 'conflicted_fields':'summary'})),
            lambda r: r.pop('summary_source'), lambda r: r.update(secret='x'),
        ]
        for mutate in mutations:
            with self.subTest(case=mutations.index(mutate)):
                data = v2_data()
                mutate(data['items'][0])
                with self.assertRaises(ValidationError):
                    validate_content(data)
        data = v2_data()
        data['items'][0]['extracted_text'] = '雪' * 30000
        validate_content(data)

    def test_combined_v2_json_quota_counts_new_retained_body(self):
        from unittest.mock import patch
        data = v2_data()
        data['items'][0]['extracted_text'] = '雪' * 1000
        # Limit exceeds the old-field-only payload but not new retained content.
        with patch('bookmarks.portability.content_v2.MAX_JSON_BYTES', 5000):
            with self.assertRaises(ValidationError):
                validate_content(data)

    def test_exact_manifest_dispatch_rejects_cross_version_content_and_unknown_versions(self):
        for version, data in ((1, v2_data()), (2, frozen_data()), (3, empty_data()),
                              (True, empty_data()), (2.0, empty_data())):
            with self.subTest(version=version):
                output = self.root / 'hostile.zip'
                raw_bundle(output, data, manifest_change=lambda m: m.update(version=version))
                with self.assertRaises(ValueError):
                    archive.read_bundle(output)

    def test_bad_v2_restore_cannot_change_existing_settings_or_content(self):
        self.set_config(self.target, 'enrichment_settings', TARGET_SETTINGS)
        self.set_config(self.target, 'restored_enrichment_settings', SOURCE_SETTINGS)
        before = self.content()
        data = v2_data()
        data['items'][0]['summary_revision'] = True
        with self.assertRaises(ValidationError):
            self.restore(data)
        self.assertEqual(self.content(), before)
        self.assertEqual(self.config(self.target, 'enrichment_settings'), TARGET_SETTINGS)

    def test_settings_statement_failure_rolls_back_rows_inside_callers_transaction(self):
        data = v2_data()
        self.set_config(self.target, 'enrichment_settings', TARGET_SETTINGS)
        with self.target._storage._transaction(write=True) as c:
            c.execute("INSERT INTO library_config VALUES('caller-marker','kept')")
            c.execute("""CREATE TRIGGER reject_restored_settings BEFORE INSERT ON library_config
                WHEN NEW.key='restored_enrichment_settings' BEGIN SELECT RAISE(ABORT,'synthetic'); END""")
            with self.assertRaises(sqlite3.IntegrityError):
                restore_content(c, data)
            self.assertTrue(c.in_transaction)
            self.assertEqual(c.execute('SELECT count(*) FROM items').fetchone()[0], 0)
            self.assertIsNone(c.execute("SELECT value FROM library_config WHERE key='restored_enrichment_settings'").fetchone())
            self.assertEqual(c.execute("SELECT value FROM library_config WHERE key='caller-marker'").fetchone()[0], 'kept')
        self.assertEqual(self.config(self.target, 'enrichment_settings'), TARGET_SETTINGS)

    def test_v2_preview_rejects_inconsistent_asset_body_without_mutation(self):
        data = v2_data()
        _, assets, _ = archive.read_bundle(FIXTURES / 'frozen-writer-v1.zip')
        key = next(iter(assets))
        output = self.root / 'wrong-size.zip'
        data['assets'][0]['size'] += 1
        raw_bundle(output, data, {'assets/' + key + '.blob': assets[key]},
                   manifest_change=lambda m: m.update(version=2))
        raw = output.read_bytes()
        store = PortabilityStore(self.target._storage)
        upload = store.upload_create(len(raw), sha256(raw).hexdigest(), str(uuid4()))
        store.upload_chunk(upload['id'], 0, base64.b64encode(raw).decode())
        with self.assertRaises(ValidationError):
            store.backup_preview(upload['id'])
        self.assertEqual(self.target.counts()['all'], 0)

    def test_html_explicitly_drops_retained_text_settings_and_provenance(self):
        data = v2_data()
        output = self.root / 'lossy.html'
        result = archive.write_html(output, data)
        raw = output.read_text()
        for value in ('Synthetic retained article body', 'synthetic-source-model', 'synthetic-actual-model'):
            self.assertNotIn(value, raw)
        self.assertTrue(any('lossy' in text for text in result['limitations']))
        self.assertEqual(result['counts']['omitted_settings'], 1)


if __name__ == '__main__':
    unittest.main()
