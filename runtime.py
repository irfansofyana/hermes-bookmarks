"""Explicit plugin-owned bridge between native registration and path-loaded API.

No host internals, credentials or profile-local defaults. All participating
profiles must configure the same absolute settings.library_root. Registration
publishes explicit settings and supervised worker state; import has no storage
or inference side effects.
"""
from pathlib import Path
from threading import RLock
from time import monotonic
import importlib
import sys

if __package__:
    from .bookmarks.errors import BookmarkError, ConfigurationError, StorageError
    from .bookmarks.service import BookmarkService
else:
    from bookmarks.errors import BookmarkError, ConfigurationError, StorageError
    from bookmarks.service import BookmarkService

BRIDGE_NAME = 'hermes_bookmarks_runtime_bridge'
_lock = RLock()
_roots = {}
_startups = {}
_contexts = {}
_workers = {}
_import_states = {}
_retry_after = {}
_RESTART_COOLDOWN = 30


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
        _contexts[token] = (ctx, getattr(ctx, "profile_name", "unknown"))
        sys.modules[BRIDGE_NAME] = module
    def release():
        with _lock:
            _roots.pop(token, None)
            _startups.pop(token, None)
            _contexts.pop(token, None)
            _workers.pop(token, None)
            _import_states.pop(token,None)
            _retry_after.pop(token, None)
            if not _roots and sys.modules.get(BRIDGE_NAME) is module:
                sys.modules.pop(BRIDGE_NAME, None)
    cleanup(release)
    return token


def record_startup(token,profile,result):
    bridge=sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]:
        return bridge.record_startup(token,profile,result)
    with _lock:
        if token in _roots: _startups[token]={'profile':profile,'result':result}


def _track_worker(token,profile,task):
    # Task ownership/cancellation stays with ctx.spawn_task. Only observe its
    # public completion and clear metadata for this exact registration/attempt.
    with _lock:
        if token not in _contexts: return
        _workers[token]=task
    def finished(completed):
        if completed.cancelled(): result='worker_stopped'
        else:
            error=completed.exception()  # Observe exceptions; never expose text.
            result='storage_unavailable' if isinstance(error,StorageError) else 'worker_failed' if error is not None else 'worker_stopped'
        with _lock:
            if _workers.get(token) is not completed: return
            _workers.pop(token,None)
            if token not in _contexts: return
            record_startup(token,profile,result)
            _retry_after[token]=monotonic()+_RESTART_COOLDOWN
    task.add_done_callback(finished)


def start_registered_enrichment(token):
    bridge=sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]: return bridge.start_registered_enrichment(token)
    with _lock:
        entry=_contexts.get(token)
        if entry is None: return 'configuration_required'
        ctx,profile=entry
        if profile != getattr(ctx,'profile_name','unknown'): return 'not_owner'
        running=_workers.get(token)
        if running is not None and not running.done(): return 'started'
        module=importlib.import_module('.worker_host',__package__) if __package__ else importlib.import_module('worker_host')
        result=module.start_enrichment(ctx,on_task=lambda task:_track_worker(token,profile,task))
        record_startup(token,profile,result)
        if result=='started': _retry_after.pop(token,None)
        elif result=='storage_unavailable': _retry_after[token]=monotonic()+_RESTART_COOLDOWN
        return result


def ensure_enrichment():
    """Activate only from a host-owned async entry, never create an event loop.

    Registration is synchronous in the isolated plugin host. Its public async
    tool/API lane supplies the persistent loop on first use. Only the original
    context's profile may activate it; spawn_task retains unload ownership.
    """
    bridge=sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]: return bridge.ensure_enrichment()
    with _lock:
        for token,(ctx,profile) in _contexts.items():
            if profile != getattr(ctx,'profile_name','unknown'): continue
            result=_startups.get(token,{}).get('result')
            if result!='host_loop_unavailable':
                if result not in {'storage_unavailable','worker_failed','worker_stopped'}: continue
                if monotonic() < _retry_after.get(token,0): continue
            start_registered_enrichment(token)


