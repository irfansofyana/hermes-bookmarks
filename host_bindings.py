"""Plugin-owned public-surface probes and native foundation registration."""
import json


def foundation_status(raw_args: str = "", **kwargs) -> str:
    """Read-only slash command; no library, inference, or context transfer yet."""
    return json.dumps({
        "ok": True, "plugin": "hermes-bookmarks",
        "stage": "foundation_preview", "library_ready": False,
    })


def register_foundation(ctx):
    """Use the documented command adapter without acquiring resources."""
    ctx.register_command(
        name="bookmarks-status", handler=foundation_status,
        description="Show Hermes Bookmarks foundation preview status (read-only).",
    )


def describe_capabilities(
    *, host: str | None = None, renderer: object | None = None,
    mounted: bool = False, context: object | None = None,
) -> dict[str, bool]:
    """Describe injected public surfaces, not successful host operations.

    Python cannot discover a renderer. Its adapter must pass the public SDK
    handle and assert its own mount; absent/unknown hosts fail closed. A true
    handoff flag only identifies a candidate API lane: Task 4 must still check
    the exact session, live composer acknowledgement, and draft safety.
    No probe calls a host action or reads a reactive atom.
    """
    caps = {
        "custom_chat": False,
        "native_chat_embedding": False,
        "native_navigation": False,
        "native_chat_handoff": False,
        "json_transport_surface": False,
        "binary_transport_surface": False,
        "llm_completion_surface": False,
        "llm_vision_input_surface": False,
        "auxiliary_task_surface": False,
        "cleanup_surface": False,
        "supervised_task_surface": False,
        "shared_storage": False,
        "native_attachments": False,
    }
    if host not in ("desktop", "dashboard", "backend"):
        return caps
    if context is not None:
        llm = getattr(context, "llm", None)
        caps["llm_completion_surface"] = callable(getattr(llm, "complete", None))
        caps["llm_vision_input_surface"] = callable(getattr(llm, "complete_structured", None))
        caps["auxiliary_task_surface"] = callable(getattr(context, "register_auxiliary_task", None))
        caps["cleanup_surface"] = callable(getattr(context, "on_unload", None))
        caps["supervised_task_surface"] = callable(getattr(context, "spawn_task", None))
    if mounted is not True or renderer is None:
        return caps
    if host == "dashboard":
        caps["json_transport_surface"] = callable(getattr(renderer, "fetchJSON", None))
        caps["binary_transport_surface"] = callable(getattr(renderer, "authedFetch", None))
        return caps
    if host != "desktop":
        return caps
    public_host = getattr(renderer, "host", None)
    caps["native_navigation"] = callable(getattr(public_host, "navigate", None))
    composer = getattr(public_host, "composer", None)
    state = getattr(public_host, "state", None)
    caps["native_chat_handoff"] = bool(
        caps["native_navigation"]
        and callable(getattr(public_host, "openSession", None))
        and callable(getattr(composer, "getDraft", None))
        and callable(getattr(composer, "insertText", None))
        and callable(getattr(getattr(state, "focusedStoredSessionId", None), "get", None))
        and callable(getattr(getattr(state, "focusedSessionOwner", None), "get", None))
    )
    return caps
