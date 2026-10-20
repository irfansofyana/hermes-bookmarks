"""Explicit plugin-owned bridge between native registration and path-loaded API.

No host internals, credentials or profile-local defaults. All participating
profiles must configure the same absolute settings.library_root. Registration
publishes only configuration; storage is opened lazily on a user operation.
"""
from pathlib import Path
from threading import RLock
import importlib
import sys

if __package__:
    from .bookmarks.errors import ConfigurationError
    from .bookmarks.service import BookmarkService
else:
    from bookmarks.errors import ConfigurationError
    from bookmarks.service import BookmarkService

BRIDGE_NAME = 'hermes_bookmarks_runtime_bridge'
_lock = RLock()
_roots = {}


def bind_runtime(ctx):
    getter = getattr(ctx, 'get_config', None)
    cleanup = getattr(ctx, 'on_unload', None)
    if not callable(getter) or not callable(cleanup):
        return
    raw = getter('library_root', None)
    root = None
    if raw is not None:
        if not isinstance(raw, str) or not raw or '\x00' in raw or not Path(raw).is_absolute():
            raise ConfigurationError()
        root = Path(raw).resolve()
    module = sys.modules[__name__]
    token = object()
    with _lock:
        existing = sys.modules.get(BRIDGE_NAME)
        if existing is not None and existing is not module:
            # One plugin generation owns the bridge. Share its registration,
            # never silently replace a live generation/context.
            return existing.bind_runtime(ctx)
        configured = {v for v in _roots.values() if v is not None}
        if root is not None and configured and root not in configured:
            raise ConfigurationError()
        _roots[token] = root
        sys.modules[BRIDGE_NAME] = module
    def release():
        with _lock:
            _roots.pop(token, None)
            if not _roots and sys.modules.get(BRIDGE_NAME) is module:
                sys.modules.pop(BRIDGE_NAME, None)
    cleanup(release)


def get_service():
    with _lock:
        bridge = sys.modules.get(BRIDGE_NAME)
        if bridge is not None and bridge is not sys.modules[__name__]:
            return bridge.get_service()
        roots = {v for v in _roots.values() if v is not None}
        if bridge is None or len(roots) != 1:
            raise ConfigurationError()
        root = next(iter(roots))
    return BookmarkService(root)


def dispatch(name, params):
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]:
        return bridge.dispatch(name, params)
    module = importlib.import_module('.native_tools', __package__) if __package__ else importlib.import_module('native_tools')
    return module.execute(name, params, get_service)
