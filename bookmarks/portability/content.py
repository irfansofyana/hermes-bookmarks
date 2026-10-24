"""Exact content-version dispatch; new full-fidelity snapshots are version two.

The frozen version-one validator remains in content_v1. Codec readers must pass
an already-validated manifest version; no field-based sniffing or coercion.
"""
from ..errors import ValidationError
from . import content_v1, content_v2
from .content_v1 import MAX_INTEGER, MAX_JSON_BYTES, LIMITS, ROUTE_FIELDS, STATES, TABLES, empty
from .content_v2 import FIELDS


def _implementation(version):
    if type(version) is not int or version not in (1, 2):
        raise ValidationError()
    return content_v1 if version == 1 else content_v2


def snapshot(connection, version=2) -> dict:
    return _implementation(version).snapshot(connection)


def validate_content(data, version=2) -> None:
    _implementation(version).validate_content(data)


def restore_content(connection, data, version=2) -> None:
    _implementation(version).restore_content(connection, data)
