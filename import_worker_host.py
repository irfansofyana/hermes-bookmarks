"""Host-supervised import worker metadata; no inference dependency or custom loop."""
import asyncio
from time import monotonic


def ensure(contexts, roots, states, lock, *, create_queue):
    try:asyncio.get_running_loop()
    except RuntimeError:return
    with lock:
        for token,(ctx,profile) in contexts.items():
            if profile!=getattr(ctx,'profile_name','unknown') or roots.get(token) is None:continue
            state=states.setdefault(token,{'task':None,'result':'not_started','retry_after':0})
            if state['task'] is not None:continue
            if monotonic()<state['retry_after']:continue
            spawn=getattr(ctx,'spawn_task',None)
            if not callable(spawn):state['result']='supervisor_unavailable';continue
            if __package__:from .bookmarks.imports.runner import run_imports
            else:from bookmarks.imports.runner import run_imports
            coro=None
            try:
                queue=create_queue(roots[token]);coro=run_imports(queue)
                task=spawn(coro,name='bookmarks-imports')
            except Exception:
                if coro is not None:coro.close()
                state.update(result='storage_unavailable',retry_after=monotonic()+30);continue
            state.update(task=task,result='started')
            def finished(completed,_token=token,_state=state):
                error=None if completed.cancelled() else completed.exception()
                with lock:
                    if states.get(_token) is not _state or _state['task'] is not completed:return
                    _state.update(task=None,result='worker_stopped' if completed.cancelled() else 'worker_failed' if error else 'worker_stopped',retry_after=monotonic()+30)
            task.add_done_callback(finished)
