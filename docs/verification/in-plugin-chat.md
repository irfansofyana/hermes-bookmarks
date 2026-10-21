# In-plugin chat verification

Date: 2026-10-21. Development feature, not a release or installation claim. Replaces the legacy handoff implementation; older `native-chat.md` describes a superseded snapshot.

## Implemented boundary

- Bookmarks owns the responsive conversation panel, context selection, editable composer and Markdown presentation. Wide layouts retain the library; narrow layouts switch Library/Chat without navigating to ordinary Hermes chat.
- Hermes owns agent execution, durable transcripts, providers, tools, approvals and interruption. No private host imports, core edits, new agent loop or credential store. Learning is a read-only architecture reference, not a runtime dependency.
- Dedicated sessions use public `session.create`/`session.resume`, `prompt.submit`, `session.activate`/`session.history` and `session.interrupt`. Each RPC captures the intended profile/session; Desktop also fences connection identity. The ordinary focused session is never adopted.
- SQLite migration 5 adds random library identity and profile-owned binding metadata, not transcript copies. `GET /chat/identity`, paginated `GET /chat/threads` and bounded `POST /chat/threads` use host-authenticated plugin routes. Bindings are idempotent and cannot be retargeted; body-supplied profiles and secret/model extras are rejected.
- Send is explicit. Up to 20 IDs are attached as untrusted context, not entire bookmark bodies, notes, images or the whole library. Selected context is visible. Lost prompt acknowledgement blocks replay until deliberate restore/reconciliation. Stop and dispose invalidate pending creation/submission continuations.
- Real streaming/tool/plan events are scoped. Tool display uses exposed summaries, never raw args/results. Monotonic plan revisions reject stale updates. Human approval/clarification uses `request.answer`/`clarify.lock`, not model-granted consent. Other-session and unsupported WebSocket server requests are declined.
- A new conversation may use an authenticated configured model or profile default. Existing conversations retain their host-owned model. Chat never changes the library enrichment route.
- Marked 18.1.1 supplies Markdown lexing; allowlisted React rendering supplies safety. Raw HTML is literal text, executable/relative URLs are not links, automatic image loads are disabled, nesting and rendered text are bounded. Tables/code render in scoped scrollable containers. Full Marked license is embedded in both bundles. esbuild 0.28.2 is build-only.

## Test-first evidence

1. New real SQLite/API tests initially failed on missing routes (404); four tests now pass: stable/reopened/different-root identity, binding idempotency and retarget refusal, active-profile isolation, bounded writes/pagination.
2. Controller tests initially failed because the owned controller was absent; transport tests failed because adapters were absent. They now cover explicit binding/submission, duplicate Send, bounded references, scoped stream/tool/plan events, uncertain delivery, Stop/dispose races, profile drift and real human decisions.
3. Checking the target's declared `PromptSubmitResult` exposed an invalid synthetic fixture status (`accepted`). The fixture was corrected to the real `streaming` status; the resulting RED was fixed against the published enum (`streaming`, `queued`, `steered`, `redirected`). No fake host result is used as runtime acceptance evidence.
4. Both emitted entrypoints with real React/jsdom failed before the in-plugin composer existed, then passed context preparation, no navigation/inference before Send, actual transport-to-controller binding/submission, preserved capture input, native-tool refresh, Stop, safe Markdown and explicit decisions.
5. Both emitted restored-model regressions failed (follow-up could accidentally ask to reset the model); fixed by retaining the restored conversation's model, not the new-thread picker value. Six focused emitted-UI tests now pass.

Whole-suite verification at `2399edc`: **86 Python tests on CPython 3.14.7 and 3.11.14; 29 Node tests passed**. Both Python runs used `-W error`; deterministic bundles, Desktop syntax and diff whitespace passed. Nonfatal async slow-callback diagnostics from SQLite contention tests remain visible. No remote CI is claimed.

Official isolated `hermes plugins validate --json` returned `ok: true`, `host_ready: true`, no core override and SDK-only Desktop surface. It reported two `inline_shell_exec` cautions, one for each emitted bundle. Investigation matched the scanner’s Markdown skill DSL pattern against bundled Marked inline-code regular-expression negative lookaheads (`(?!` followed by a backtick), not an executable shell path. The renderer does not evaluate Markdown commands; the vendor lexer only returns tokens. The warnings remain disclosed, not suppressed.

## Actual isolated host evidence so far

Current package staged only into a disposable Hermes home, not an active discovery root. Its old synthetic queued jobs were cancelled before startup. A real Dashboard server returned authenticated HTTP 200 for health, new chat identity and empty profile-owned conversation list. It reports the registered `default` owner; no filesystem path or credential appears in identity responses. This proves host-mounted API integration, not streaming/provider execution.

The real emitted Dashboard plugin then passed four browser cases: Hermes Teal dark and Nous Blue light, each at 1440 and 390 pixels. Both chat and composer were visible; no horizontal page/workspace overflow or browser JavaScript errors occurred. Theme changes and mobile Library/Chat navigation preserved both capture and chat drafts. Preparing Ask Hermes context made no create/submit call. An explicit Send exercised actual SDK-authenticated `client.capabilities`, `model.options`, `session.resume`, `session.create`, `prompt.submit`, `session.activate` and `session.history`. These are real frames, not synthetic responses. Raw sanitized facts: [visual/session evidence](in-plugin-chat-visual.json).

Screenshots: [dark wide](screenshots/bookmarks-chat-dashboard-dark-1440.png), [dark narrow](screenshots/bookmarks-chat-dashboard-dark-390.png), [light wide](screenshots/bookmarks-chat-dashboard-light-1440.png), [light narrow](screenshots/bookmarks-chat-dashboard-light-390.png). Initial harness attempts discovered an already-selected light theme and a terminal Stop-button detachment race; selecting the requested themes explicitly and waiting for settled terminal state produced the successful evidence, rather than relabeling or hiding failed attempts.

The disposable host intentionally has no provider model, `auth.json` or `.env`. The real request therefore returned Hermes’s genuine missing-provider error and reconciled from Thinking to Ready. **No successful model response is claimed.** Synthetic real-provider verification remains approved, but credentials were not copied into this fixture and no model response was fabricated.

Connected packaged Desktop acceptance remains blocked: a fresh isolated app user-data directory, Xvfb and the supported remote URL/token override reached matching client/backend version displays but remained behind the Backend offline/connection overlay. No pointer interception bypass, core patch or active-app deployment was attempted. Both emitted Desktop React behavior and scoped gateway adapter tests pass, but are not substitutes for a connected Electron acceptance pass. OAuth and independent-machine topology remain unproven.

The targeted new chat ownership/auth/lifecycle review is still pending at this checkpoint. The previous M1 review is historical and is not being repeated.

No active install, production restart, merge or release was performed. Full v1 collections/notes/import/export/standalone-image/vision/settings milestones remain separate and incomplete.
