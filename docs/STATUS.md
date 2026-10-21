# Development status and continuation

## Current state

**In-plugin chat (2026-10-21):** owner approved implementation after the Learning architecture report. Bookmarks now has its own transcript/composer, dedicated Hermes sessions, profile-scoped durable bindings, streaming/activity/plan/decision controls, Stop, history and new-conversation model selection. The native-screen/draft-handoff source and obsolete tests are removed. Focused new tests and both emitted React entrypoints pass; real authenticated binding routes pass. Actual-host conversation/visual checks and a targeted new-boundary review are in progress. See `verification/in-plugin-chat.md`; do not confuse implementation with all-target/provider acceptance.

**Verified chat reference:** owner-requested `irfansofyana/hermes-learning`, commit `2a9f2e2fd9c5007996dc7a6b7f16f50a306a6c10`. Its plugin-owned TutorPanel uses real Hermes sessions through Desktop public gateway methods/events and Dashboard SDK-authenticated WebSocket JSON-RPC. Inspected source matches installed Learning; 58 focused controller/transport tests passed. See `docs/verification/in-plugin-chat-reference.md`. This removes the mistaken native-composer/handoff blocker, not Bookmarks' own implementation/runtime acceptance work.

**Current shipping permission:** publish a PR only; owner retains merge/release. Synthetic real text/vision provider tests are approved, including disclosed host retries/possible charges. No live installation or production restart is authorized. The earlier unanswered question about accepting Dashboard handoff limitations is superseded by the in-plugin UI correction.

M1 is a working development foundation with real backend and Dashboard evidence, **not full target acceptance or a v1 release**. Work remains on `feat/m1-native-foundation` in the existing `m1` linked worktree, based on `e7e0cc91cf71724c9d3caf7978308be462c78a77`. Resolve current HEAD with `rtk git log -1`; do not recreate the worktree or restart completed tasks.

The owner approved subagent-driven execution, then explicitly switched to **hybrid after Task 2**. Ordinary implementation is direct with TDD, targeted boundary reviews and one whole-branch review. Tasks 1–2 were independently approved; do not redo their implementer/reviewer cycles.

| Task | State and committed evidence |
| --- | --- |
| 1: public contracts/package | Approved at `a51a493`; both minors fixed in Task 3. Historical host/build provenance: `verification/compatibility.md`. |
| 2: durable shared service | Approved at `13d6e004db6efa035f2300a468267e8e1f63e60e`; storage/multi-process evidence: `verification/service.md`. |
| 3: native tools/dual-host UI | Locally implemented at `51b1f3c`; initial evidence: `verification/capture.md`; newer real-host checks below. |
| 4: in-plugin conversation | Replaces the historical `b03c42b` handoff. New public Hermes-backed controller, transports, scoped binding API and owned chat UI are implemented; tests pass. Current evidence: `verification/in-plugin-chat.md`. |
| 5: jobs/enrichment | `98391e8`, targeted review fixes at `5ea3920`, then actual-host async activation fix in Task 6. Real host consumed an intentionally incomplete job after the initiating request ended; no real model call used. |
| 6: image/integration | Image slice at `44014f3`; real cold-host auth/image/reopen/native-registry checks and Dashboard visual matrix now exercised. Final whole-branch review consumed; all three Important findings fixed in one RED→GREEN pass. Two UI minors are deferred. M1 remains incomplete because target/model gates are open. |

Chat checkpoint: **86 Python tests passed on CPython 3.14.7; 27 Node tests passed before the additional two restored-model regressions, whose focused six-test UI run now passes**. Whole suites are rerun before completion. Prior committed checkpoint `8f0a2e9`: 82 Python on both 3.14/3.11 and 14 Node, official validation passed. Nonfatal async slow-callback diagnostics are recorded, not hidden. No remote CI or new provider acceptance is claimed.

## Read next

1. `AGENTS.md`.
2. `docs/verification/m1.md`: real topology, checks, versions, four Dashboard screenshots and remaining gates.
3. `docs/verification/final-review.md` and `final-review-fixes.md`: original independent whole-branch review and the one verified fix pass, remaining minors/rulings. Earlier targeted findings are in `enrichment-review-fixes.md`. Do not redispatch either completed review.
4. Product spec and `docs/ROADMAP.md` for complete v1 scope.
5. Active plan: `docs/superpowers/plans/2026-10-20-m1-native-foundation.md`. Local ledger/review artifacts: `.superpowers/sdd/2026-10-20-m1-native-foundation/` (gitignored). Committed verification documents are the portable record; historical documents describe their original snapshots.

