# Targeted in-plugin chat review

## Verdicts

- **Quality/security: FAIL.** Five Important defects reproduced, including an approval-authority mismatch. No Critical finding. Product source was read-only throughout this review.
- **Chat-spec (§2.2 / replacement brief): FAIL.** The plugin-owned UI / Hermes-execution architecture is implemented, but the findings below violate exact human-decision targeting, current-turn ownership / uncertain-delivery fencing, reconnect lifecycle, draft preservation, and conversation-scoped plans. These are new-chat findings, not a repeat of the previous M1 review or findings about deferred collections/import/export/images.

Reviewed range: `08ccd57c71ff6fedc9c20dfea9bf1c555582f793..2399edca20b2cc429c01c2fead4672d91bd35afb` in the existing `m1` worktree. Tests and adversarial probes ran with the requested `2399edca20b2cc429c01c2fead4672d91bd35afb` HEAD and clean tracked source/index. The 25 changed/deleted tracked files had review fingerprint SHA-256 `a5f0fe0d4c2c71b48328bd30fd96060144ac74a93290fb08a721c157fe470e8e` (path + NUL + file bytes, or `<deleted>`, in `git diff --name-only` order). During final report verification, the parent advanced HEAD to `a1e9b4cedc63b66f31d2b1c62090d235008b4f72`, a documentation/screenshots-only commit. `git diff` confirmed no product, build, or test changes from the requested head; this report still reviews the exact requested range, not that later documentation. Concurrent parent-created Dashboard screenshots were left untouched and are not this review's evidence.

## Important findings

### R1 — Allow/clarification handlers do not identify the card the human actually answered

**Locations:** `ui/chat-panel.js:79`; `ui/chat-session.js:175-184`.

The rendered permission buttons call `controller.current.respond('once')` without the rendered request ID. `respond()` then obtains whichever request is current in controller state. The same issue affects clarification choices: neither the rendered request ID nor question ID is passed by the UI. The check after the identity await only checks that this newly captured request remains current; it cannot detect that the clicked card was a different one.

**Reproduction, both actual emitted entrypoints, real React/jsdom:**

1. Start a synthetic conversation and render approval A, description `Read harmless file A?`, command `read A`.
2. Retain the DOM node for A's `Allow once` button.
3. Deliver a second legitimate approval B (`Delete important file B?`, `delete B`) to the controller, before React commits the corresponding render; click the still-rendered A button.
4. The actual emitted UI sends `request.answer` for **B**, with `{choice:'once'}`.

Observed on **Desktop and Dashboard**:

```json
{"displayedAtClick":"Your permission is neededRead harmless file A?read ADenyAllow once","answeredRequest":"request-new-B","choice":"once"}
```

The probe used the existing emitted-UI `mount` helper, batched the incoming second event and DOM click with `React.act`, and asserted the DOM still displayed A at click time. This is a stale-render scheduling probe, not a real dangerous-command/provider run.

**Impact:** A human can authorize a different command from the one presented. Parallel/new approvals and delayed React commits must not convert a click on an old card into authority over the replacement. Clarification can likewise answer a different question using the old question's choice.

**Required fix direction:** Pass the displayed request ID and, for clarification, displayed question ID into `respond`; reject any mismatch before and after prerequisite awaits. Keep the answered request immutable across the whole action.

### R2 — Old reconciliation can overwrite a new turn and clear its uncertain-delivery fence

**Locations:** `ui/chat-session.js:60` (Send reuses the existing epoch); `ui/chat-session.js:157-161` (terminal events start refreshes without locking admission); `ui/chat-session.js:192-205` (old snapshot/history mutates current state and clears uncertainty).

Only fresh/restore/stop/disconnect change the epoch. A new Send does not invalidate a reconciliation already running for an idle/completed prior turn. A late terminal/error event can start such a refresh while the panel is idle; Send is still allowed. Its delayed history response remains `valid(epoch)` after the new Send and unconditionally replaces messages, clears `uncertain`, and marks the UI idle.

**Deterministic execution against the real controller:**

