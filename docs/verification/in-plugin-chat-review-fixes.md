# In-plugin chat: targeted review fix pass

Date: 2026-10-21. Implementation range reviewed: `08ccd57..2399edc`. The original independent [review](in-plugin-chat-review.md) is preserved unchanged. It reported **five Important findings, no Critical findings**, with separate quality/security and chat-spec FAIL verdicts. Those original verdicts describe the reviewed snapshot, not independent approval of the subsequent author fixes.

The controller reproduced every finding, then fixed them in one RED→GREEN pass. No second review loop was commissioned. Author verification is described below; connected Electron, real-provider success and OAuth/independent-machine acceptance remain separate gates.

## Fixed findings

| Finding | Verified failure before fix | Fix and passing regression |
| --- | --- | --- |
| R1: human decision targets the displayed request | In both emitted clients, clicking A's still-rendered approval/clarification after B arrived produced one answer for B; expected zero. | Rendered handlers pass the immutable request/session/epoch and clarification question ID. Controller checks them before and after identity lookup and response. Both-client stale-card regressions now reject the old click while a real click on B still works. A related RED→GREEN lifecycle regression fences the decision-busy latch: Stop retires A, and A's late reply cannot leave or clear B's latch. |
| R2: prior reconciliation overwrites a new turn / removes uncertainty | Held A history erased B's stream, both with normal B admission and a lost B acknowledgement. | Each admitted Send advances ownership synchronously. Polling uses an epoch-owned lease; old success, failure and finally cannot mutate or clear a later operation. Regressions retain B's stream, Stop/busy state and uncertain-delivery fence, and reject another Send without restore/current-turn completion. |
| R3: stale auth rejection closes recovered socket | First ticket lookup timed out; after reconnect succeeded, rejecting that old lookup closed the new socket (readyState 3 instead of 1). | Success, rejection, handshake, socket callbacks and timers are generation-owned. The old failure is ignored, the recovered socket remains open and serves another RPC, and no extra ticket/replay occurs. |
| R4: history restore loses editable draft | Both emitted clients accepted typing with unresolved history destination. | The composer is temporarily disabled while opening/restoring, rather than accepting ambiguous-destination edits. Regressions verify it unlocks after restore and the old thread's draft survives switching back. Library capture remains independent. |
| R5: plans leak across conversations | A revision-50 plan remained visible while restoring B and rejected B revision 1. | Restore retires the old runtime/event target before its first await, clears the plan/reasoning state, and clears messages on a thread change. Regressions reject late A plan events during the await and accept B revision 1, with and without a snapshot plan. |

Ruling for R4: lock only the composer while its history destination is unresolved, rather than introduce a new draft revision/switch coordinator. This prevents loss with the smallest change; the UX cost is temporarily unavailable typing during restore. Drafts remain editable during ordinary response streaming.

## Final local verification

- CPython **3.14.7**: `python -W error -m unittest discover -s tests -q` — **86 passed**.
- CPython **3.11.14**: the same command in the isolated test environment — **86 passed**.
- `npm test` — **41 Node tests passed, zero failed/skipped**, including both actual emitted entrypoints with real React/jsdom.
- Deterministic build check, emitted Desktop ESM syntax check and `git diff --check` — passed.
- The full six-check gate ran against an unchanged worktree: SHA-256 fingerprint before/after **`c9bb81d5bf6e8ae10a287bfebde281e3c2c9fe821439984e48bb2fa2e227330f`**. This fingerprint includes HEAD/index/working changes and tracked/untracked non-ignored file bytes at the verification checkpoint, before this documentation update. No product code changed afterward. It is not a claim that a later documentation commit has the same whole-tree fingerprint.
- Existing nonfatal asyncio slow-callback diagnostics were visible; both Python runs still passed with warnings promoted to errors.

The corrected emitted Dashboard bundle was also exercised against the actual disposable Hermes host: four dark/light, wide/narrow cases again passed with no page JavaScript errors or horizontal overflow; drafts survived theme and mobile view changes; real SDK create/resume/submit/activate/history calls worked. The credential-free host returned its genuine missing-provider error and reconciled to Ready. No successful model answer or dangerous live approval is claimed. [Sanitized session/visual facts](in-plugin-chat-visual.json).

Official isolated package validation was rerun after the fix commit and passed `ok: true` / host-ready with two disclosed inline-shell scanner cautions on bundled Marked regex syntax, not a shell execution path. The underlying parser/import boundary was unchanged by these fixes. No scan suppression, core modification, active installation, production restart, merge or release was performed.

## Published development artifact

[Draft PR #1](https://github.com/irfansofyana/hermes-bookmarks/pull/1) is open against `main`, explicitly not ready for release. Code-fix head `fb80a4207db922de79a845b243374ff1bbe01b8a` passed both [push CI](https://github.com/irfansofyana/hermes-bookmarks/actions/runs/39539517840) and [PR CI](https://github.com/irfansofyana/hermes-bookmarks/actions/runs/39539609827). Each run and all three jobs (`node`, `python (3.11)`, `python (3.14)`) returned that exact head SHA and success. A later documentation head needs its own CI readback; this checkpoint does not claim those future results. The PR remains draft/unmerged and owner retains deployment/merge/release control.