def ensure_imports():
    bridge=sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]:return bridge.ensure_imports()
    module=importlib.import_module('.import_worker_host',__package__) if __package__ else importlib.import_module('import_worker_host')
    queue_module=importlib.import_module('.bookmarks.imports.runner',__package__) if __package__ else importlib.import_module('bookmarks.imports.runner')
    storage_module=importlib.import_module('.bookmarks.storage',__package__) if __package__ else importlib.import_module('bookmarks.storage')
    return module.ensure(_contexts,_roots,_import_states,_lock,create_queue=lambda root:queue_module.ImportQueue(storage_module.Storage(root)))


def get_status():
    bridge=sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]: return bridge.get_status()
    with _lock:
        configured=len({root for root in _roots.values() if root is not None})==1
        return {'library_configured':configured,'library_ready':None if configured else False,
                'enrichment_startups':[dict(value) for value in _startups.values()]}


def get_service():
    with _lock:
        bridge = sys.modules.get(BRIDGE_NAME)
        if bridge is not None and bridge is not sys.modules[__name__]:
            return bridge.get_service()
        roots = {v for v in _roots.values() if v is not None}
        if bridge is None or len(roots) != 1:
            raise ConfigurationError()
        root = next(iter(roots))
    queue_module = importlib.import_module('.bookmarks.jobs', __package__) if __package__ else importlib.import_module('bookmarks.jobs')
    return BookmarkService(root, enrichment_settings=queue_module.JobQueue(root).route())


def dispatch(name, params):
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]:
        return bridge.dispatch(name, params)
    module = importlib.import_module('.native_tools', __package__) if __package__ else importlib.import_module('native_tools')
    return module.execute(name, params, get_service)


def chat_operation(operation, params=None):
    """Resolve profile in the request's context, never the process environment."""
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]:
        return bridge.chat_operation(operation, params)
    try:
        with _lock:
            owners = {profile for ctx, profile in _contexts.values()
                      if profile != 'unknown' and profile == getattr(ctx, 'profile_name', 'unknown')}
        if len(owners) != 1:
            raise ConfigurationError()
        profile = owners.pop()
        module = importlib.import_module('.bookmarks.chat', __package__) if __package__ else importlib.import_module('bookmarks.chat')
        store = module.ChatStore(get_service()._storage.database_path.parent)
        if operation == 'identity':
            result = store.identity(profile)
        elif operation == 'threads':
            result = store.threads(profile, params)
        elif operation == 'bind':
            result = store.bind(profile, params)
        else:
            raise ValueError('Unknown chat operation')
        return {'ok': True, 'result': result}
    except BookmarkError as exc:
        return {'ok': False, 'error': {'code': exc.code, 'message': exc.message}}
    except (ValueError, TypeError):
        return {'ok': False, 'error': {'code': 'invalid_argument', 'message': 'Invalid conversation binding or pagination.'}}


def asset_operation(operation, *args):
    bridge = sys.modules.get(BRIDGE_NAME)
    if bridge is not None and bridge is not sys.modules[__name__]:
        return bridge.asset_operation(operation, *args)
    try:
        module = importlib.import_module('.bookmarks.assets', __package__) if __package__ else importlib.import_module('bookmarks.assets')
        store = module.AssetStore(get_service()._storage.database_path.parent)
        if operation not in {'store_image','get_asset','read_asset','preview'}:
            raise ValueError('Unsupported operation')
        return {'ok': True, 'result': getattr(store, operation)(*args)}
    except LookupError:
        return {'ok': False, 'error': {'code': 'not_found', 'message': 'Asset not found.'}}
    except BookmarkError as exc:
        return {'ok': False, 'error': {'code': exc.code, 'message': exc.message}}
    except (ValueError, OSError):
        return {'ok': False, 'error': {'code': 'invalid_argument', 'message': 'Image data or owned asset reference is invalid.'}}
