"""Hermes Bookmarks foundation preview. Registration only; no storage on import."""
from .host_bindings import register_foundation


def register(ctx):
    """Keep the native entrypoint independent of the path-loaded HTTP adapter."""
    register_foundation(ctx)
