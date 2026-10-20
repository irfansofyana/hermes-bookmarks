"""Shared save/get/search contract, independent of any host/session/worker."""
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

    Construction creates/migrates only that root. No default is discovered from
    HOME, Hermes profiles, or the current working directory. Saves are durable
    but enrichment is not yet run/scheduled: new items say ``not_started``.
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

    def search(self, query: str, limit: int = 50, offset: int = 0) -> dict:
        _validate_text(query)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError()
        if type(offset) is not int or offset < 0:
            raise ValidationError()
        return self._storage.search(query.strip(), limit, offset)
