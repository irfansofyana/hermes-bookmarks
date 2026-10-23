"""Public, explicit-root facade shared by native tools and authenticated HTTP."""
from pathlib import Path

from .errors import ValidationError
from .storage import Storage
from .urls import validate_url


def _validate_text(value: str, *, nonempty=False) -> None:
    if not isinstance(value, str) or (nonempty and not value):
        raise ValidationError()
    # SQLite UTF-8 binding rejects lone surrogates; NUL truncates FTS tokens.
    if "\x00" in value or any("\ud800" <= c <= "\udfff" for c in value):
        raise ValidationError()


class BookmarkService:
    """An explicit installation-owned absolute Path is required.

    Construction creates/migrates only that root. Captures are durable without
    a model. Optional enrichment settings admit link jobs atomically; an empty
    route is intentionally queued for a configuration-required worker result.
    Standalone images never enter the URL-extraction queue.
    """

    def __init__(self, data_root: Path, *, enrichment_settings=None):
        self._storage = Storage(data_root)
        self._enrichment_settings = enrichment_settings

    def save_link(self, url: str, title: str = "") -> dict:
        validate_url(url)
        _validate_text(title)
        return self._storage.save_link(url, title, enrichment_settings=self._enrichment_settings)

    def get(self, item_id: str) -> dict:
        _validate_text(item_id, nonempty=True)
        return self._storage.get(item_id)

    def capture(self, *, kind='link', url=None, title='', description='', notes='', collection_id=None,
                tags=(), favorite=False, read_later=False, primary_asset_id=None, attachment_ids=(), operation_key=None):
        from .items import ItemStore
        return ItemStore(self._storage).capture(kind=kind, url=url, title=title, description=description, notes=notes,
            collection_id=collection_id, tags=tags, favorite=favorite, read_later=read_later,
            primary_asset_id=primary_asset_id, attachment_ids=attachment_ids, operation_key=operation_key,
            enrichment_settings=self._enrichment_settings)

    def capture_status(self, operation_key):
        from .items import ItemStore
        return ItemStore(self._storage).capture_status(operation_key)

    def update(self, item_id, expected_revision, changes):
        from .items import ItemStore
        return ItemStore(self._storage).update(item_id, expected_revision, changes)

    def note_update(self, item_id, expected_revision, text, mode='replace'):
        from .items import ItemStore
        return ItemStore(self._storage).note_update(item_id, expected_revision, text, mode)

    def trash(self, item_id, expected_revision):
        from .trash import transition
        return transition(self._storage,item_id,expected_revision,deleted=True)

    def restore(self, item_id, expected_revision):
        from .trash import transition
        return transition(self._storage,item_id,expected_revision,deleted=False)

    def import_preview(self, records=None, html=None, options=None):
        from .imports.preview import ImportStore
        return ImportStore(self._storage).preview(records,html,options)

    def import_start(self, preview_id, input_digest, request_id):
        from .imports.preview import ImportStore
        return ImportStore(self._storage).start(preview_id,input_digest,request_id)

    def import_job_get(self, job_id, limit=50, offset=0):
        from .imports.preview import ImportStore
        return ImportStore(self._storage).get(job_id,limit,offset)

    def import_request_get(self, request_id):
        from .imports.preview import ImportStore
        return ImportStore(self._storage).request_get(request_id)

    def import_job_cancel(self, job_id):
        from .imports.preview import ImportStore
        return ImportStore(self._storage).cancel(job_id)

    def export_create(self, format='bundle', include_trash=False, request_id=None):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).export_create(format,include_trash,request_id)

    def export_get(self, request_id):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).export_get(request_id)

    def export_read(self, artifact_id, offset=0):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).export_read(artifact_id,offset)

    def backup_upload_create(self, size, digest, request_id):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).upload_create(size,digest,request_id)

    def backup_upload_chunk(self, upload_id, offset, content_base64):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).upload_chunk(upload_id,offset,content_base64)

    def backup_preview(self, upload_id):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).backup_preview(upload_id)

    def backup_restore(self, preview_id, input_digest, request_id):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).backup_restore(preview_id,input_digest,request_id)

    def backup_restore_get(self, request_id):
        from .portability.store import PortabilityStore
        return PortabilityStore(self._storage).backup_restore_get(request_id)

    def identity(self):
        with self._storage._transaction() as connection:
            row = connection.execute("SELECT value FROM library_config WHERE key='library_id'").fetchone()
            return {'library_id': row['value']}

    def search(self, query='', limit=50, offset=0, *, view='all', collection_id=None, tags=()):
        from .queries import search
        with self._storage._transaction() as connection:
            return search(connection, query, limit, offset, view=view, collection_id=collection_id, tags=tags)

    def counts(self):
        from .queries import counts
        with self._storage._transaction() as connection:
            return counts(connection)

    def tag_list(self, query='', limit=50, offset=0):
        from .queries import tag_list
        with self._storage._transaction() as connection:
            return tag_list(connection, query, limit, offset)

    def collection_list(self, limit=50, offset=0, *, parent_id=None, query=''):
        from .collections import CollectionStore
        return CollectionStore(self._storage).list(limit, offset, parent_id=parent_id, query=query)

    def collection_create(self, name, parent_id=None):
        from .collections import CollectionStore
        return CollectionStore(self._storage).create(name, parent_id)

    def collection_update(self, collection_id, expected_revision, changes):
        from .collections import CollectionStore
        return CollectionStore(self._storage).update(collection_id, expected_revision, changes)

    def collection_delete(self, collection_id, expected_revision, contents_policy):
        from .collections import CollectionStore
        return CollectionStore(self._storage).delete(collection_id, expected_revision, contents_policy)
