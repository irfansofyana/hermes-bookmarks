"""Synthetic codec fixtures only: no host/provider or user-library access."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile

from PIL import Image


TABLES = ('items', 'collections', 'tags', 'item_tags', 'item_assets', 'assets', 'sources')


def empty_data():
    return {**{name: [] for name in TABLES}, 'settings': {}}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def image_bytes(fmt='PNG', size=(2, 3), animated=False):
    stream = BytesIO()
    image = Image.new('RGB', size, 'blue')
    options = {}
    if animated:
        options = {'save_all': True, 'append_images': [Image.new('RGB', size, 'red')], 'duration': 100, 'loop': 0}
    image.save(stream, format=fmt, **options)
    return stream.getvalue()


def raw_bundle(path, data=None, blobs=None, manifest_change=None, library_raw=None, extras=()):
    data = empty_data() if data is None else data
    payloads = {'library.json': encoded(data) if library_raw is None else library_raw}
    payloads.update(blobs or {})
    manifest = {'format': 'hermes-bookmarks-content', 'version': 1,
                'created_at': '2026-10-23T00:00:00+00:00', 'source_identity': 'synthetic-library',
                'counts': {name: len(data[name]) for name in TABLES},
                'members': {name: {'size': len(raw), 'sha256': sha256(raw).hexdigest()} for name, raw in payloads.items()}}
    if manifest_change:
        manifest_change(manifest)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', encoded(manifest))
            for name, raw in payloads.items():
                archive.writestr(name, raw)
            for name, raw in extras:
                archive.writestr(name, raw)
    return manifest


class PortableArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'backup.zip'

    def test_empty_bundle_roundtrip_has_exact_manifest_and_canonical_payload(self):
        from bookmarks.portability.archive import write_bundle, read_bundle
        data = empty_data()
        previous = os.umask(0o022)
        try:
            result = write_bundle(self.target, data, lambda key: self.fail('No registered assets'), 'synthetic-library')
        finally:
            os.umask(previous)
        restored, assets, manifest = read_bundle(self.target)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(restored, data)
        self.assertEqual(assets, {})
        self.assertEqual(set(manifest), {'format', 'version', 'created_at', 'source_identity', 'counts', 'members'})
        self.assertEqual(manifest['format'], 'hermes-bookmarks-content')
        self.assertEqual(manifest['version'], 2)
        self.assertEqual(manifest['source_identity'], 'synthetic-library')
        self.assertEqual(result['counts'], {name: 0 for name in TABLES})
        self.assertTrue(any('unencrypted' in value.lower() for value in result['limitations']))
        with zipfile.ZipFile(self.target) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json', 'library.json'})
            self.assertEqual(archive.read('library.json'), encoded(data))
            self.assertEqual(manifest['members'], {'library.json': {'size': len(encoded(data)), 'sha256': sha256(encoded(data)).hexdigest()}})

    def library_fixture(self):
        from bookmarks.assets import AssetStore
        from bookmarks.portability.content import snapshot
        from bookmarks.service import BookmarkService
        root = self.root / 'library'
        service = BookmarkService(root)
        assets = AssetStore(root)
        image = assets.store_image(image_bytes(), 'image/png')
        staged = assets.store_image(image_bytes('JPEG'), 'image/jpeg')
        folder = service.collection_create('Research <&>')
        nested = service.collection_create('Empty "雪"', folder['id'])
        first = service.capture(url='https://example.test/?q=1&b=2', title='<script>雪</script>',
                                description='<b>plain & text</b>', notes='private note', tags=['雪 & sun'],
                                favorite=True, read_later=True, collection_id=folder['id'], attachment_ids=[image['id']])['item']
        second = service.capture(url='https://example.test/trash', title='Trash')['item']
        service.trash(second['id'], second['revision'])
        service.capture(kind='image', primary_asset_id=image['id'], title='Image', notes='image note', operation_key='00000000-0000-4000-8000-000000000001')
        with service._storage._transaction() as connection:
            data = snapshot(connection)
        return service, assets, data, first, image, staged, nested

    def test_service_snapshot_assets_are_exact_shared_once_and_staged_retained(self):
        from bookmarks.portability.archive import write_bundle, read_bundle
        service, store, data, _, image, staged, _ = self.library_fixture()
        result = write_bundle(self.target, data, lambda key: store.read_asset(key)[0], service.identity()['library_id'])
        restored, assets, manifest = read_bundle(self.target)
        self.assertEqual(restored, data)
        self.assertEqual(set(assets), {image['id'], staged['id']})
        self.assertEqual(assets[image['id']], store.read_asset(image['id'])[0])
        self.assertEqual(assets[staged['id']], store.read_asset(staged['id'])[0])
        self.assertEqual(result['counts']['items'], 3)
        self.assertEqual(result['counts']['assets'], 2)
        self.assertEqual(set(manifest['members']), {'library.json', 'assets/' + image['id'] + '.blob', 'assets/' + staged['id'] + '.blob'})

    def test_html_escapes_text_preserves_nested_empty_folders_and_reports_exact_losses(self):
        from bookmarks.imports.html import parse_bookmarks
        from bookmarks.portability.archive import write_html
        _, _, data, _, _, _, _ = self.library_fixture()
        html = self.root / 'bookmarks.html'
        result = write_html(html, data)
        raw = html.read_text('utf-8')
        self.assertNotIn('<script>', raw)
        self.assertNotIn('<b>', raw)
        self.assertIn('Empty &quot;雪&quot;', raw)
        rows = parse_bookmarks(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://example.test/?q=1&b=2')
        self.assertEqual(rows[0]['title'], '<script>雪</script>')
        self.assertEqual(rows[0]['description'], '<b>plain & text</b>')
        self.assertEqual(rows[0]['tags'], ['雪 & sun'])
        self.assertEqual(rows[0]['collection_path'], ['Research <&>'])
        for key, value in {'exported_links': 1, 'omitted_images': 1, 'omitted_trashed_links': 1,
                           'omitted_assets': 2, 'omitted_notes': 2, 'omitted_flags': 1,
                           'omitted_tag_provenance': 1, 'flattened_trash': 0}.items():
            self.assertEqual(result['counts'][key], value, key)
        self.assertTrue(result['limitations'])
        other = self.root / 'trash.html'
        included = write_html(other, data, include_trash=True)
        self.assertEqual(len(parse_bookmarks(other.read_text('utf-8'))), 2)
        self.assertEqual(included['counts']['flattened_trash'], 1)
        self.assertEqual(included['counts']['omitted_trashed_links'], 0)

    def test_html_refuses_unsafe_legacy_url_without_partial_file_or_private_url_in_error(self):
        from bookmarks.portability.archive import write_html
        _, _, data, first, _, _, _ = self.library_fixture()
        row = next(row for row in data['items'] if row['id'] == first['id'])
        row['url'] = 'javascript:alert(private-secret)'
        target = self.root / 'unsafe.html'
        with self.assertRaises(ValueError) as raised:
            write_html(target, data)
        self.assertIn(first['id'], str(raised.exception))
        self.assertNotIn('private-secret', str(raised.exception))
        self.assertFalse(target.exists())

    def test_html_empty_library_and_invalid_include_trash_type(self):
        from bookmarks.portability.archive import write_html
        target = self.root / 'empty.html'
        previous = os.umask(0o022)
        try:
            result = write_html(target, empty_data())
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertIn('<DL>', target.read_text('utf-8'))
        self.assertEqual(result['counts']['exported_links'], 0)
        with self.assertRaises(ValueError):
            write_html(self.root / 'invalid.html', empty_data(), include_trash=1)

    def test_asset_decoding_mime_dimensions_animation_and_size_are_validated(self):
        from bookmarks.portability.archive import read_bundle, write_bundle
        key = 'a' * 32
        normal = image_bytes()
        data = empty_data()
        data['assets'] = [{'rowid': 1, 'id': key, 'mime_type': 'image/png', 'size': len(normal), 'width': 2, 'height': 3}]
        for raw, mime in [(normal, 'image/jpeg'), (image_bytes(size=(3, 3)), 'image/png'),
                          (image_bytes(animated=True), 'image/png'), (normal[:30], 'image/png'),
                          (b'<svg/>', 'image/png'), (b'x' * (10 * 1024 * 1024 + 1), 'image/png'),
                          (image_bytes(size=(5000, 5000)), 'image/png')]:
            with self.subTest(size=len(raw), mime=mime):
                hostile = deepcopy(data)
                hostile['assets'][0].update(size=len(raw), mime_type=mime)
                raw_bundle(self.target, hostile, {'assets/' + key + '.blob': raw})
                with self.assertRaises(ValueError):
                    read_bundle(self.target)
                self.target.unlink()
                with self.assertRaises(ValueError):
                    write_bundle(self.target, hostile, lambda unused: raw, 'synthetic-library')
                self.assertFalse(self.target.exists())
        for fmt, mime in [('PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')]:
            with self.subTest(fmt=fmt):
                raw = image_bytes(fmt)
                data['assets'][0].update(size=len(raw), mime_type=mime)
                write_bundle(self.target, data, lambda unused: raw, 'synthetic-library')
                self.assertEqual(read_bundle(self.target)[1], {key: raw})
                self.target.unlink()

    def test_inventory_and_digest_are_checked_against_registered_assets(self):
        from bookmarks.portability.archive import read_bundle
        raw = image_bytes()
        key = 'a' * 32
        data = empty_data()
        data['assets'] = [{'rowid': 1, 'id': key, 'mime_type': 'image/png', 'size': len(raw), 'width': 2, 'height': 3}]
        raw_bundle(self.target, data)
        with self.assertRaises(ValueError):
            read_bundle(self.target)
        raw_bundle(self.target, blobs={'assets/' + key + '.blob': raw})
        with self.assertRaises(ValueError):
            read_bundle(self.target)
        def wrong_hash(manifest):
            manifest['members']['assets/' + key + '.blob']['sha256'] = '0' * 64
        raw_bundle(self.target, data, {'assets/' + key + '.blob': raw}, manifest_change=wrong_hash)
        with self.assertRaises(ValueError):
            read_bundle(self.target)

    def test_bounded_archive_json_and_streamed_total_fail_without_partial_outputs(self):
        from unittest.mock import patch
        from bookmarks.portability import archive
        raw_bundle(self.target)
        for name, bound in [('MAX_ARCHIVE_BYTES', 80), ('MAX_JSON_BYTES', 20), ('MAX_UNCOMPRESSED_BYTES', 100)]:
            with self.subTest(name=name):
                with patch.object(archive, name, bound):
                    with self.assertRaises(ValueError):
                        archive.read_bundle(self.target)
                    output = self.root / (name + '.zip')
                    with self.assertRaises(ValueError):
                        archive.write_bundle(output, empty_data(), lambda key: b'', 'synthetic-library')
                    self.assertFalse(output.exists())
        with patch.object(archive, 'MAX_ARCHIVE_BYTES', 40):
            target = self.root / 'too-large.html'
            with self.assertRaises(ValueError):
                archive.write_html(target, empty_data())
            self.assertFalse(target.exists())

    def test_output_collisions_and_missing_asset_do_not_clobber_other_files(self):
        from bookmarks.portability.archive import read_bundle, write_bundle, write_html
        self.target.write_bytes(b'original')
        for writer in [lambda: write_bundle(self.target, empty_data(), lambda key: b'', 'synthetic-library'),
                       lambda: write_html(self.target, empty_data())]:
            with self.assertRaises(FileExistsError):
                writer()
            self.assertEqual(self.target.read_bytes(), b'original')
        link = self.root / 'link.zip'
        link.symlink_to(self.target)
        with self.assertRaises(ValueError):
            read_bundle(link)
        with self.assertRaises(FileExistsError):
            write_bundle(link, empty_data(), lambda key: b'', 'synthetic-library')
        key = 'a' * 32
        data = empty_data()
        raw = image_bytes()
        data['assets'] = [{'rowid': 1, 'id': key, 'mime_type': 'image/png', 'size': len(raw), 'width': 2, 'height': 3}]
        def missing(unused):
            raise FileNotFoundError('Asset unavailable')
        target = self.root / 'missing.zip'
        with self.assertRaises(FileNotFoundError):
            write_bundle(target, data, missing, 'synthetic-library')
        self.assertFalse(target.exists())

    def test_strict_json_writer_and_manifest_parser_reject_unknown_or_nonfinite_content(self):
        from bookmarks.portability.archive import read_bundle, write_bundle
        for value in [float('nan'), float('inf'), '\ud800']:
            data = empty_data()
            data['extra'] = value
            with self.assertRaises(ValueError):
                write_bundle(self.target, data, lambda key: b'', 'synthetic-library')
            self.assertFalse(self.target.exists())
        for raw in [b'{"format":1,"format":2}', b'{"version":NaN}', b'{"version":1e999}', b'[]']:
            with zipfile.ZipFile(self.target, 'w') as archive:
                archive.writestr('manifest.json', raw)
                archive.writestr('library.json', encoded(empty_data()))
            with self.assertRaises(ValueError):
                read_bundle(self.target)

    def test_rejects_duplicate_unsafe_unlisted_and_missing_members(self):
        from bookmarks.portability.archive import read_bundle
        for name in ['../escape', '/absolute', 'C:/drive', 'assets\\escape', 'folder/', 'unexpected', 'library.json', 'manifest.json']:
            with self.subTest(name=name):
                raw_bundle(self.target, extras=[(name, b'hostile')])
                with self.assertRaises(ValueError):
                    read_bundle(self.target)
                self.assertFalse((self.root / 'escape').exists())
        raw_bundle(self.target, manifest_change=lambda m: m['members'].update({'assets/' + 'a' * 32 + '.blob': {'size': 1, 'sha256': '0' * 64}}))
        with self.assertRaises(ValueError):
            read_bundle(self.target)

    def test_rejects_unsupported_or_inexact_manifest(self):
        from bookmarks.portability.archive import read_bundle
        changes = [lambda m: m.update(version=3), lambda m: m.update(version=True),
                   lambda m: m.update(format='other'), lambda m: m.update(secret='not allowed'),
                   lambda m: m.update(created_at='invalid'), lambda m: m.update(source_identity=4),
                   lambda m: m['counts'].update(items=True), lambda m: m['counts'].update(items=1),
                   lambda m: m['members']['library.json'].update(size=True),
                   lambda m: m['members']['library.json'].update(sha256='0' * 64),
                   lambda m: m['members']['library.json'].update(extra=1),
                   lambda m: m['members'].update({'manifest.json': {'size': 0, 'sha256': '0' * 64}})]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                raw_bundle(self.target, manifest_change=change)
                with self.assertRaises(ValueError):
                    read_bundle(self.target)

    def test_rejects_duplicate_json_keys_nonfinite_invalid_unicode_and_wrong_shape(self):
        from bookmarks.portability.archive import read_bundle
        for raw in [b'{"items":[],"items":[]}', b'{"items":NaN}', b'{"items":Infinity}',
                    b'{"items":-Infinity}', b'{"items":"\\ud800"}', b'[]', b'\xff', b'{']:
            with self.subTest(raw=raw):
                raw_bundle(self.target, library_raw=raw)
                with self.assertRaises(ValueError):
                    read_bundle(self.target)

    def test_rejects_nonregular_zip_entries(self):
        from bookmarks.portability.archive import read_bundle
        for mode in [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFDIR | 0o755]:
            with self.subTest(mode=mode):
                manifest = raw_bundle(self.target)
                with zipfile.ZipFile(self.target, 'w') as archive:
                    archive.writestr('manifest.json', encoded(manifest))
                    info = zipfile.ZipInfo('library.json')
                    info.create_system = 3
                    info.external_attr = mode << 16
                    archive.writestr(info, encoded(empty_data()))
                with self.assertRaises(ValueError):
                    read_bundle(self.target)

    def test_forged_entry_size_cannot_hide_extra_decompressed_bytes(self):
        from bookmarks.portability.archive import read_bundle
        import zlib
        prefix = encoded(empty_data())
        manifest = raw_bundle(self.target)
        with zipfile.ZipFile(self.target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', encoded(manifest))
            archive.writestr('library.json', prefix + b'not-json' * 10000)
        forged = bytearray(self.target.read_bytes())
        with zipfile.ZipFile(self.target) as archive:
            header_offset = archive.getinfo('library.json').header_offset
        struct.pack_into('<I', forged, header_offset + 14, zlib.crc32(prefix))
        struct.pack_into('<I', forged, header_offset + 22, len(prefix))
        central = forged.find(b'PK\x01\x02')
        while central >= 0:
            filename_size = struct.unpack_from('<H', forged, central + 28)[0]
            if forged[central + 46:central + 46 + filename_size] == b'library.json':
                struct.pack_into('<I', forged, central + 16, zlib.crc32(prefix))
                struct.pack_into('<I', forged, central + 24, len(prefix))
                break
            central = forged.find(b'PK\x01\x02', central + 4)
        self.target.write_bytes(forged)
        with self.assertRaises(ValueError):
            read_bundle(self.target)

    def test_local_encryption_flags_and_strong_encryption_flags_are_refused(self):
        from bookmarks.portability.archive import read_bundle
        raw_bundle(self.target)
        original = self.target.read_bytes()
        for magic, position, bit in [(b'PK\x03\x04', 6, 1), (b'PK\x01\x02', 8, 64)]:
            with self.subTest(magic=magic, bit=bit):
                raw = bytearray(original)
                index = raw.find(magic)
                raw[index + position] |= bit
                self.target.write_bytes(raw)
                with self.assertRaises(ValueError):
                    read_bundle(self.target)

    def test_rejects_encrypted_corrupt_and_truncated_zip(self):
        from bookmarks.portability.archive import read_bundle
        raw_bundle(self.target)
        original = self.target.read_bytes()
        hostile = bytearray(original)
        for magic, position in [(b'PK\x03\x04', 6), (b'PK\x01\x02', 8)]:
            start = 0
            while (index := hostile.find(magic, start)) != -1:
                hostile[index + position] |= 1
                start = index + 4
        for content in [bytes(hostile), original[:-30], b'not a zip']:
            self.target.write_bytes(content)
            with self.assertRaises(ValueError):
                read_bundle(self.target)


if __name__ == '__main__':
    unittest.main()
