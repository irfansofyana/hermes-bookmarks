# Hermes Bookmarks

A standalone bookmark and image-library plugin for Hermes Desktop, Dashboard, and native chat tools.

**Development preview.** The library-first workspace now includes nested collections, tags, grid/list views, metadata/notes/image dialogs, revision-safe edits, durable capture receipts, and collapsible Hermes-backed chat. Chat has focused controller/transport and both-emitted-client React tests; authenticated real-host binding routes pass. Connected Desktop and real-provider acceptance remain open; see current verification rather than treating unit tests as installed-host proof. Synthetic real-provider verification and PR publication are approved; merge/release/live installation are not. This is not a v1 release or an approved live deployment.

Start with [development status](docs/STATUS.md) and [M1 evidence](docs/verification/m1.md), including the [final review fix pass](docs/verification/final-review-fixes.md). Current workspace evidence is tracked in [library-first verification](docs/verification/library-first-workspace.md), with the [preserved final review and author fixes](docs/verification/library-first-revision-review-fixes.md). The [roadmap](docs/ROADMAP.md) distinguishes working foundations from later release requirements.

## Working foundation

- One SQLite library at an explicit absolute backend directory. Profiles that participate must configure the same directory; profile names are not privacy boundaries or cross-machine sync.
- Shared save/get/search service behind native tools and authenticated plugin HTTP routes. Duplicate saves preserve the existing record.
- Individual link captures enqueue durable enrichment jobs. The configured owner profile uses the host's supervised task and LLM facade; leases, fresh claim tokens, revisions, retries and cancellation protect persistence. Saved bookmarks do not depend on model success.
- Bounded PNG/JPEG/WebP images with backend-owned IDs, authenticated delivery, previews, standalone image items and item attachments. Standalone image analysis and inline note embeds remain unavailable.
- Library-first browsing offers nested collections, whole-library counts, tags and AND filters, grid/list views and pagination. Add/Edit dialogs keep description, personal Markdown notes and AI summaries separate. Stale revisions reject without overwriting; uncertain captures are reconciled using their original operation key.
- Recoverable Trash keeps notes/assets and rejects stale revisions. Normalized JSON records and Netscape bookmark HTML support immutable preview, explicit Start, accurate durable results, cancellation, and job-ID inspection after reload. Imports skip existing (including trashed) URLs and default to **no AI enrichment**. Supported source metadata is separate from generated summaries; unsupported fields are warned, not silently claimed as preserved.
- **Data** opens versioned ZIP content backup or explicitly lossy bookmark HTML export. Generate and Download are separate, authenticated transfers use bounded chunks and SHA-256, and uploaded backups require preview plus explicit confirmation. Full restore is atomic and only accepts an empty content library; target identity survives and jobs/routes never reactivate automatically. Backups are unencrypted. See [portability verification](docs/verification/export-and-restore.md) for current gates.
- Shared React source emits separate Desktop ESM and Dashboard bundles. Styling follows each host's active theme.
- Chat is initially closed and opens explicitly. Collapse preserves session, draft and running output; Stop is a separate action. A plugin-owned conversation panel stays alongside the library (or in the in-plugin Chat view on narrow screens), backed by dedicated Hermes-managed sessions. It supports explicit Send, streaming, safe Markdown, tool summaries, real plans, approvals/clarification, Stop, model choice for new conversations and profile-scoped history. This replaces the legacy draft handoff; no ordinary focused chat is adopted. See [chat verification](docs/verification/in-plugin-chat.md) for current evidence and remaining host gates.

## Native tools

| Tool | Purpose |
| --- | --- |
| `bookmark_save` | Capture a link/image with metadata and an optional idempotency key; links queue configured enrichment |
| `bookmark_get` | Read a saved item |
| `bookmark_search` | Search saved metadata/notes/tags and combine collection, tag and smart-view filters |
| `bookmark_attachment_add` | Validate and store supplied base64 image bytes |
| `bookmark_attachment_get` | Read owned-attachment metadata and an authenticated API reference |
| `bookmark_update` | Atomically update metadata, tags and image associations at an expected revision |
| `bookmark_note_update` | Replace or explicitly append personal Markdown notes |
| `bookmark_capture_status` | Read a capture receipt and current item without retrying the write |
| `bookmark_collection_list` | Page collections or search with ancestor paths |
| `bookmark_collection_create` | Create a collection under an optional parent |
| `bookmark_collection_update` | Rename or move with revision/cycle checks |
| `bookmark_collection_delete` | Delete a collection with an explicit non-destructive contents policy |
| `bookmark_tag_list` | Page normalized effective tags with whole-library counts |
| `bookmark_library_identity` | Read the installation-owned shared library identity |
| `bookmark_counts` | Read All, Inbox, Favorites and Read later counts |
| `bookmark_delete` / `bookmark_restore` | Revision-checked recoverable trash/restore |
| `bookmark_import_preview` | Validate supplied normalized records or bookmark HTML without writing items |
| `bookmark_import_start` | Admit an immutable preview using its digest and a stable request ID |
| `bookmark_import_request_get` | Read admission by request ID without replaying a write |
| `bookmark_job_get` / `bookmark_job_cancel` | Inspect durable import results or cancel remaining rows |
| `bookmark_export_create` / `bookmark_export_get` | Generate a versioned content backup or lossy HTML; reconcile the exact request without replay |
| `bookmark_export_read` | Read at most 32 KiB of an authenticated owned artifact; returns IDs/metadata, never server paths |
| `bookmark_backup_upload_create` / `bookmark_backup_upload_chunk` | Admit/resume a supplied backup using its digest and exact bounded offsets |
| `bookmark_backup_preview` | Verify the sealed archive/domain without changing library content |
| `bookmark_backup_restore` / `bookmark_backup_restore_get` | Explicit atomic empty-target restore and durable read-only request reconciliation |

