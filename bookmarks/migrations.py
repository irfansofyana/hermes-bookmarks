"""Ordered SQLite migrations. The caller owns one transaction for all steps."""
from sqlite3 import Connection

from .errors import ConfigurationError
from .library_schema import upgrade_library
from .imports.schema import upgrade_imports
from .portability.schema import upgrade_content
from .portability.operations_schema import upgrade_operations


MIGRATIONS = (
    (
        """CREATE TABLE items (
            id TEXT PRIMARY KEY NOT NULL,
            url TEXT NOT NULL UNIQUE COLLATE BINARY,
            title TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            enrichment_status TEXT NOT NULL DEFAULT 'not_started'
        )""",
    ),
    (
        """CREATE VIRTUAL TABLE items_fts USING fts5(
            title, url, content='items', content_rowid='rowid', tokenize='unicode61'
        )""",
        """CREATE TRIGGER items_fts_insert AFTER INSERT ON items BEGIN
            INSERT INTO items_fts(rowid, title, url) VALUES (new.rowid, new.title, new.url);
        END""",
        """CREATE TRIGGER items_fts_delete AFTER DELETE ON items BEGIN
            INSERT INTO items_fts(items_fts, rowid, title, url)
            VALUES ('delete', old.rowid, old.title, old.url);
        END""",
        """CREATE TRIGGER items_fts_update AFTER UPDATE ON items BEGIN
            INSERT INTO items_fts(items_fts, rowid, title, url)
            VALUES ('delete', old.rowid, old.title, old.url);
            INSERT INTO items_fts(rowid, title, url) VALUES (new.rowid, new.title, new.url);
        END""",
        "INSERT INTO items_fts(items_fts) VALUES ('rebuild')",
    ),
    (
        "ALTER TABLE items ADD COLUMN summary TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE items ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE items ADD COLUMN enrichment_job_id TEXT",
        "CREATE TABLE library_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        """CREATE TABLE jobs (
            id TEXT PRIMARY KEY, item_id TEXT NOT NULL, revision INTEGER NOT NULL,
            settings TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
            worker TEXT, token TEXT, expires REAL, attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT, result TEXT, UNIQUE(item_id, revision))""",
        "CREATE INDEX jobs_claim ON jobs(state)",
    ),
    (
        """CREATE TABLE assets (
            id TEXT PRIMARY KEY, mime_type TEXT NOT NULL,
            size INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL)
        """,
    ),
    (
        "INSERT INTO library_config(key,value) VALUES('library_id',lower(hex(randomblob(16))))",
        """CREATE TABLE chat_threads (
            id TEXT PRIMARY KEY NOT NULL, profile TEXT NOT NULL,
            session_id TEXT NOT NULL, title TEXT NOT NULL, model TEXT NOT NULL,
            created_at REAL NOT NULL DEFAULT ((julianday('now')-2440587.5)*86400.0),
            UNIQUE(profile,session_id))""",
        "CREATE INDEX chat_threads_profile ON chat_threads(profile,created_at DESC)",
    ),
    (upgrade_library,),
    (
        "ALTER TABLE items ADD COLUMN deleted_at REAL",
        "CREATE INDEX items_deleted_collection ON items(deleted_at,collection_id)",
        "ALTER TABLE capture_operations RENAME TO capture_operations_old",
        """CREATE TABLE capture_operations(operation_key TEXT PRIMARY KEY NOT NULL,payload_hash TEXT NOT NULL,
            item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,accepted_revision INTEGER NOT NULL CHECK(accepted_revision>=1),
            outcome TEXT NOT NULL CHECK(outcome IN ('created','duplicate','trashed_duplicate')))""",
        "INSERT INTO capture_operations SELECT * FROM capture_operations_old",
        "DROP TABLE capture_operations_old",
    ),
    (upgrade_imports,),
    (upgrade_content,),
    (upgrade_operations,),
)


def migrate(connection: Connection) -> None:
    """Never downgrade, partially commit DDL, or rekey existing records."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if not 0 <= version <= len(MIGRATIONS):
        raise ConfigurationError()
    for index in range(version, len(MIGRATIONS)):
        for statement in MIGRATIONS[index]:
            # executescript would implicitly commit and break migration atomicity.
            if callable(statement):
                statement(connection)
            else:
                connection.execute(statement)
        # The interpolated value is our schema index, never a caller-provided value.
        connection.execute(f"PRAGMA user_version = {index + 1}")
