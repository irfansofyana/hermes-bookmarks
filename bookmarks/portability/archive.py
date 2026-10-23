"""Bounded content codecs; ZIP names are data, never filesystem destinations."""
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import warnings
import zipfile
import zlib

from PIL import Image, UnidentifiedImageError

from ..errors import BookmarkError

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_ASSET_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
TABLES = ('items', 'collections', 'tags', 'item_tags', 'item_assets', 'assets', 'sources')
FORMAT = 'hermes-bookmarks-content'
VERSION = 1
_ASSET_NAME = re.compile(r'assets/([a-f0-9]{32})\.blob\Z')
_SHA256 = re.compile(r'[a-f0-9]{64}\Z')
_FORMATS = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}
BUNDLE_LIMITATIONS = [
    'This unencrypted backup contains sensitive library content, notes and images.',
    'Credentials, host identity, chat sessions, runtime queues, uploads and operation history are excluded.',
    'Processing state and route settings are content history or inert intent; restore never activates jobs or a route.',
    'SHA-256 checksums detect corruption, not authenticity.',
]


def _validate_content(data):
    # The content boundary is independent of the codec and may load later.
    from .content import validate_content
    try:
        validate_content(data)
    except BookmarkError:
        raise ValueError('Invalid portable library content') from None


def _valid_json_value(value):
    """Reject lone surrogates and overflowed finite-looking JSON floats too."""
    if isinstance(value, str):
        value.encode('utf-8', errors='strict')
    elif type(value) is float and not math.isfinite(value):
        raise ValueError('Nonfinite JSON number')
    elif isinstance(value, list):
        for member in value:
            _valid_json_value(member)
    elif isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str):
                raise ValueError('JSON object keys must be strings')
            _valid_json_value(key)
            _valid_json_value(member)
    elif value is not None and type(value) not in (int, float, bool):
        raise ValueError('Unsupported JSON value')


def _json_bytes(value):
    try:
        _valid_json_value(value)
        output = bytearray()
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
        for part in encoder.iterencode(value):
            raw = part.encode('utf-8')
            if len(output) + len(raw) > MAX_JSON_BYTES:
                raise ValueError('JSON exceeds portability limit')
            output.extend(raw)
        return bytes(output)
    except (UnicodeError, RecursionError, TypeError):
        raise ValueError('Invalid portable JSON') from None


