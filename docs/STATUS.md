# Development status and continuation

## Current state

M1 is a working development foundation with real backend and Dashboard evidence, **not full target acceptance or a v1 release**. Work remains on `feat/m1-native-foundation` in the existing `m1` linked worktree, based on `e7e0cc91cf71724c9d3caf7978308be462c78a77`. Resolve current HEAD with `rtk git log -1`; do not recreate the worktree or restart completed tasks.

The owner approved subagent-driven execution, then explicitly switched to **hybrid after Task 2**. Ordinary implementation is direct with TDD, targeted boundary reviews and one whole-branch review. Tasks 1–2 were independently approved; do not redo their implementer/reviewer cycles.

| Task | State and committed evidence |
| --- | --- |
| 1: public contracts/package | Approved at `a51a493`; both minors fixed in Task 3. Historical host/build provenance: `verification/compatibility.md`. |
| 2: durable shared service | Approved at `13d6e004db6efa035f2300a468267e8e1f63e60e`; storage/multi-process evidence: `verification/service.md`. |
| 3: native tools/dual-host UI | Locally implemented at `51b1f3c`; initial evidence: `verification/capture.md`; newer real-host checks below. |
| 4: native handoff | Implemented at `b03c42b`, exact-target/draft/focus tests passed. Connected Desktop acceptance remains blocked; Dashboard contextual handoff is unsupported in the inspected SDK. `verification/native-chat.md`. |
| 5: jobs/enrichment | `98391e8`, targeted review fixes at `5ea3920`, then actual-host async activation fix in Task 6. Real host consumed an intentionally incomplete job after the initiating request ended; no real model call used. |
| 6: image/integration | Image slice at `44014f3`; real cold-host auth/image/reopen/native-registry checks and Dashboard visual matrix now exercised. Final whole-branch review remains. M1 is still incomplete because target/model gates are open. |

Latest verification: **77 Python tests passed on CPython 3.14.7 and fresh CPython 3.11.14; 10 Node tests passed**. Deterministic bundle, Desktop syntax, whitespace and official plugin validation passed (`ok: true`, no warnings). Nonfatal async slow-callback diagnostics from parallel runs are recorded, not hidden. No remote CI is claimed.

## Read next

1. `AGENTS.md`.
2. `docs/verification/m1.md`: real topology, checks, versions, four Dashboard screenshots and remaining gates.
3. `docs/verification/enrichment-review-fixes.md`: the three independently found Important issues and controller RED→GREEN fixes. Do not redispatch that targeted review.
4. Product spec and `docs/ROADMAP.md` for complete v1 scope.
5. Active plan: `docs/superpowers/plans/2026-10-20-m1-native-foundation.md`. Local ledger/review artifacts: `.superpowers/sdd/2026-10-20-m1-native-foundation/` (gitignored). Committed verification documents are the portable record; historical documents describe their original snapshots.

## Integration rules to preserve

- Configure the same absolute `plugins.entries.hermes-bookmarks.settings.library_root` in participating profiles. No profile-local fallback, privacy boundary or cross-machine sync is implied. Conflicting roots fail closed.
- Route fields are `provider`, `model`, `owner_profile`; only the configured owner initializes the persisted route. Library inference is independent from native chat. Hermes owns credentials, provider retries/fallback and trust.
- Real isolated registration is synchronous and has no running loop. Public async native capture (`is_async=True`) or authenticated async HTTP entry activates `ctx.spawn_task` on the host's persistent async lane. Only the original context's profile may activate it; metadata is lifecycle-owned. No private loop import, ad-hoc loop or sidecar. Startup success is not provider compatibility.
- Initial owner API activation can resume already accepted automatic capture jobs. GET-only smoke checks do not promise zero background processing. Attachment uploads do not enqueue image analysis.
- Complete/fail sample lease time after the SQLite write lock. Fresh claim tokens and revisions reject stale applies. Admitted executor work drains before worker termination is acknowledged, including repeated cancellation; cancellation does not instantly stop a thread.
- Images have owned IDs, bounded decoding and authenticated delivery; no static-files auth bypass or arbitrary path refs. UI JSON transport is public; do not assume binary IPC works in every authentication mode.
- Shared UI sources emit separate Desktop/Dashboard loaders. Do not hand-edit generated bundles or build custom chat.

## Open acceptance gates

1. Connected actual Desktop bookmark/composer proof. A disposable packaged app launched with verified separate userData but stayed behind its backend connection overlay. No core workaround or active-app deployment was attempted.
2. Supported Dashboard context/draft handoff, or an explicit owner revision of that target's acceptance. Resume navigation is not equivalent; keep the action unavailable.
3. Approved real-model text/vision, trust and routing. The real worker probe used incomplete job settings and a non-callable synthetic route; it is not inference evidence.
4. Independent-machine/OAuth transport and maximum payload checks through every host proxy. Current real authenticated TCP checks are loopback.
5. Final whole-branch review and blocking fixes. Earlier targeted enrichment review is consumed and its three findings are fixed.

## Next runnable action

Finish the final whole-branch review of the current committed snapshot. Fix Critical/Important findings directly with RED→GREEN regressions and a green full suite; record minors/rulings rather than starting speculative review loops. Preserve the partial-M1 label while gates remain. Do not expand into M2 imports/organization or M3 notes/settings until the M1 outcome is recorded.

Use current files/git and the ledger, not checked-box totals or old conversation summaries. Preserve uncommitted work. Keep local review artifacts while target acceptance is unfinished.

## Scope and permissions

Approved: isolated M1 development, hybrid execution, synthetic fixtures, local commits and documentation. Disposable test-home configuration/installs were exercised within that isolated test scope. **Not approved:** active plugin install/enable, production restart, paid/live inference, real-vault migration, push/merge, catalog submission or release. Publishing a development branch needs separate approval; no remote CI result exists without a real exact-head run.

Shared library, native chat, automatic individual-capture tags/summaries, nested collections, rich notes/images, import and export remain v1 requirements. M2–M5 are roadmapped, not implemented. Follow each host's theme. No core patches, private imports, custom agent/chat/model picker or separate credentials.

Public repo: `irfansofyana/hermes-bookmarks`. Initial spec: `c1b37f4d278ce76c9ac6632422ecc7e402875f19`; native-chat/UX revision: `b4259228b11bf57f7227e71207b26f833b15ce79`. Detailed Task 1–2 history remains in their verification documents and git history, not duplicated here.
