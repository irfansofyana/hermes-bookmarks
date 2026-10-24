# Task 1 — public host boundaries and evidence

Checked 2026-10-20. This is a **foundation preview**, not M1 acceptance, a release, or proof of installed UI compatibility. Only the package registration was exercised through the real isolated Hermes validator/doctor. Python direct-router and Node SDK-double tests are not real host authentication or rendered UI evidence.

## Exact targets and provenance

| Target | Recorded value | Evidence / limit |
| --- | --- | --- |
| Backend CLI | `Hermes Agent v0.22.2 (2026.9.24)`, stable; install stamp `baseVersion: 0.22.2`, `commit: d923a5eb487a17c0a68801bba9ef0f56c81040a8`, `dirty: false` | `rtk proxy hermes --version`, read-only install-stamp metadata, and `rtk git rev-parse HEAD`. Call this revision **H** below. |
| Source used by the session's Python | Managed runtime workspace, not the source checkout path | SHA-256 byte comparisons matched H for `hermes_cli/{plugins.py,plugins_manifest.py,plugin_host.py,plugins_cmd_catalog.py}`. This is limited file parity, not a claim that the entire managed tree has git metadata. |
| Desktop source | H, `apps/desktop/package.json` version `0.0.0` | This placeholder is not a released Desktop compatibility version. `@hermes/plugin-sdk` exports inspected at H.[6][7] |
| Existing Desktop build | `apps/desktop/dist/hermes-build.json`: schema `1`, Linux x64; build Node `26.7.0`; `stampClock: 2026-10-15T14:53:27.228Z`; source hash `e7aca8d29fbb7fa77d3b10157c51b347e925086eae513be14a3075bdba390acf`; output hash `56fc4c8bf6a729fb2908e32e837e15fa00e098137b312de5eefa0cf16edeb70d` | Metadata only. No assumption that this older build contains every SDK export in H; no live renderer queried, installed, or restarted. |
| Dashboard source / SDK | H; `SDK_CONTRACT_VERSION = "1.1.0"` in `web/src/plugins/registry.ts:106` | Declared source version, not a running-server probe.[9][10] |
| Owner reference | `irfansofyana/hermes-blogwatcher`, HEAD `1b6f32afc1a509437a9bc57a078bea99b3d69dab`, manifest version `0.2.0` | Public clone in scratch; inspected files listed below.[16] |
| Test runtimes | CPython `3.14.7` (host and isolated harness), CPython `3.11.14` (isolated harness), Node `v24.18.0` | Executed, not inferred. No support range for Hermes was extrapolated from these tests. |

The live documentation index was fetched and used to locate the plugin guide, Desktop SDK, Dashboard extension guide, Plugin LLM Access, and Web Dashboard guide.[1][2][3]

The relevant installed Markdown and public-export source were also read; the live HTML extraction omits some longer sections, so absence from that extraction is **not** evidence of missing capability.[4][5][6]

Evidence levels below: **D** = documented; **S** = inspected pinned source; **U** = exercised using public-shaped doubles or standalone router; **V** = real official isolated validator/doctor; **H-run** = actual Desktop/Dashboard integration. There is **no H-run evidence** in this task.

## Host compatibility matrix

All pinned source locators in this table refer to H unless a different revision is stated. Python plugin context is the common backend lane; renderer SDKs are different interfaces, not interchangeable.[4][6]

