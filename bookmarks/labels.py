"""Shared Unicode identity and text bounds, with no persistence side effects."""
import unicodedata
from .errors import ValidationError


def validate_text(value, *, max_chars=None, max_bytes=None, nonempty=False):
    if not isinstance(value, str) or '\x00' in value or any('\ud800' <= c <= '\udfff' for c in value):
        raise ValidationError()
    if nonempty and not value:
        raise ValidationError()
    if max_chars is not None and len(value) > max_chars:
        raise ValidationError()
    if max_bytes is not None and len(value.encode('utf-8')) > max_bytes:
        raise ValidationError()
    return value


def normalize_label(value, max_chars):
    validate_text(value)
    display = unicodedata.normalize('NFC', value.strip())
    validate_text(display, max_chars=max_chars, nonempty=True)
    return display, unicodedata.normalize('NFC', display.casefold())
