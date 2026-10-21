"""Typed service errors with public-safe messages, never raw input/SQLite text."""


class BookmarkError(Exception):
    code = "bookmark_error"
    message = "The bookmark operation could not be completed."

    def __init__(self):
        super().__init__(self.message)


class ConfigurationError(BookmarkError):
    code = "configuration_error"
    message = "An accessible, explicit absolute library root and supported schema are required."


class ValidationError(BookmarkError):
    code = "invalid_argument"
    message = "Arguments must have valid types and values; limit is 1–100 and offset is nonnegative."


class InvalidURLError(ValidationError):
    code = "invalid_url"
    message = "Provide a valid HTTP(S) URL without credentials, whitespace, or control characters."


class NotFoundError(BookmarkError):
    code = "not_found"
    message = "The requested bookmark was not found."


class StorageError(BookmarkError):
    code = "storage_error"
    message = "Library storage is unavailable; check access, database health, and SQLite FTS5 support."


class StorageBusyError(StorageError):
    """Internal retry classification; public code/message remain storage_error."""