| Capability | Host | Public symbol / route and source locator | Version / level | Boundary and fallback |
| --- | --- | --- | --- | --- |
| Native navigation and session identity | Desktop | `host.navigate`, `host.openSession(storedSessionId, options)`, `host.state.focusedStoredSessionId`, `host.state.focusedSessionOwner`; SDK `index.ts:695-702,755,958` | H; D/S/U | A connection-qualified owner matters, not only a profile string. Candidate navigation lane exists; explicit target and actual composer mount remain Task 4 checks. No automatic send.[6][7] |
| Context / draft handoff and composition | Desktop | `host.composer.getDraft`, `insertText`, `setDraft`; `sdk/composer.ts:55-116`; guide “Composer” and “Arbitration”. `PANES_AREA` / `ROUTES_AREA` for plugin library layout | H; D/S/U | Draft API is public and session-addressed; mutations require a mounted surface and return false if absent; explicit-session getDraft may instead return persisted text and is not proof of a live composer. Prefer acknowledged insertion with explicit append consent, not replacing an existing draft. No atomic compare-and-set is exposed in the inspected composer contract; read-then-set alone does not prove race safety. No public reusable chat-component export was found in the canonical export list; do not copy one. Task 4 must prove safe handoff and preserved library state.[6][7][8] |
| Native navigation / context | Dashboard | Documented native `/chat?resume=<id>&profile=<name>` URL; Web Dashboard “Managing multiple profiles” and “Chat”. SDK exposes React, hooks, `api`, and fetch helpers, not a composer API | H / SDK 1.1.0; D/S | **Basic native-chat resume navigation exists.** No documented session-bound editable-draft/context API or exported chat component was found in the inspected SDK/registry. A resume link is not an Ask Hermes draft handoff or proof that library/draft state survives. Context-bearing Ask Hermes is an acceptance blocker pending a supported contract; no terminal keystroke injection, DOM interception, or custom chat.[9][19][21] |
| Host-owned inference and vision | Desktop backend | `ctx.llm.complete`, `complete_structured` / async twins; typed image input; `ctx.register_auxiliary_task`; Plugin LLM Access “API surface”, “Task-routed auxiliary calls”, “Trust gate” | H; D/S/U (shape only) | One-shot inference is not native agent chat. Host owns credentials, retries, fallback and vision routing. Shape detection does not grant trust, prove a compatible model, or incur a call. No real text/vision call made.[5][11][15] |
| Host-owned inference and vision | Dashboard backend | Same Python `ctx.llm` facade; API loader imports `plugin_api.py` under a separate name; `web_server_dashboard.py:1021-1042` | H; D/S | A separately imported route module does not acquire the native plugin context. Future inference needs a documented explicit bridge/lifecycle; do not duplicate credentials or assume import-time globals share context. Task 1 health is stateless. Profile-scoped aux settings do not yet prove one stable installation-wide enrichment route.[14][15] |
| Shared installation library root | Desktop/backend | `plugins.plugin_storage.plugin_data_dir(name)` and `plugin_db`; `plugin_storage.py:27-45`. `ctx.get_config` is plugin/profile settings | H; D/S | Built-in storage follows the active profile and creates that profile's directory. It is **not** the required shared library. Task 2 takes an explicit installation-owned `data_root: pathlib.Path`; unresolved root must be a configuration error, with no profile-local fallback. Task 1 neither resolves nor creates storage.[11][12][17] |
| Shared installation library root | Dashboard/backend | Same explicit service root, independent of per-request profile; HTTP profile scope documented by `_plugin_route_secret_scope`, `web_server_dashboard.py:812-823` | H; S | A request profile selects execution scope, not library ownership. `ctx.storage`/browser storage is only client preferences, not the shared database. No automatic root-discovery or shared-root grant is claimed.[6][12][14] |
| Lifecycle / work ownership | Desktop | Renderer `ctx.onDispose`, scoped timers/listeners, registration disposers; common Python context has `on_unload`, `spawn_task` at `plugins.py:409-428` | H; renderer D/S; backend S/U | Renderer lifecycle is documented. Python method docstrings show cleanup/supervised asyncio tasks, but the inspected public guide does not describe a dedicated persistent service runner or these methods in detail. No worker starts here; source-level presence is not proof of cold-start service ownership, running loop, shutdown completion, or durable scheduling. Task 5 must establish a documented lifecycle before using it.[6][11][17] |
| Lifecycle / work ownership | Dashboard | Backend imported at mount; hosted APIs buffered; `web_server_dashboard.py:826-852,869-896`; same Python context source surfaces | H; S/U | HTTP handlers must not start unowned workers or depend on an open tab. No browser lifetime can own durable enrichment. Backend process ownership remains unexercised.[11][14] |
| Attachments / authenticated transport | Desktop | `ctx.rest(path, {upload:{filename,contentType?,bytes},...})`; guide “Calling it from the plugin”; `COMPOSER_AREAS.attachments` / `ComposerAttachmentProvider` extension point | H; D/S | Upload transport exists in the public contract; this does not prove durable bookmark asset delivery or stable native-chat attachment refs. `ctx.socket` is a no-op on OAuth remotes; keep bounded polling. Do not reach into a native bridge or persist client paths. Task 6 must prove owned, authenticated upload/read.[6] |
| Attachments / authenticated transport | Dashboard | `SDK.fetchJSON`, `SDK.authedFetch`, `buildWsUrl`, `buildWsAuthParam`; `sdk.d.ts:44-77,140-149`, registry exposure | H / SDK 1.1.0; D/S/U | Use host helpers for JSON and binary transport, not copied tokens or custom auth. No asset upload/download exists in this preview. Presence of `authedFetch` is not native composer attachment support.[9][10] |
| Authorization / approvals | Desktop | `ctx.rest` scopes `/api/plugins/<id>` and rejects traversal; shared backend `auth_middleware`, OAuth gate and plugin-enabled request gate | H; D/S | Keep real backend auth enabled. Renderer authority is **not a security sandbox**, and profile names are not authorization boundaries. No custom credentials/auth. Actual remote unauthorized request and native approval behavior remain untested.[6][13] |
| Authorization / approvals | Dashboard | `GET /api/plugins/hermes-bookmarks/health` under real host middleware; `web_server.py:670-751`; enabled import gate at `web_server_dashboard.py:791-804` | H; D/S; health router U; registration V | Direct ASGI router tests prove response and HTTP methods only: they intentionally have **no host auth gate**. They cannot prove unauthenticated rejection. No writes/bulk approval needed in Task 1; later mutations require genuine host authorization/approval, never a model-supplied boolean.[13][14] |