## Integration rules to preserve

- Configure the same absolute `plugins.entries.hermes-bookmarks.settings.library_root` in participating profiles. No profile-local fallback, privacy boundary or cross-machine sync is implied. Conflicting roots fail closed.
- Route fields are `provider`, `model`, `owner_profile`; only the configured owner initializes the persisted route. Library inference is independent from native chat. Hermes owns credentials, provider retries/fallback and trust.
- Real isolated registration is synchronous and has no running loop. Public async native capture (`is_async=True`) or authenticated async HTTP entry activates `ctx.spawn_task` on the host's persistent async lane. Only the original context's profile may activate it; metadata is lifecycle-owned. No private loop import, ad-hoc loop or sidecar. Startup success is not provider compatibility.
- Initial owner API activation can resume already accepted automatic capture jobs. GET-only smoke checks do not promise zero background processing. Attachment uploads do not enqueue image analysis.
- Only SQLite busy/locked failures receive three bounded per-operation attempts; public storage error messages stay sanitized. Lifecycle-owned public task observers record termination. A failed worker can restart only from its original owner’s next async entry after a 30-second monotonic cooldown, not on a background timer. A real host recovered a 7.027-second write lock with the default five-second timeout and no extra API activation.
- Complete/fail sample lease time after the SQLite write lock. Fresh claim tokens and revisions reject stale applies. Admitted executor work drains before worker termination is acknowledged, including repeated cancellation; cancellation does not instantly stop a thread.
- Images have owned IDs, bounded decoding and authenticated delivery; no static-files auth bypass or arbitrary path refs. UI JSON transport is public; do not assume binary IPC works in every authentication mode.
- Shared UI sources emit separate Desktop/Dashboard loaders. Do not hand-edit generated bundles. Plugin-owned chat presentation is required; a separate agent runtime, credential store, copied internals or host UI interception is not allowed.

## Open acceptance gates

1. Connected actual Desktop plugin proof. The disposable app stayed behind its backend connection overlay. No core workaround or active-app deployment was attempted.
2. In-plugin chat UI and verified public Hermes-backed execution on both clients. The old native-composer handoff gate is no longer the intended UX; do not waive in-plugin chat just because a handoff works.
3. Actual real-model text/vision, trust and routing checks on synthetic content are now approved but unperformed. Earlier incomplete-job probes remain lifecycle evidence, not inference evidence.
4. Independent-machine/OAuth transport and maximum payload checks through every host proxy. Current real authenticated TCP checks are loopback.
Code review/fix gates are consumed, not pending. Deferred UI minors: global Retry only reloads rather than resubmitting; narrow layouts hide item status. Both are recorded in `final-review-fixes.md` for the next UI pass, not waived for v1.

## Next runnable action

Finish actual isolated chat/visual checks and the targeted new ownership/auth/lifecycle review; fix Important findings in one RED→GREEN pass. Local execution brief: `.superpowers/sdd/2026-10-20-m1-native-foundation/chat-implementation.md`. The old M1 whole-branch review remains consumed; do not repeat it. Keep synthetic model verification separately labeled: the disposable host intentionally has no credentials. Prepare the authorized PR when evidence is ready, without merge/release/live installation.

Use current files/git and the ledger, not checked-box totals or old conversation summaries. Preserve uncommitted work. Keep local review artifacts while target acceptance is unfinished.

## Scope and permissions

Approved: continued development toward v1 using hybrid execution, synthetic fixtures, local commits/documentation, development-branch push and PR publication, and real text/vision verification using synthetic inputs through Hermes. Host retries/fallback and possible provider charges were disclosed. Disposable test-home installs remain within isolated test scope. **Not approved:** merge/release, active plugin install/enable, production restart, real-vault migration or catalog submission. No remote CI result exists without a real exact-head run.

Shared library, native chat, automatic individual-capture tags/summaries, nested collections, rich notes/images, import and export remain v1 requirements. M2–M5 are roadmapped, not implemented. Follow each host's theme. The plugin owns its chat UI; Hermes owns the execution underneath. No core patches, private imports, copied host internals, new agent loop or separate credentials.

Public repo: `irfansofyana/hermes-bookmarks`. Initial spec: `c1b37f4d278ce76c9ac6632422ecc7e402875f19`; native-chat/UX revision: `b4259228b11bf57f7227e71207b26f833b15ce79`. Detailed Task 1–2 history remains in their verification documents and git history, not duplicated here.
