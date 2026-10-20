"""SQLite persistence; connections are short-lived and never profile-scoped."""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from uuid import uuid4

from .errors import ConfigurationError, NotFoundError, StorageError
from .migrations import migrate


def item_from_row(row):
    data = dict(row)
    try: data['tags'] = json.loads(data['tags'])
    except (ValueError, KeyError): raise StorageError() from None
    return data


class Storage:
    def __init__(self, data_root: Path):
        if not isinstance(data_root, Path) or not data_root.is_absolute():
            raise ConfigurationError()
        try:
            data_root.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError):
            raise ConfigurationError() from None
        self.database_path = data_root / "bookmarks.sqlite3"
        with self._transaction(write=True) as connection:
            migrate(connection)

    @contextmanager
    def _transaction(self, *, write=False):
        connection = None
        try:
            # BEGIN IMMEDIATE serializes writers (including concurrent migrations).
            # A bounded busy wait handles ordinary cross-profile process contention.
            connection = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        except sqlite3.Error:
            raise StorageError() from None
        finally:
            if connection is not None:
                connection.close()

    def save_link(self, url: str, title: str, *, enrichment_settings=None) -> dict:
        with self._transaction(write=True) as connection:
            connection.execute(
                "INSERT INTO items(id, url, title) VALUES (?, ?, ?) ON CONFLICT(url) DO NOTHING",
                (str(uuid4()), url, title),
            )
            # Select inside the same transaction, including on the duplicate path.
            # Never REPLACE: it could rekey the row or overwrite manual metadata.
            row = connection.execute("SELECT * FROM items WHERE url = ?", (url,)).fetchone()
            if enrichment_settings is not None and row['enrichment_status'] == 'not_started':
                from .jobs import validate_settings
                settings = validate_settings(enrichment_settings)
                job_id = str(uuid4())
                connection.execute('INSERT INTO jobs(id,item_id,revision,settings) VALUES(?,?,?,?)',
                                   (job_id,row['id'],row['revision'],settings))
                connection.execute("UPDATE items SET enrichment_status='pending',enrichment_job_id=? WHERE id=?",(job_id,row['id']))
                row = connection.execute('SELECT * FROM items WHERE id=?',(row['id'],)).fetchone()
            return item_from_row(row)

    def get(self, item_id: str) -> dict:
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                raise NotFoundError()
            return item_from_row(row)

    def search(self, query: str, limit: int, offset: int) -> dict:
        # One quoted FTS5 phrase: operators/column selectors/prefixes are literal
        # tokens, never executable query syntax. unicode61 still tokenizes words.
        match = '"' + query.replace('"', '""') + '"'
        source = "items"
        parameters = ()
        if query:
            source += " JOIN items_fts ON items_fts.rowid = items.rowid WHERE items_fts MATCH ?"
            parameters = (match,)
        with self._transaction() as connection:
            # One read transaction gives count + page the same SQLite snapshot.
            total = connection.execute("SELECT count(*) FROM " + source, parameters).fetchone()[0]
            # Python integers need not fit SQLite's signed 64-bit OFFSET binding.
            items = []
            if offset < total:
                rows = connection.execute(
                    "SELECT items.* FROM " + source + " ORDER BY items.rowid ASC LIMIT ? OFFSET ?",
                    (*parameters, limit, offset),
                ).fetchall()
                items = [item_from_row(row) for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