1. Finish A and reconcile it to idle.
2. Deliver A's late `error` event; let its `session.activate` snapshot say `running:false`, then hold its `session.history` response.
3. Submit B and stream B's text. The synthetic backend now accurately reports that B is running.
4. Resolve A's old history response. B disappears and the panel reports idle; another prompt is admitted into the running B session.

Observed:

```json
{"case":"old terminal history overwrites active turn","backendRunning":true,"uiBusy":false,"uiUncertain":false,"messages":["Turn A","Answer A"]}
{"promptAdmissionStatuses":["streaming","streaming","steered"]}
```

A second probe accepted B on the synthetic backend but rejected only B's acknowledgement (no transport-disconnected event). B correctly became uncertain initially. Resolving A's old history then removed that protection and permitted the **same B prompt again without any restore**:

```json
{"case":"stale history clears uncertain accepted prompt","backendRunning":true,"uncertainAfterStaleHistory":false,"submits":3,"restoreCalls":0}
```

The ordering does not require a second A submission. A terminal/error notification and polling are independent completion signals. The inspected target's `tui_gateway/prompt_turn.py:130-133`, for example, releases `running` before emitting an ownership-refusal error, so polling can observe an idle A before its error notification. The reproduction uses external gateway doubles and does not claim this ordering was observed on the live host. Per-request acknowledgement failure without a disconnect is especially relevant to the Desktop RPC adapter; Dashboard's terminal socket-disconnect path separately invalidates its epoch.

**Impact:** A live answer and its Stop affordance disappear, a follow-up can unexpectedly steer/queue into a running turn, and a request with unknown delivery can be replayed without the required deliberate restore/reconciliation of that request.

**Required fix direction:** Invalidate prior async ownership synchronously on every admitted Send, not just navigation/Stop. Bind reconciliation success, failure, and cleanup to its turn/generation; an old snapshot must never clear a later submission's uncertainty or busy state.

### R3 — A stale SDK authentication failure closes the successfully reconnected Dashboard socket

**Locations:** `ui/chat-transport.js:95-107`, especially the unconditional catch at line 107; reconnect reset at `ui/chat-transport.js:115-119`.

A successful old `buildWsUrl` continuation checks its connection generation, but its rejection handler calls `terminate()` unconditionally. If the first authentication call times out, an explicit reconnect can create a healthy new socket while the first SDK call is still outstanding. A subsequent failure of that old call terminates the new connection.

**Executed reproduction:** first `SDK.buildWsUrl` returns a controlled promise; connect timeout is 20 ms; wait for timeout; explicitly reconnect with a successful second ticket/capability handshake; reject the first ticket promise.

```json
{"case":"stale authentication rejection after successful reconnect","authAttempts":2,"newSocketRemainsOpen":false,"disconnects":["Bookmarks connection timed out. Reconnect to try again.","Could not authenticate the Hermes connection. Reconnect through the Dashboard."]}
```

This used the real Dashboard transport, a protocol-level WebSocket double, real timers, and no credentials. The old SDK operation was deliberately left pending until the second connection was confirmed open.

**Impact:** A recovered conversation is disconnected by an obsolete attempt, potentially during a new prompt; the user is forced back into uncertain-delivery recovery for work unrelated to the failed attempt.

**Required fix direction:** Generation/ownership checks must cover rejection handlers as well as success handlers, including the capability-handshake catch. Only the owning attempt may terminate its socket.

### R4 — Typing during history restore is silently discarded

**Locations:** `ui/chat-panel.js:50-58`, especially line 56; editable composer at `ui/chat-panel.js:80`.

`selectThread()` saves the old draft once, awaits `chat.restore()`, and then unconditionally replaces the composer with the destination's cached draft. History controls/Send are locked while opening, but the textarea remains editable. Text written during that await is not saved in either conversation and is overwritten by the late continuation.

**Reproduced in both actual emitted entrypoints with React/jsdom:** restore thread A, type `Original A draft`, switch to B with a controlled pending `session.resume`, type into the still-editable composer, then release B's resume response.

```json
{"target":"desktop","case":"editable draft is overwritten by late history switch","beforeHistoryResolves":"New writing while history loads","afterHistoryResolves":""}
{"target":"dashboard","case":"editable draft is overwritten by late history switch","beforeHistoryResolves":"New writing while history loads","afterHistoryResolves":""}
```

