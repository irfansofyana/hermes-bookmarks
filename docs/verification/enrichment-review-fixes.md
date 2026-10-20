# Enrichment review fix pass

The independent targeted review of `98391e8` requested changes for three Important findings, with no Critical finding. The controller reproduced each finding before changing production code, then fixed them directly under the approved hybrid workflow. This is regression verification, not a new independent approval or full M1 acceptance.

## Findings and fixes

1. Supervised cancellation previously abandoned executor-backed database work. A held completion could mutate storage after awaiting worker termination. The worker now owns a shielded storage operation and drains it before acknowledging cancellation, including repeated cancellation requests. Work already admitted may commit while shutdown waits; it cannot outlive acknowledged termination. Cancellation is checked before admitting new storage work, and after extraction, so an upstream coroutine returning success after swallowing cancellation does not restart processing. A cancelled, still-live claim is recovered when its lease expires.
2. Lease checks sampled time before waiting for SQLite's write lock. Completion and failure now sample the production wall clock inside the acquired write transaction. Fresh-token and revision checks remain in the same transaction. Tests hold a real competing SQLite lock, advance a controlled clock past expiry, then release the lock; neither operation may mutate the expired claim.
3. Route bootstrap previously persisted an immutable route before checking profile ownership. The ownership check now precedes queue/database creation. A nonowner with a stale model creates no database and cannot prevent the intended owner from initializing its pinned route.

Shutdown policy is drain, not rollback of already admitted work. Waiting for storage can delay cancellation acknowledgement by SQLite lock wait plus execution time; uninterruptible filesystem I/O is not given a fictitious hard deadline. No custom supervisor, unmanaged persistent worker, core patch or credential store was added.

## RED to GREEN

- `test_completion_rechecks_production_clock_after_write_lock`: expired completion returned True before the fix; returns False afterward.
- `test_failure_rechecks_production_clock_after_write_lock`: same reproduction for the failure transition.
- `test_nonowner_profile_cannot_change_execution_identity`: strengthened to prove no database creation and successful subsequent owner initialization; failed before ownership was moved earlier.
- `test_cancellation_drains_inflight_completion_before_termination`: observed premature termination before fix, now waits for the held mutation, including a second cancellation.
- `test_cancellation_drains_inflight_claim_before_termination`: same guarantee while a claim is in flight.
- `test_provider_swallowing_cancellation_cannot_apply_result`: reproduced continued processing before the fix; now terminates without persisting its synthetic result.

## Verification

Commands, all exit 0:

```sh
rtk proxy python -W error -m unittest discover -s tests -q
rtk proxy npm test
rtk proxy node scripts/build-ui.cjs --check
rtk proxy node --check desktop/plugin.js
rtk proxy git diff --check
```

Results: 70 Python tests and 10 Node tests passed. The six named regression cases also passed five consecutive repetitions in a single run (30 test executions). Synchronous SQLite fixture preparation was moved off the async test loop after an earlier repeat printed a 0.100-second slow-callback diagnostic; the final full suite and repeated-regression run completed without that diagnostic. No model calls or real publisher fetches were used in this fix pass.

The verification tree was fingerprinted before and after both final commands using HEAD plus sorted tracked/untracked nonignored paths and bytes. Fingerprints matched: `9a21f183bd4c4be5c90ae887a676dc336ea6187e64a7af7f6c2639ffd2254a06`. Subsequent changes were documentation/ledger updates only before commit.

Actual-host cold startup, supervision, model routing, authentication and remote asset delivery remain unverified. Task 6 and the final whole-branch review remain outstanding; these fixes do not close M1. No active installation, live restart, paid inference, push, merge or release was performed.
