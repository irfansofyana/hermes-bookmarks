# Development status and continuation

## Current state

**Library-first UX revision (2026-10-21):** owner approved the written [workspace design](superpowers/specs/2026-10-21-library-first-workspace-design.md) with “lets implement all”. The detailed [implementation plan](superpowers/plans/2026-10-21-library-first-workspace.md) covers the full revision in eight test-first tasks and awaits its required written review. Keep the established hybrid method; no execution-method choice needs reopening. This brings parts of M2–M4 forward, but collections, notes, association/image records and the revised layout are not implemented yet. Fresh planning baseline at `c811880`: 86 Python tests passed on CPython 3.14.7, 41 Node tests passed, deterministic bundle check passed. These are baseline tests, not new-feature evidence.

**In-plugin chat (2026-10-21):** owner approved implementation after the Learning architecture report. Bookmarks now has its own transcript/composer, dedicated Hermes sessions, profile-scoped durable bindings, streaming/activity/plan/decision controls, Stop, history and new-conversation model selection. The native-screen/draft-handoff source and obsolete tests are removed. Focused new tests and both emitted React entrypoints pass; real authenticated binding routes pass. Actual Dashboard conversation/visual checks passed. The targeted review found five Important defects; all were reproduced and fixed in one author-verified RED→GREEN pass. Connected Electron/provider acceptance remains open. See `verification/in-plugin-chat.md`; do not confuse implementation with all-target/provider acceptance.

**Verified chat reference:** owner-requested `irfansofyana/hermes-learning`, commit `2a9f2e2fd9c5007996dc7a6b7f16f50a306a6c10`. Its plugin-owned TutorPanel uses real Hermes sessions through Desktop public gateway methods/events and Dashboard SDK-authenticated WebSocket JSON-RPC. Inspected source matches installed Learning; 58 focused controller/transport tests passed. See `docs/verification/in-plugin-chat-reference.md`. This removes the mistaken native-composer/handoff blocker, not Bookmarks' own implementation/runtime acceptance work.

**Published review artifact:** [Draft PR #1](https://github.com/irfansofyana/hermes-bookmarks/pull/1) targets `main`; it is open, draft and unmerged. Code/review-fix commit: `fb80a4207db922de79a845b243374ff1bbe01b8a`. Its push and pull-request Actions runs both passed Node, Python 3.11 and Python 3.14; exact run/job SHAs were read back. Resolve current PR HEAD/CI for later documentation commits rather than extrapolating this checkpoint. Do not recreate the PR.

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

Latest chat review-fix verification: **86 Python tests passed on both CPython 3.14.7 and 3.11.14; 41 Node tests passed**, including stale-card, history-switch, replay-fence, auth-generation and plan-isolation regressions. See `verification/in-plugin-chat-review-fixes.md` for the stable checkpoint fingerprint. Deterministic build, Desktop syntax and whitespace passed. Official isolated validation returned `ok: true`/host-ready, with two disclosed scanner cautions on bundled Marked code-span regex syntax (not shell execution); see chat verification. Nonfatal async slow-callback diagnostics remain visible. Remote CI for the code-fix head `fb80a42` passed both push/PR events with all three expected jobs. Successful provider inference is still not claimed.

## Read next

1. `AGENTS.md`.
2. `docs/verification/m1.md`: real topology, checks, versions, four Dashboard screenshots and remaining gates.
3. `docs/verification/final-review.md` and `final-review-fixes.md`: original independent whole-branch review and the one verified fix pass, remaining minors/rulings. Earlier targeted findings are in `enrichment-review-fixes.md`. Do not redispatch either completed review.
4. Product spec, the approved `superpowers/specs/2026-10-21-library-first-workspace-design.md`, and `docs/ROADMAP.md` for complete v1 scope.
5. Next implementation plan: `superpowers/plans/2026-10-21-library-first-workspace.md`, pending plan review. The M1 plan and local `.superpowers/sdd/2026-10-20-m1-native-foundation/` ledger remain historical references. Committed verification documents are the portable evidence; old documents describe their original snapshots.

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
2. Complete actual-target chat acceptance on both clients. The owned UI and both emitted React behaviors now exist; actual Dashboard create/resume/submit/history and four visual cases pass. The credential-free host reports its real missing-provider error. Connected Electron and successful provider execution remain unproven; handoff is not a substitute.
3. Actual real-model text/vision, trust and routing checks on synthetic content are now approved but unperformed. Earlier incomplete-job probes remain lifecycle evidence, not inference evidence.
4. Independent-machine/OAuth transport and maximum payload checks through every host proxy. Current real authenticated TCP checks are loopback.
Both review/fix gates are consumed: original M1 and the new targeted chat review. No independent re-approval of author fixes is claimed. Prior UI minors remain historical in `final-review-fixes.md`; global Retry semantics were not changed. Current responsive chat acceptance is recorded separately, not inferred from the older stylesheet.

## Next runnable action

The written library-first design is approved and the detailed plan is ready for required review. After plan approval, execute Task 1's failing collapse/lifecycle tests in the existing worktree, preserving hybrid execution. Do not re-ask specification approval or execution method. No product code in this revision has changed yet; do not treat the new plan or baseline tests as implementation evidence. All prior target/provider acceptance gates remain open.

Draft PR #1 already contains the chat implementation and verified review fixes. Keep it draft while connected Electron and successful provider-response acceptance remain open. Re-read its exact head and CI before future publication; do not recreate the PR or repeat consumed M1/chat reviews. Local historical execution brief: `.superpowers/sdd/2026-10-20-m1-native-foundation/chat-implementation.md`. Synthetic model verification remains separate: the disposable host intentionally has no credentials. Merge/release/live installation remain unauthorized.

Use current files/git and the ledger, not checked-box totals or old conversation summaries. Preserve uncommitted work. Keep local review artifacts while target acceptance is unfinished.

## Scope and permissions

Approved: continued development toward v1 using hybrid execution, synthetic fixtures, local commits/documentation, development-branch push and PR publication, and real text/vision verification using synthetic inputs through Hermes. Host retries/fallback and possible provider charges were disclosed. Disposable test-home installs remain within isolated test scope. **Not approved:** merge/release, active plugin install/enable, production restart, real-vault migration or catalog submission. No remote CI result exists without a real exact-head run.

Shared library, native chat, automatic individual-capture tags/summaries, nested collections, rich notes/images, import and export remain v1 requirements. M2–M5 are roadmapped, not implemented. Follow each host's theme. The plugin owns its chat UI; Hermes owns the execution underneath. No core patches, private imports, copied host internals, new agent loop or separate credentials.

Public repo: `irfansofyana/hermes-bookmarks`. Initial spec: `c1b37f4d278ce76c9ac6632422ecc7e402875f19`; native-chat/UX revision: `b4259228b11bf57f7227e71207b26f833b15ce79`. Detailed Task 1–2 history remains in their verification documents and git history, not duplicated here.