def _json_load(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    def constant(value):
        raise ValueError('Nonfinite JSON number')

    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('JSON exceeds portability limit')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        _valid_json_value(value)
        if type(value) is not dict:
            raise ValueError('JSON document must be an object')
        return value
    except (UnicodeError, RecursionError):
        raise ValueError('Invalid portable JSON') from None


def _counts(data):
    return {name: len(data[name]) for name in TABLES}


def _asset_name(asset_id):
    if not isinstance(asset_id, str) or re.fullmatch(r'[a-f0-9]{32}', asset_id) is None:
        raise ValueError('Invalid asset identity')
    return 'assets/' + asset_id + '.blob'


def _validate_image(raw, metadata):
    if type(raw) is not bytes or not raw or len(raw) > MAX_ASSET_BYTES or metadata['size'] != len(raw):
        raise ValueError('Asset size is unavailable, inconsistent or exceeds limit')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if (image.format not in _FORMATS or _FORMATS[image.format] != metadata['mime_type']
                        or image.width * image.height > MAX_PIXELS
                        or (image.width, image.height) != (metadata['width'], metadata['height'])
                        or getattr(image, 'n_frames', 1) != 1):
                    raise ValueError('Unsupported asset type, dimensions or animation')
                image.verify()
            with Image.open(BytesIO(raw)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Invalid image asset') from None


def _member(name):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


class _BoundedWriter:
    def __init__(self, handle):
        self.handle = handle

    def write(self, raw):
        if self.handle.tell() + len(raw) > MAX_ARCHIVE_BYTES:
            raise ValueError('Archive exceeds portability limit')
        return self.handle.write(raw)

    def __getattr__(self, name):
        return getattr(self.handle, name)


def write_bundle(target: Path, data: dict, read_asset, source_identity: str) -> dict:
    """Write a new bundle. On failure only this call's incomplete file is removed."""
    _validate_content(data)
    if not isinstance(source_identity, str) or not source_identity or len(source_identity) > 200:
        raise ValueError('Invalid source identity')
    _json_bytes(source_identity)
    library = _json_bytes(data)
    total = len(library)
    members = {}
    target = Path(target)
    created = False
    try:
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            created = True
            with zipfile.ZipFile(_BoundedWriter(handle), 'w') as archive:
                def append(name, raw):
                    nonlocal total
                    if total > MAX_UNCOMPRESSED_BYTES:
                        raise ValueError('Uncompressed content exceeds portability limit')
                    archive.writestr(_member(name), raw)
                    members[name] = {'size': len(raw), 'sha256': sha256(raw).hexdigest()}

                append('library.json', library)
                for asset in data['assets']:
                    name = _asset_name(asset['id'])
                    raw = read_asset(asset['id'])
                    _validate_image(raw, asset)
                    total += len(raw)
                    append(name, raw)
                manifest = {'format': FORMAT, 'version': VERSION,
                            'created_at': datetime.now(timezone.utc).isoformat(),
                            'source_identity': source_identity, 'counts': _counts(data), 'members': members}
                manifest_raw = _json_bytes(manifest)
                total += len(manifest_raw)
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError('Uncompressed content exceeds portability limit')
                archive.writestr(_member('manifest.json'), manifest_raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    return {'counts': _counts(data), 'limitations': list(BUNDLE_LIMITATIONS)}


def _manifest(value):
    if set(value) != {'format', 'version', 'created_at', 'source_identity', 'counts', 'members'}:
        raise ValueError('Unsupported manifest fields')
    if value['format'] != FORMAT or type(value['version']) is not int or value['version'] != VERSION:
        raise ValueError('Unsupported backup format version')
    if not isinstance(value['created_at'], str):
        raise ValueError('Invalid creation time')
    try:
        created = datetime.fromisoformat(value['created_at'])
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise ValueError('Invalid creation time') from None
    if not isinstance(value['source_identity'], str) or not value['source_identity'] or len(value['source_identity']) > 200:
        raise ValueError('Invalid source identity')
    counts = value['counts']
    if type(counts) is not dict or set(counts) != set(TABLES) or any(type(n) is not int or n < 0 for n in counts.values()):
        raise ValueError('Invalid content counts')
    members = value['members']
    if type(members) is not dict or 'library.json' not in members or len(members) > 10001:
        raise ValueError('Invalid member inventory')
    for name, description in members.items():
        if name != 'library.json' and _ASSET_NAME.fullmatch(name) is None:
            raise ValueError('Unsupported member name')
        limit = MAX_JSON_BYTES if name == 'library.json' else MAX_ASSET_BYTES
        if (type(description) is not dict or set(description) != {'size', 'sha256'}
                or type(description['size']) is not int or not 0 <= description['size'] <= limit
                or not isinstance(description['sha256'], str) or _SHA256.fullmatch(description['sha256']) is None):
            raise ValueError('Invalid member metadata')


def _read_member(archive, handle, info, budget):
    """Check true DEFLATE length, not ZipExtFile's declared-length truncation.

    ZipFile.open supplies its local-name/overlap/header checks. We independently
    bound decompressor output and require the complete single stream to finish.
    """
    with archive.open(info):
        pass
    handle.seek(info.header_offset)
    header = handle.read(30)
    if len(header) != 30:
        raise ValueError('Truncated member header')
    magic, version, flags, method, _, _, crc, compressed, size, name_len, extra_len = struct.unpack('<4s5H3I2H', header)
    if magic != b'PK\x03\x04' or flags != info.flag_bits or method != info.compress_type:
        raise ValueError('Inconsistent member header')
    name = handle.read(name_len)
    extra = handle.read(extra_len)
    if name != info.filename.encode('ascii') or len(extra) != extra_len:
        raise ValueError('Inconsistent member name or header')
    if not flags & 8:
        if size == 0xffffffff or compressed == 0xffffffff:
            # Local ZIP64 sizes are legal even for small streaming writers.
            cursor = 0
            extended = None
            while cursor + 4 <= len(extra):
                field, length = struct.unpack_from('<HH', extra, cursor)
                cursor += 4
                if cursor + length > len(extra):
                    raise ValueError('Invalid ZIP64 member header')
                if field == 1:
                    extended = extra[cursor:cursor + length]
                    break
                cursor += length
            if extended is None:
                raise ValueError('Missing ZIP64 member sizes')
            cursor = 0
            if size == 0xffffffff:
                if len(extended) < cursor + 8:
                    raise ValueError('Missing ZIP64 member size')
                size = struct.unpack_from('<Q', extended, cursor)[0]
                cursor += 8
            if compressed == 0xffffffff:
                if len(extended) < cursor + 8:
                    raise ValueError('Missing ZIP64 compressed size')
                compressed = struct.unpack_from('<Q', extended, cursor)[0]
        if (size, compressed, crc) != (info.file_size, info.compress_size, info.CRC):
            raise ValueError('Inconsistent member lengths or CRC')
    result = bytearray()
    remaining = info.compress_size
    decompressor = zlib.decompressobj(-15) if method == zipfile.ZIP_DEFLATED else None

    def append(raw):
        if len(result) + len(raw) > min(info.file_size, budget):
            raise ValueError('Streamed content exceeds portability limit')
        result.extend(raw)

    while remaining:
        raw = handle.read(min(65536, remaining))
        if not raw:
            raise ValueError('Truncated compressed member')
        remaining -= len(raw)
        if decompressor is None:
            append(raw)
        else:
            pending = raw
            while pending:
                append(decompressor.decompress(pending, min(65536, info.file_size - len(result) + 1, budget - len(result) + 1)))
                if decompressor.unused_data:
                    raise ValueError('Extra compressed member data')
                pending = decompressor.unconsumed_tail
    if decompressor is not None and not decompressor.eof:
        raise ValueError('Incomplete compressed member stream')
    if len(result) != info.file_size or zlib.crc32(result) != info.CRC:
        raise ValueError('Incorrect member length or CRC')
    return bytes(result)


def read_bundle(source: Path) -> tuple[dict, dict, dict]:
    """Validate explicit ZIP members in memory; never extract archive paths."""
    source = Path(source)
    if source.is_symlink():
        raise ValueError('Backup must be a regular file')
    try:
        with source.open('rb') as handle:
            source_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_size > MAX_ARCHIVE_BYTES:
                raise ValueError('Backup is unavailable or exceeds archive limit')
            with zipfile.ZipFile(handle) as archive:
                infos = archive.infolist()
                if not 2 <= len(infos) <= 10002:
                    raise ValueError('Invalid archive inventory')
                entries = {}
                advertised = 0
                for info in infos:
                    name = info.filename
                    mode = info.external_attr >> 16
                    file_type = stat.S_IFMT(mode)
                    if (name in entries or info.orig_filename != name or info.flag_bits & ~(0x000e | 0x0800)
                            or name not in ('manifest.json', 'library.json') and _ASSET_NAME.fullmatch(name) is None
                            or file_type not in (0, stat.S_IFREG) or info.external_attr & 0x10
                            or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                        raise ValueError('Unsafe archive member')
                    limit = MAX_JSON_BYTES if name in ('manifest.json', 'library.json') else MAX_ASSET_BYTES
                    advertised += info.file_size
                    if info.file_size > limit or advertised > MAX_UNCOMPRESSED_BYTES:
                        raise ValueError('Uncompressed content exceeds portability limit')
                    entries[name] = info
                if 'manifest.json' not in entries or 'library.json' not in entries:
                    raise ValueError('Missing required archive member')
                consumed = 0

                def read(name):
                    nonlocal consumed
                    raw = _read_member(archive, handle, entries[name], MAX_UNCOMPRESSED_BYTES - consumed)
                    consumed += len(raw)
                    return raw

                manifest = _json_load(read('manifest.json'))
                _manifest(manifest)
                if set(entries) != {'manifest.json', *manifest['members']}:
                    raise ValueError('Archive inventory does not match manifest')

                def verified(name):
                    expected = manifest['members'][name]
                    if entries[name].file_size != expected['size']:
                        raise ValueError('Member length does not match manifest')
                    raw = read(name)
                    if sha256(raw).hexdigest() != expected['sha256']:
                        raise ValueError('Member checksum mismatch')
                    return raw

                data = _json_load(verified('library.json'))
                _validate_content(data)
                if manifest['counts'] != _counts(data):
                    raise ValueError('Content counts do not match manifest')
                expected_assets = {_asset_name(asset['id']) for asset in data['assets']}
                if set(manifest['members']) != {'library.json', *expected_assets}:
                    raise ValueError('Asset inventory does not match library')
                assets = {}
                for asset in data['assets']:
                    raw = verified(_asset_name(asset['id']))
                    _validate_image(raw, asset)
                    assets[asset['id']] = raw
                return data, assets, manifest
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError, zlib.error):
        raise ValueError('Invalid or unavailable backup archive') from None


def write_html(target: Path, data: dict, include_trash: bool = False) -> dict:
    """Netscape bookmark HTML is a deliberately lossy link export, not backup."""
    from ..urls import validate_url

    if type(include_trash) is not bool:
        raise ValueError('include_trash must be a boolean')
    _validate_content(data)
    selected = [item for item in data['items'] if item['kind'] == 'link'
                and (include_trash or item['deleted_at'] is None)]
    for item in selected:
        try:
            validate_url(item['url'])
        except BookmarkError:
            # IDs are domain-validated; never echo private URL data.
            raise ValueError('Unsafe URL for item ' + item['id']) from None

    counts = _counts(data)
    selected_ids = {item['id'] for item in selected}
    counts.update({
        'exported_links': len(selected),
        'omitted_images': sum(item['kind'] == 'image' for item in data['items']),
        'omitted_trashed_links': sum(item['kind'] == 'link' and item['deleted_at'] is not None
                                     and not include_trash for item in data['items']),
        'omitted_assets': len(data['assets']),
        'omitted_notes': sum(bool(item['notes']) for item in data['items']),
        'omitted_summaries': sum(bool(item['summary']) for item in data['items']),
        'omitted_descriptions': sum(bool(item['description']) and item['id'] not in selected_ids for item in data['items']),
        'omitted_flags': sum(bool(item['favorite'] or item['read_later']) for item in data['items']),
        'omitted_tag_provenance': len(data['item_tags']),
        'omitted_sources': len(data['sources']),
        'omitted_settings': len(data['settings']),
        'flattened_trash': sum(item['deleted_at'] is not None for item in selected),
        'ambiguous_tag_labels': sum(',' in tag for item in selected for tag in json.loads(item['tags'])),
    })
    limitations = [
        'Bookmark HTML is lossy; use a full content backup for restoration.',
        'Image items, asset bytes, notes, saved summaries, source provenance and settings are omitted; exact counts are reported.',
        'Flags, tag provenance/suppression, identities, revisions, ordering metadata and processing history are not preserved.',
        'Tags are comma-separated labels; labels containing commas are ambiguous to browser importers.',
        'Included Trash links lose their Trash state; empty folders are emitted but some browser importers may discard them.',
    ]
    children = {}
    for collection in data['collections']:
        children.setdefault(collection['parent_id'], []).append(collection)
    items = {}
    for item in selected:
        items.setdefault(item['collection_id'], []).append(item)

    target = Path(target)
    created = False
    try:
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            created = True
            writer = _BoundedWriter(handle)

            def line(text):
                writer.write((text + '\n').encode('utf-8'))

            def folder(parent):
                for item in items.get(parent, ()):
                    tags = ','.join(json.loads(item['tags']))
                    attributes = ' HREF="' + escape(item['url'], quote=True) + '"'
                    if tags:
                        attributes += ' TAGS="' + escape(tags, quote=True) + '"'
                    line('<DT><A' + attributes + '>' + escape(item['title'], quote=True) + '</A>')
                    if item['description']:
                        line('<DD>' + escape(item['description'], quote=True) + '</DD>')
                for collection in children.get(parent, ()):
                    line('<DT><H3>' + escape(collection['name'], quote=True) + '</H3>')
                    line('<DL>')
                    folder(collection['id'])
                    line('</DL>')

            line('<!DOCTYPE NETSCAPE-Bookmark-file-1>')
            line('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">')
            line('<TITLE>Bookmarks</TITLE>')
            line('<H1>Bookmarks</H1>')
            line('<DL>')
            folder(None)
            line('</DL>')
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    return {'counts': counts, 'limitations': limitations}
