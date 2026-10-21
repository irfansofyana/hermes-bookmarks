"""Schema six: a forward-only upgrade in the caller's write transaction."""
import json
import time
from uuid import uuid4

from .errors import StorageError, ValidationError
from .labels import normalize_label


def upgrade_library(connection):
    # Validate first; invalid legacy data must never be silently discarded.
    legacy = connection.execute('SELECT rowid,* FROM items ORDER BY rowid').fetchall()
    labels = {}
    try:
        for row in legacy:
            values = json.loads(row['tags'])
            if not isinstance(values, list) or len(values) > 20:
                raise ValueError()
            normalized = [(value, *normalize_label(value, 80)) for value in values]
            labels[row['id']] = normalized
    except (ValueError, TypeError, ValidationError):
        raise StorageError() from None
    connection.execute('''CREATE TABLE collections(
        id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL, identity TEXT NOT NULL,
        parent_id TEXT REFERENCES collections(id) ON DELETE RESTRICT,
        revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=1),
        created_at REAL NOT NULL, updated_at REAL NOT NULL)''')
    connection.execute('CREATE UNIQUE INDEX collections_root ON collections(identity) WHERE parent_id IS NULL')
    connection.execute('CREATE UNIQUE INDEX collections_siblings ON collections(parent_id,identity) WHERE parent_id IS NOT NULL')
    for trigger in ('items_fts_insert', 'items_fts_delete', 'items_fts_update'):
        connection.execute('DROP TRIGGER ' + trigger)
    connection.execute('DROP TABLE items_fts')
    connection.execute('''CREATE TABLE items_next(
        id TEXT PRIMARY KEY NOT NULL, url TEXT UNIQUE COLLATE BINARY, title TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=1),
        enrichment_status TEXT NOT NULL DEFAULT 'not_started', summary TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]', enrichment_job_id TEXT,
        kind TEXT NOT NULL DEFAULT 'link' CHECK(kind IN ('link','image')),
        description TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
        collection_id TEXT REFERENCES collections(id) ON DELETE RESTRICT,
        favorite INTEGER NOT NULL DEFAULT 0 CHECK(favorite IN (0,1)),
        read_later INTEGER NOT NULL DEFAULT 0 CHECK(read_later IN (0,1)),
        primary_asset_id TEXT REFERENCES assets(id) ON DELETE RESTRICT,
        created_at REAL NOT NULL DEFAULT ((julianday('now')-2440587.5)*86400.0),
        updated_at REAL NOT NULL DEFAULT ((julianday('now')-2440587.5)*86400.0),
        enrichment_generation INTEGER NOT NULL DEFAULT 1 CHECK(enrichment_generation>=1),
        CHECK((kind='link' AND url IS NOT NULL AND primary_asset_id IS NULL) OR
              (kind='image' AND url IS NULL AND primary_asset_id IS NOT NULL)))''')
    now = time.time()
    connection.execute('''INSERT INTO items_next(rowid,id,url,title,revision,enrichment_status,summary,tags,
        enrichment_job_id,enrichment_generation,created_at,updated_at)
        SELECT rowid,id,url,title,revision,enrichment_status,summary,tags,enrichment_job_id,revision,?,? FROM items''', (now, now))
    connection.execute('DROP TABLE items')
    connection.execute('ALTER TABLE items_next RENAME TO items')
    connection.execute('CREATE INDEX items_collection ON items(collection_id)')
    connection.execute('ALTER TABLE jobs ADD COLUMN generation INTEGER NOT NULL DEFAULT 1')
    connection.execute('UPDATE jobs SET generation=revision')
    connection.execute('''CREATE TABLE tags(id TEXT PRIMARY KEY NOT NULL,label TEXT NOT NULL,identity TEXT NOT NULL UNIQUE)''')
    connection.execute('''CREATE TABLE item_tags(
        item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
        tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
        manual INTEGER NOT NULL DEFAULT 0 CHECK(manual IN (0,1)),
        generated INTEGER NOT NULL DEFAULT 0 CHECK(generated IN (0,1)),
        suppressed INTEGER NOT NULL DEFAULT 0 CHECK(suppressed IN (0,1)),
        label TEXT,
        PRIMARY KEY(item_id,tag_id))''')
    connection.execute('''CREATE TABLE item_assets(
        item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
        asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
        role TEXT NOT NULL CHECK(role IN ('primary','attachment')),
        PRIMARY KEY(item_id,asset_id))''')
    connection.execute("CREATE UNIQUE INDEX item_primary ON item_assets(item_id) WHERE role='primary'")
    connection.execute('''CREATE TABLE capture_operations(
        operation_key TEXT PRIMARY KEY NOT NULL,payload_hash TEXT NOT NULL,
        item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
        accepted_revision INTEGER NOT NULL CHECK(accepted_revision>=1),
        outcome TEXT NOT NULL CHECK(outcome IN ('created','duplicate')))''')
    for item_id, values in labels.items():
        for original, display, key in values:
            connection.execute('INSERT INTO tags(id,label,identity) VALUES(?,?,?) ON CONFLICT(identity) DO NOTHING', (uuid4().hex, display, key))
            tag = connection.execute('SELECT id FROM tags WHERE identity=?', (key,)).fetchone()[0]
            # V5 accepted aliases within one item. Keep its original tags JSON
            # untouched, while one normalized membership uses the first label.
            # Metadata-only edits retain that cache; an explicit tag change or
            # generated replacement rebuilds it under the new identity rules.
            connection.execute('''INSERT INTO item_tags(item_id,tag_id,generated,label) VALUES(?,?,1,?)
                ON CONFLICT(item_id,tag_id) DO NOTHING''', (item_id,tag,original))
    columns = ('title','url','description','notes','summary','tags')
    names = ','.join(columns)
    connection.execute("CREATE VIRTUAL TABLE items_fts USING fts5(" + names + ",content='items',content_rowid='rowid',tokenize='unicode61')")
    new = ','.join('new.'+name for name in columns)
    old = ','.join('old.'+name for name in columns)
    connection.execute(f'CREATE TRIGGER items_fts_insert AFTER INSERT ON items BEGIN INSERT INTO items_fts(rowid,{names}) VALUES(new.rowid,{new}); END')
    connection.execute(f"CREATE TRIGGER items_fts_delete AFTER DELETE ON items BEGIN INSERT INTO items_fts(items_fts,rowid,{names}) VALUES('delete',old.rowid,{old}); END")
    connection.execute(f"CREATE TRIGGER items_fts_update AFTER UPDATE ON items BEGIN INSERT INTO items_fts(items_fts,rowid,{names}) VALUES('delete',old.rowid,{old}); INSERT INTO items_fts(rowid,{names}) VALUES(new.rowid,{new}); END")
    connection.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise StorageError()