Native tools are registered through Hermes's public async lane. Owner capture and authenticated async API entry can activate the supervised worker after synchronous registration; the plugin never creates an event loop or a persistent sidecar. The worker survives request completion and is not owned by a browser tab. Missing configuration or capabilities are reported separately from saved-item success.

## Configuration contract

Settings live under `plugins.entries.hermes-bookmarks.settings`:

- `library_root`: an explicit absolute directory outside the installed plugin's code. Use the same value in every participating profile.
- `enrichment_route`: a mapping containing `provider`, `model`, and `owner_profile`. Only the configured owner may initialize the persisted library route; another profile cannot silently change it. The library route is independent of the native chat model.

Use Hermes configuration commands rather than editing active YAML by hand. Credentials and provider trust grants remain owned by Hermes; do not put keys in plugin settings. Full library settings editing and background-enrichment model-selection UX are assigned to M3; the chat picker already supports model choice for new conversations. The health endpoint reports configured state and startup outcomes without exposing the directory; `library_ready: null` means it has not performed a storage-readiness probe.

No active install command is provided for this incomplete preview. Installing the backend, copying a Desktop entry into its discovery root, enabling it, and restarting a live service are deployment actions requiring their own scope.

## Development and verification

Use an isolated Python environment with `requirements-test.txt` and install the pinned Node development dependencies. Node regression tests also execute a standard-library-only Python storage probe; supply `python3` or set `BOOKMARKS_TEST_PYTHON`. Then run:

```sh
rtk proxy python -W error -m unittest discover -s tests -q
rtk proxy npm test
rtk proxy node scripts/build-ui.cjs --check
rtk proxy node --check desktop/plugin.js
rtk proxy git diff --check
```

The `ui/` library/chat JavaScript and scoped CSS files are sources; run `rtk proxy node scripts/build-ui.cjs` after changing them. Commit both emitted bundles. Hermes supplies React and SDK components at runtime. Marked is bundled only as a Markdown lexer, with its full license embedded; an allowlisted React renderer rejects raw HTML, executable links and automatic remote image loads. esbuild/React/jsdom are development dependencies, not separate agent runtimes.

`scripts/host_smoke.py` checks a real backend. It defaults to GET-only checks (owner activation can resume previously queued automatic work), takes an explicit origin and token-file path, rejects redirects/credential URLs, and requires `--allow-write` for synthetic capture/image operations. Use a disposable Hermes home; the script does not configure, restart, install into, or fabricate responses for a host. Never commit token files or real user data.

## Product direction and remaining milestones

The intended v1 includes Raindrop-inspired grid/list organization, nested collections, tags, favorites/read-later, rich notes with inline images, standalone image items, configuration controls, import and export, and native agent workflows. Bulk imports default to no enrichment unless explicitly opted in; note images are not automatically analyzed. The organization workspace, standalone image records and Markdown notes are implemented in this revision. Recoverable trash and normalized/HTML imports are implemented; [trash/import verification](docs/verification/trash-and-imports.md) records real-host/browser/restart evidence and limits. HTML/content export and empty-target restore are now implemented locally with real authenticated host/native/browser/restart evidence; completed reviews, author fixes and publication status are recorded in [portability verification](docs/verification/export-and-restore.md). Rich-text/inline images, visual AI, settings and all-target acceptance remain on the roadmap.

Read the [specification](docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md), [roadmap](docs/ROADMAP.md), and [M1 plan](docs/superpowers/plans/2026-10-20-m1-native-foundation.md). Future sessions start with [AGENTS.md](AGENTS.md) and [STATUS](docs/STATUS.md), not with old conversation summaries.

The current revision follows the approved [workspace design](docs/superpowers/specs/2026-10-21-library-first-workspace-design.md) and [implementation plan](docs/superpowers/plans/2026-10-21-library-first-workspace.md). Follow [workspace evidence](docs/verification/library-first-workspace.md) for tested, protocol-only and blocked acceptance rows.

The official Hermes documentation is the integration contract. `irfansofyana/hermes-blogwatcher` is the owner's requested reference for packaging and host adapters, not a backend copied unchanged. The requested plugin-owned chat UI must use public integration contracts underneath. No core patches, private imports, copied internal UI, new agent runtime, separate credential store, catalog listing or release is part of this preview.