## Plugin-owned capability helper

`describe_capabilities()` returns only booleans and defaults every value to false. It never imports host internals, discovers a renderer through module globals, reads drafts/atoms, invokes inference, opens storage, or calls a transport. Optional public-shaped handles follow the preflight ruling:

- `host='desktop', renderer=<SDK object with .host>, mounted=True` probes navigation plus exact-session composer/identity exports. `native_chat_handoff=True` means **candidate API surface**, not a completed/live handoff. The mounted assertion belongs to the caller; a missing renderer or absent export fails closed.
- `host='dashboard', renderer=<window SDK>, mounted=True` probes `fetchJSON` / `authedFetch`. It does not manufacture a composer or infer one from `api`; the inspected API client has session/workspace helpers, not an editable-draft handoff.[20]
- `host='backend', context=<registered ctx>` probes completion, structured-image-input, auxiliary-task and lifecycle method **surfaces**. Those booleans do not prove permission, a working route/model, actual image support, or a running worker. A supplied backend context may remain available with no mounted renderer; frontend capabilities still stay false.
- `custom_chat` is always false by policy. `native_chat_embedding`, `shared_storage`, and `native_attachments` stay false: no accepted embedded component, configured installation root, or owned attachment implementation exists here. These are preview limits, not assertions that all future hosts lack them.
- Unknown host labels stay all-false even if handed convincing-looking objects. Probe inputs are trusted adapter handles, not user-provided grants.

The positive tests deliberately use callables that fail if executed; missing composer and binary exports are covered. No backend source import is needed for unit tests.

## Reference inspected, not copied wholesale

At reference SHA `1b6f32afc1a509437a9bc57a078bea99b3d69dab`, read `plugin.yaml`, `__init__.py`, `dashboard/{manifest.json,plugin_api.py}`, `scripts/build-ui.cjs`, and `summary_bridge.py`.[16]

Reusable packaging: native `register(ctx)`, Dashboard IIFE + SDK globals, explicit API namespace, separate Desktop ESM delivery, and distinct API import namespace. Reference build lines 12-45 emit two different loader contracts; its `host.navigate('/')` is only navigation, not bookmark context transfer. Reference bridge binds the exact registered context and releases its plugin-owned alias on unload; it is not needed for this stateless preview. Do not copy its CLI-backed/read-only tools, per-profile summary state, boolean consent semantics, or dependency assumptions into the shared writable library.[16]

## Package and checks exercised

