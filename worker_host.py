"""Only the configured library owner may spawn a host-supervised worker."""
import asyncio
from pathlib import Path

if __package__:
    from .bookmarks.jobs import JobQueue
    from .bookmarks.service import BookmarkService
    from .bookmarks.enrichment import run_worker
    from .bookmarks.extract import extract_text
    from .bookmarks.errors import StorageError, ConflictError, ValidationError
else:
    from bookmarks.jobs import JobQueue
    from bookmarks.service import BookmarkService
    from bookmarks.enrichment import run_worker
    from bookmarks.extract import extract_text
    from bookmarks.errors import StorageError, ConflictError, ValidationError


def start_enrichment(ctx, *, on_task=None):
    config=getattr(ctx,'get_config',None)
    if not callable(config): return 'configuration_required'
    root=config('library_root',None)
    route=config('enrichment_route',None)
    if not root or not route: return 'configuration_required'
    if not isinstance(root,str) or not Path(root).is_absolute(): return 'configuration_required'
    if not isinstance(route,dict) or not route.get('owner_profile'): return 'configuration_required'
    if getattr(ctx,'profile_name',None)!=route['owner_profile']: return 'not_owner'
    try:
        queue=JobQueue(Path(root))
        if __package__:
            from .bookmarks.settings import SettingsStore
        else:
            from bookmarks.settings import SettingsStore
        current=SettingsStore(queue.storage).seed_route(route)
        if current['settings']['owner_profile']!=getattr(ctx,'profile_name',None):return 'not_owner'
    except (ValueError,ConflictError,ValidationError):return 'route_conflict'
    except StorageError: return 'storage_unavailable'
    spawn=getattr(ctx,'spawn_task',None)
    if not callable(spawn): return 'supervisor_unavailable'
    try: asyncio.get_running_loop()
    except RuntimeError: return 'host_loop_unavailable'
    llm=getattr(ctx,'llm',None)
    if not callable(getattr(llm,'acomplete_structured',None)): return 'inference_unavailable'
    try: service=BookmarkService(Path(root))
    except StorageError: return 'storage_unavailable'
    coro=run_worker(queue,service,llm,extract_text)
    try: task=spawn(coro,name='bookmarks-enrichment')
    except Exception:
        coro.close()
        return 'supervisor_unavailable'
    if on_task is not None: on_task(task)
    return 'started'
