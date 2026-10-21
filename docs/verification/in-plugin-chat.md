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

Whole-suite checkpoint before the two added restored-model tests: 86 Python tests on CPython 3.14.7 and 27 Node tests passed; deterministic bundles, Desktop syntax and diff whitespace passed. The six-test UI run after those regressions passed. Whole suites are rerun before final completion; no remote CI is claimed at this checkpoint. Nonfatal async slow-callback diagnostics from SQLite contention tests remain visible.

## Actual isolated host evidence so far

Current package staged only into a disposable Hermes home, not an active discovery root. Its old synthetic queued jobs were cancelled before startup. A real Dashboard server returned authenticated HTTP 200 for health, new chat identity and empty profile-owned conversation list. It reports the registered `default` owner; no filesystem path or credential appears in identity responses. This proves host-mounted API integration, not streaming/provider execution.

The disposable host intentionally has no provider model, `auth.json` or `.env`. Synthetic real-provider verification remains approved, but credentials have not been copied into the fixture. Browser/session/visual evidence and targeted chat ownership/auth/lifecycle review are pending at this checkpoint. Previous connected Desktop failure remains an open acceptance gate until an actual connected target succeeds. OAuth and independent-machine topology are not proven by loopback tests.

No active install, production restart, merge or release was performed. Full v1 collections/notes/import/export/standalone-image/vision/settings milestones remain separate and incomplete.
