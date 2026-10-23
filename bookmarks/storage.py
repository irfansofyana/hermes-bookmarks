"""SQLite persistence; connections are short-lived and never profile-scoped."""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3


from .errors import ConfigurationError, NotFoundError, StorageError, StorageBusyError
from .migrations import migrate


def item_from_row(row, connection):
    data = dict(row)
    try: data['tags'] = json.loads(data['tags'])
    except (ValueError, KeyError): raise StorageError() from None
    data.pop('enrichment_generation', None)
    data['favorite'] = bool(data['favorite'])
    data['read_later'] = bool(data['read_later'])
    from .tags import effective_tags
    data['tag_details'] = effective_tags(connection, data['id'])
    data['attachments'] = [dict(asset) for asset in connection.execute('''
        SELECT ia.asset_id,ia.role,a.mime_type,a.size,a.width,a.height
        FROM item_assets ia JOIN assets a ON a.id=ia.asset_id WHERE ia.item_id=?
        ORDER BY CASE ia.role WHEN 'primary' THEN 0 ELSE 1 END,ia.rowid''', (data['id'],))]
    data['imported_sources'] = [dict(source) for source in connection.execute('SELECT source_id,source,locator,imported_summary,source_text FROM content_sources WHERE item_id=? ORDER BY rowid',(data['id'],))]
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
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        except sqlite3.Error as error:
            # Extended SQLite busy/locked codes share their primary low byte.
            if (getattr(error, 'sqlite_errorcode', 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise StorageBusyError() from None
            raise StorageError() from None
        finally:
            if connection is not None:
                connection.close()

    def save_link(self, url: str, title: str, *, enrichment_settings=None) -> dict:
        from .items import ItemStore
        return ItemStore(self).capture(url=url,title=title,enrichment_settings=enrichment_settings)['item']

    def get(self, item_id: str) -> dict:
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                raise NotFoundError()
            return item_from_row(row, connection)

    def search(self, query: str, limit: int, offset: int) -> dict:
        from .queries import search
        with self._transaction() as connection:
            return search(connection,query,limit,offset,view='all',collection_id=None,tags=())
