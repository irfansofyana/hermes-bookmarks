"""Hermes Bookmarks native registration. No storage/inference on import."""
from .host_bindings import register_foundation
from .native_tools import register_tools
from .runtime import bind_runtime, record_startup
from .worker_host import start_enrichment


def register(ctx):
    token = bind_runtime(ctx)
    register_foundation(ctx)
    register_tools(ctx)
    record_startup(token, getattr(ctx, 'profile_name', 'unknown'), start_enrichment(ctx))
