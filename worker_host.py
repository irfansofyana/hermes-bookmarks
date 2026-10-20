"""Only the configured library owner may spawn a host-supervised worker."""
import asyncio
from pathlib import Path

if __package__:
    from .bookmarks.jobs import JobQueue
    from .bookmarks.service import BookmarkService
    from .bookmarks.enrichment import run_worker
    from .bookmarks.extract import extract_text
else:
    from bookmarks.jobs import JobQueue
    from bookmarks.service import BookmarkService
    from bookmarks.enrichment import run_worker
    from bookmarks.extract import extract_text


def start_enrichment(ctx):
    config=getattr(ctx,'get_config',None)
    if not callable(config): return 'configuration_required'
    root=config('library_root',None)
    route=config('enrichment_route',None)
    if not root or not route: return 'configuration_required'
    if not isinstance(root,str) or not Path(root).is_absolute(): return 'configuration_required'
    queue=JobQueue(Path(root))
    try: queue.configure_route(route)
    except ValueError: return 'route_conflict'
    if getattr(ctx,'profile_name',None)!=route['owner_profile']: return 'not_owner'
    spawn=getattr(ctx,'spawn_task',None)
    if not callable(spawn): return 'supervisor_unavailable'
    try: asyncio.get_running_loop()
    except RuntimeError: return 'host_loop_unavailable'
    llm=getattr(ctx,'llm',None)
    if not callable(getattr(llm,'acomplete_structured',None)): return 'inference_unavailable'
    coro=run_worker(queue,BookmarkService(Path(root)),llm,extract_text)
    try: spawn(coro,name='bookmarks-enrichment')
    except Exception:
        coro.close()
        return 'supervisor_unavailable'
    return 'started'