Returning to A yielded only `Original A draft`, confirming the new writing was not merely moved to A's saved draft. The harness was adapted **in memory only** to delay resume and to await RPC results in its Dashboard socket double; the product bundles were unchanged.

**Impact:** User-authored text is lost during an ordinary slow history switch, violating the explicit draft-preservation requirement.

**Required fix direction:** Establish destination draft ownership synchronously and guard late updates by draft revision/thread, or make the composer non-editable while it has no stable destination. Never blindly overwrite edits made after an await began.

### R5 — Plan revision/state leaks across restored conversations and suppresses the new conversation's plan

**Locations:** `ui/chat-session.js:95-111` (restore retains the previous plan); `ui/chat-session.js:122-125` (revision comparison uses that retained state).

Restoring a different thread resets `streamId`, but does not clear `state.plan`. An authoritative B snapshot without a plan leaves A's plan displayed. If B has a plan, its legitimate revision is compared with A's unrelated revision and is rejected whenever lower. This is not merely a loading flash: it persists after restore and subsequent B plan events.

**Executed controller reproduction:** A receives plan revision 50, finish A, restore B with no `todo_state`, then deliver B's legitimate revision-1 `todo.updated` event to the resumed runtime.

```json
{"case":"restore different conversation retains foreign plan","activeThread":"thread-b","displayedPlan":{"revision":50,"todos":[{"id":"a","content":"Plan for THREAD A","status":"completed"}]}}
```

**Impact:** B displays another conversation's plan/progress and silently drops B's real plan updates until B surpasses A's revision. This violates conversation-owned state and makes the required plan/progress feature incorrect after history navigation.

**Required fix direction:** Scope plan revisions to the runtime/conversation and replace/clear the plan from the new conversation's authoritative snapshot. Do not compare revisions across sessions.

## Verification and boundaries

Executed on Node `v24.18.0` and Python `3.14.7`:

- `rtk proxy node --test tests/*.cjs` — **29 passed, 0 failed**.
- `rtk proxy env PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -q` — **86 passed**. Nonfatal existing SQLite-contention slow-callback diagnostics were visible.
- `rtk proxy node scripts/build-ui.cjs --check` — passed; no bundles rebuilt/written.
- `rtk git diff --check 08ccd57c71ff6fedc9c20dfea9bf1c555582f793 2399edca20b2cc429c01c2fead4672d91bd35afb` — passed.
- All adversarial probes above ran successfully against unchanged product source. They asserted the defective outcomes, so their successful exits are evidence of the findings, not passing acceptance tests. Scripts ran with `rtk proxy node -e`; no test/product files were created or edited.

The existing green tests do not cover these schedules. For reuse, the controller probes loaded the definitions preceding the first `test('explicit...')` in `tests/test_chat_session.cjs`, exporting its `harness` and `turns` into an in-memory VM. The emitted-UI probes similarly loaded the definitions preceding `for(const target of...)` in `tests/test_chat_ui.cjs` and exercised both emitted targets with real DOM events. Controlled promises were inserted only into the external API/RPC doubles.

Reviewed but no additional Important defect demonstrated: API-derived profile and stable library identity; foreign-binding checks; parameterized/bounded binding storage; dedicated session creation rather than focused ordinary-chat adoption; model retention on restored conversations; separation from enrichment routing; scoped tool summaries; allowlisted Markdown/links and disabled remote images; Stop/dispose invalidation of pending creation; normal explicit lost-acknowledgement restore. These are bounded source/local-test observations, not an exhaustive security guarantee.

No real provider calls, credential copying, active installation, restarts, commits, pushes, or product modifications were performed by this reviewer. The pinned Learning reference and target public contracts were inspected read-only. This review does **not** establish actual connected Desktop behavior, real-provider execution, OAuth/independent-machine compatibility, or live-host dangerous approval execution. Later parent-generated actual-host evidence is separate; this review neither validates nor invalidates those acceptance claims.

**Only authored artifact:** `.superpowers/sdd/2026-10-20-m1-native-foundation/chat-review.md` (gitignored).