- `plugin.yaml`: `hermes-bookmarks` `0.1.0`, no native tools/hooks or privileged capabilities requested. No guessed minimum Hermes version and no copied runtime dependency list. FastAPI is already part of the checked Dashboard host; test dependencies are a separate harness.[17][19]
- `__init__.py` delegates only to the focused native adapter: `/bookmarks-status` returns the preview health JSON. No storage config is necessary, no file/worker/network operation runs on import or registration.
- `dashboard/manifest.json` points to a **present** `dist/index.js` and `plugin_api.py`. The tiny hand-written preview does not start Task 3's shared library UI/build. It says capture/search/Ask Hermes are unavailable, uses host React and semantic markup, and does not alter theme or chat.
- Sole HTTP route is read-only `GET /health`; the documented host prefix would expose `/api/plugins/hermes-bookmarks/health`. That namespace and 405 for unsupported mutation methods were exercised only in the direct-router harness, not a mounted real host.
- Before dependency installation, checked existing `hermes`, Python 3.11/3.14, Node, source tests, installed Desktop artifacts, and local vitest/playwright availability. Chose official isolated CLI validation and standalone unit environments; no need to launch a renderer or Docker host in this task.
- `rtk proxy python -m unittest discover -s tests -p test_host_bindings.py -v`: required initial **RED** `ModuleNotFoundError: No module named 'host_bindings'`, then GREEN; final capability suite has 3 tests.
- Isolated CPython 3.11.14 and 3.14.7 `-W error -m unittest discover -s tests -v`: **6 tests passed** on each. Node 24.18.0 `rtk proxy node --test tests/test_preview.cjs`: **1 passed**. Harness top-level pins are FastAPI 0.133.1, HTTPX 0.28.1, PyYAML 6.0.3; no plugin runtime dependency installation is claimed.
- Official installed commands `rtk proxy hermes plugins validate . --json` and `rtk proxy hermes plugins doctor . --ci`: **exit 0**, isolated synthetic HOME/HERMES_HOME under scratch and credential-free child environment. Validator reports `ok: true`, no warnings, `register() ran in isolation`, no core rebinds, and host-ready isolation. These are package checks, not host UI/auth acceptance.[18]
- The launcher automatically prepared dependencies **inside the scratch data root** for this validator; this was not a live plugin install or service restart. No `--install-deps` was used because the package declares none. The real source checkout remained tracked-clean afterward.
- CI runs equivalent Python 3.11/3.14 and Node 24.18.0 suites with read-only repository permissions and no credentials for unit tests. No push was authorized, so no GitHub job was run or claimed green. The UI deterministic build check belongs to Task 3 when that script exists.

Full RED/GREEN outputs, files, self-review, and next work are in the local coordination report `.superpowers/sdd/2026-10-20-m1-native-foundation/task-1-report.md` (intentionally gitignored by the SDD directory). This document is the committed compatibility evidence.

## Acceptance blockers and next boundaries

1. **Dashboard contextual Ask Hermes:** documented resume navigation is available, but a supported editable-draft/context API was not found. Keep Ask Hermes disabled until that gap is resolved or the owner revises acceptance. Do not claim complete handoff from a bare resume link.
2. **Desktop actual-host handoff:** source APIs exist, but the existing build's exports/mount/session/draft preservation have not been exercised. No atomic conditional replace is promised; future safe append behavior needs explicit consent and adversarial tests.
3. **Shared storage:** Task 2 must use the explicit installation-owned root contract, not `plugin_data_dir`. The preview has no database and must not be represented as capture functionality.
4. **Lifecycle and stable enrichment route:** source-shaped probes are not a documented persistent runner or proof of one library execution route across profile processes. Task 5 must settle ownership, trust, stable routing, leases and cold-start behavior without private imports.
5. **Auth, approvals and assets:** actual native-host unauthorized requests, remote binary delivery, native attachments, browser visuals and native Markdown/tool/stop/history/approval flows remain unexercised. No real vault data or paid inference used.

These are target/milestone acceptance limits, not reasons to stop the independent safe package and service work approved in the preflight.

## Sources

[1] https://hermes-agent.nousresearch.com/docs/llms.txt
[2] https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
[4] https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard
[5] https://hermes-agent.nousresearch.com/docs/developer-guide/plugin-llm-access
[6] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/website/docs/developer-guide/desktop-plugin-sdk.md
[7] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/apps/desktop/src/sdk/index.ts
[8] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/apps/desktop/src/sdk/composer.ts
[9] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/web/src/plugins/sdk.d.ts
[10] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/web/src/plugins/registry.ts
[11] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/hermes_cli/plugins.py
[12] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/plugins/plugin_storage.py
[13] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/hermes_cli/web_server.py
[14] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/hermes_cli/web_server_dashboard.py
[15] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/website/docs/developer-guide/plugin-llm-access.md
[16] https://github.com/irfansofyana/hermes-blogwatcher/tree/1b6f32afc1a509437a9bc57a078bea99b3d69dab
[17] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/website/docs/developer-guide/plugins/index.md
[18] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/hermes_cli/plugin_validate.py
[19] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/website/docs/user-guide/features/web-dashboard.md
[20] https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/web/src/lib/api.ts
[21] https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
