# Hermes Bookmarks

A standalone bookmark and image-library plugin for Hermes Desktop, Dashboard, and native chat tools.

**Development preview.** Shared capture/search, durable enrichment jobs, and image attachments are implemented. Real isolated Hermes backend checks pass, and the emitted Dashboard UI has been exercised against that backend in light/dark themes at wide/narrow widths. Full M1 acceptance is still pending: the disposable Desktop app could not finish connecting, Dashboard contextual native-chat handoff is unavailable in the inspected SDK, and no real-model call has been authorized. This is not a v1 release or an approved live deployment.

Start with [development status](docs/STATUS.md) and [M1 evidence](docs/verification/m1.md). The [roadmap](docs/ROADMAP.md) distinguishes working foundations from later release requirements.

## Working foundation

- One SQLite library at an explicit absolute backend directory. Profiles that participate must configure the same directory; profile names are not privacy boundaries or cross-machine sync.
- Shared save/get/search service behind native tools and authenticated plugin HTTP routes. Duplicate saves preserve the existing record.
- Individual captures enqueue durable enrichment jobs. The configured owner profile uses the host's supervised task and LLM facade; leases, fresh claim tokens, revisions, retries and cancellation protect persistence. Saved bookmarks do not depend on model success.
- Bounded PNG/JPEG/WebP attachments with backend-owned IDs, authenticated delivery, and previews. These are not yet standalone image library items or note embeds.
- Shared React source emits separate Desktop ESM and Dashboard bundles. Styling follows each host's active theme.
- Desktop Ask Hermes prepares references for an explicit native session and preserves its draft; it never submits. Its actual-host acceptance is outstanding. Dashboard contextual handoff remains visibly unavailable, with no replacement chat UI.

## Native tools

| Tool | Purpose |
| --- | --- |
| `bookmark_save` | Save a URL and queue configured enrichment |
| `bookmark_get` | Read a saved item |
| `bookmark_search` | Search titles/URLs or list the library |
| `bookmark_attachment_add` | Validate and store supplied base64 image bytes |
| `bookmark_attachment_get` | Read owned-attachment metadata and an authenticated API reference |

Native tools are registered through Hermes's public async lane. Owner capture and authenticated async API entry can activate the supervised worker after synchronous registration; the plugin never creates an event loop or a persistent sidecar. The worker survives request completion and is not owned by a browser tab. Missing configuration or capabilities are reported separately from saved-item success.

## Configuration contract

Settings live under `plugins.entries.hermes-bookmarks.settings`:

- `library_root`: an explicit absolute directory outside the installed plugin's code. Use the same value in every participating profile.
- `enrichment_route`: a mapping containing `provider`, `model`, and `owner_profile`. Only the configured owner may initialize the persisted library route; another profile cannot silently change it. The library route is independent of the native chat model.

Use Hermes configuration commands rather than editing active YAML by hand. Credentials and provider trust grants remain owned by Hermes; do not put keys in plugin settings. Full settings editing and model-selection UX are assigned to M3. The health endpoint reports configured state and startup outcomes without exposing the directory; `library_ready: null` means it has not performed a storage-readiness probe.

No active install command is provided for this incomplete preview. Installing the backend, copying a Desktop entry into its discovery root, enabling it, and restarting a live service are deployment actions requiring their own scope.

## Development and verification

Use an isolated Python environment with `requirements-test.txt` and install the pinned Node development dependencies. Then run:

```sh
rtk proxy python -W error -m unittest discover -s tests -q
rtk proxy npm test
rtk proxy node scripts/build-ui.cjs --check
rtk proxy node --check desktop/plugin.js
rtk proxy git diff --check
```

`ui/library.js`, `ui/library.css`, and `ui/native-chat.js` are sources; run `rtk proxy node scripts/build-ui.cjs` after changing them. Commit both emitted bundles. Hermes supplies React and SDK components at runtime; development React/jsdom dependencies are not bundled into the plugin.

`scripts/host_smoke.py` checks a real backend. It defaults to GET-only checks (owner activation can resume previously queued automatic work), takes an explicit origin and token-file path, rejects redirects/credential URLs, and requires `--allow-write` for synthetic capture/image operations. Use a disposable Hermes home; the script does not configure, restart, install into, or fabricate responses for a host. Never commit token files or real user data.

## Product direction and remaining milestones

The intended v1 includes Raindrop-inspired grid/list organization, nested collections, tags, favorites/read-later, rich notes with inline images, standalone image items, configuration controls, import and export, and native agent workflows. Bulk imports default to no enrichment unless explicitly opted in; note images are not automatically analyzed. These capabilities remain on the roadmap and are not implied by the foundation preview.

Read the [specification](docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md), [roadmap](docs/ROADMAP.md), and [M1 plan](docs/superpowers/plans/2026-10-20-m1-native-foundation.md). Future sessions start with [AGENTS.md](AGENTS.md) and [STATUS](docs/STATUS.md), not with old conversation summaries.

The official Hermes documentation is the integration contract. `irfansofyana/hermes-blogwatcher` is the owner's requested reference for packaging and host adapters, not a backend copied unchanged. No core patches, private imports, custom chat renderer, separate credential store, catalog listing or release is part of this preview.
