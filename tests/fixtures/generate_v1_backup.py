"""Manually regenerate the frozen synthetic archive using the pinned old writer.

Run with ``rtk proxy python tests/fixtures/generate_v1_backup.py`` from this
repository. No installed plugin, user input, provider, credentials or services.
Only the pinned Git tree, temporary synthetic library and the two v1 fixture
outputs are touched. This generator is not run by the test suite.
"""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

PINNED_WRITER = '85161559263424c4bb4e0ecc66309a78043733ca'
FIXTURES = Path(__file__).resolve().parent
REPOSITORY = FIXTURES.parent.parent


def main():
    archived = subprocess.run(
        ['rtk', 'proxy', 'git', 'archive', '--format=tar', PINNED_WRITER],
        cwd=REPOSITORY, check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix='bookmarks-v1-writer-', dir=os.environ['TMPDIR']) as folder:
        scratch = Path(folder)
        writer = scratch / 'writer'
        writer.mkdir()
        with tarfile.open(fileobj=BytesIO(archived)) as tree:
            tree.extractall(writer, filter='data')
        # A subprocess prevents current bookmarks modules from entering the old
        # writer's import cache. Its source root is the pinned extracted tree.
        generated = scratch / 'frozen-v1.zip'
        program = r'''
from pathlib import Path
import json
import sys
from bookmarks.service import BookmarkService
from bookmarks.assets import AssetStore
from bookmarks.jobs import JobQueue
from bookmarks.portability.store import PortabilityStore
from bookmarks.tags import merge_generated

root = Path(sys.argv[1]); destination = Path(sys.argv[2])
route = {'provider':'synthetic-provider','model':'frozen-v1-model','owner_profile':'synthetic-v1-owner'}
JobQueue(root).configure_route(route)
s = BookmarkService(root, enrichment_settings=route)
folder = s.collection_create('Synthetic Café')
s.collection_create('Empty synthetic child', folder['id'])
asset = AssetStore(root).store_image((Path('tests/fixtures/tiny.png')).read_bytes(), 'image/png')
link = s.capture(url='https://example.org/frozen-v1', title='Synthetic frozen legacy link',
    notes='Synthetic personal note; no real personal input.', tags=['Manual'],
    collection_id=folder['id'], attachment_ids=[asset['id']], favorite=True)['item']
with s._storage._transaction(write=True) as c:
    merge_generated(c, link['id'], ['Generated','Suppressed'])
    c.execute('UPDATE items SET summary=?,processing_history=? WHERE id=?',
        ('Frozen legacy summary', '["failed"]', link['id']))
s.update(link['id'], link['revision'], {'remove_tags':['Suppressed']})
s.capture(kind='image', primary_asset_id=asset['id'], title='Synthetic frozen image',
    operation_key='00000000-0000-4000-8000-000000000001')
trash = s.save_link('https://example.org/frozen-v1-trash', 'Synthetic Trash')
s.trash(trash['id'], trash['revision'])
with s._storage._transaction(write=True) as c:
    c.execute('INSERT INTO content_sources(item_id,source_id,source,locator,imported_summary,source_text) VALUES(?,?,?,?,?,?)',
        (link['id'],'synthetic-old-record','Synthetic fixture','row-1','Imported synthetic summary','Synthetic imported text'))
    c.execute("INSERT INTO library_config VALUES('synthetic_secret_omit','DO NOT COPY')")
artifact = PortabilityStore(s._storage).export_create(
    request_id='00000000-0000-4000-8000-000000000002')
assert artifact['format_version'] == 1
raw = (root / 'portability' / (artifact['id'] + '.ready')).read_bytes()
assert b'DO NOT COPY' not in raw
destination.write_bytes(raw)
'''
        environment = {key: value for key, value in os.environ.items()
                       if key not in {'PYTHONPATH', 'PYTHONHOME'}}
        subprocess.run(['rtk', 'proxy', sys.executable, '-c', program,
                        str(scratch / 'synthetic-library'), str(generated)],
                       cwd=writer, env=environment, check=True)
        raw = generated.read_bytes()
        (FIXTURES / 'frozen-writer-v1.zip').write_bytes(raw)
        provenance = {
            'writer_commit': PINNED_WRITER,
            'generator': 'generate_v1_backup.py',
            'synthetic_only': True,
            'fixture_sha256': sha256(raw).hexdigest(),
            'writer_source_sha256': {
                path: sha256((writer / path).read_bytes()).hexdigest()
                for path in ('bookmarks/portability/content.py', 'bookmarks/portability/archive.py',
                             'bookmarks/portability/store.py')},
            'method': 'Pinned git archive; isolated subprocess runs old BookmarkService and PortabilityStore.export_create; frozen output bytes are copied unchanged.',
        }
        (FIXTURES / 'frozen-writer-v1.provenance.json').write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(json.dumps(provenance, sort_keys=True))


if __name__ == '__main__':
    main()
