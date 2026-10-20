"""Ordered SQLite migrations. The caller owns one transaction for all steps."""
from sqlite3 import Connection

from .errors import ConfigurationError


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
)


def migrate(connection: Connection) -> None:
    """Never downgrade, partially commit DDL, or rekey existing records."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if not 0 <= version <= len(MIGRATIONS):
        raise ConfigurationError()
    for index in range(version, len(MIGRATIONS)):
        for statement in MIGRATIONS[index]:
            # executescript would implicitly commit and break migration atomicity.
            connection.execute(statement)
        # The interpolated value is our schema index, never a caller-provided value.
        connection.execute(f"PRAGMA user_version = {index + 1}")
