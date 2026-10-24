# Final-review fix pass

The independent whole-branch review examined `e7e0cc91cf71724c9d3caf7978308be462c78a77..d602bed8120fc67cd873abad97edea021c9c70d2`. Its original report is preserved unchanged in `final-review.md`: no Critical, three Important, two Minor findings, with separate code-quality and partial-spec verdicts. This document records the controller's one fix pass, not a second independent approval. M1 remains unaccepted at the host/model boundaries described in `m1.md`.

## Important findings: reproduced and fixed

### Accepted numeric URL crashed both rendered libraries

The new service regression first failed for each numeric-host example, and both real React/emitted-entrypoint regressions failed with `Invalid URL`. The first Node test harness attempt also rejected React's act thenable incorrectly; that harness error was corrected before the actual render failure was accepted as RED.

- Numeric final host labels now require canonical dotted-decimal IPv4 syntax. Malformed numeric hosts, noncanonical shorthand/hex/octal addresses and DNS-like names ending in a numeric label are rejected; input identity is never normalized or repaired. Ordinary hostnames, IPv6 and canonical IPv4 retain their existing behavior.
- Hostname display catches parse failure per record. A previously saved bad URL cannot blank the library or require deletion to recover the page; persisted records remain readable.
- The render test creates a real temporary SQLite library, inserts a frozen legacy row, reads the service's real JSON result in a Python subprocess and renders it through each emitted client with real React/jsdom. It checks both rows and the usable capture input. Node CI now explicitly supplies Python 3.11 for this integration test; `BOOKMARKS_TEST_PYTHON` may choose a local interpreter.

Tests: `test_invalid_numeric_hosts_are_rejected_without_saving`, `test_legacy_numeric_host_remains_readable_after_capture_validation_changes`, and each client's `an unreadable legacy URL cannot crash persisted library results`.

### Storage contention silently killed enrichment

All three new real-SQLite lifecycle regressions failed first: a recovered write lock left the job unprocessed, and exhausted/corrupt storage left health stuck at `started`.

- SQLite busy/locked primary and extended error codes become an internal `StorageBusyError` subclass. The external `storage_error` code/message are unchanged; raw SQLite text is never exposed.
- Only that transient class is retried, up to three attempts per storage operation, with 0.1/0.2-second inter-attempt waits. Permanent faults are not treated as contention. The existing SQLite busy timeout remains five seconds. Storage outages are not reclassified as provider failures or immediate additional model calls.
- Retained public task handles have completion observers. Unexpected exit updates status to `storage_unavailable`, `worker_failed` or `worker_stopped`; callbacks observe exceptions without leaking text. Metadata is scoped to the exact registration/task and removed on unload. Host `ctx.spawn_task` still owns cancellation.
- After terminal failure, the original owner's next authorized async entry can restart after a 30-second monotonic cooldown. Calls during cooldown and calls from another profile cannot create a restart storm. No background restart scheduler or private host integration was added.
- Executor shield/drain, cancellation admission checks, token/revision/lease fencing and original-owner guards remain intact and passed their existing regressions.

The fast tests shorten the *real connection's* busy timeout, not SQLite behavior. The observing connection can also encounter that shortened timeout; its bounded polling now tolerates only the typed busy condition. The first GREEN attempt exposed that observer issue, which was corrected without weakening worker/job assertions.

**Actual host confirmation:** the new snapshot was copied only into the disposable plugin home and started through real Hermes. A synthetic write transaction was held **7.027 seconds**, beyond the unchanged five-second SQLite timeout. Authenticated health responded while locked; after commit the existing worker consumed the intentionally incomplete job, `failed / configuration_required`, in one attempt. No API reactivation occurred between unlocking and job completion. Status was `started` before/during/after because the worker recovered and remained live. No publisher extraction or model call occurred. Raw sanitized evidence: `worker-contention.json`.

Tests: `test_real_transient_lock_recovers_without_losing_the_worker`, `test_exhausted_lock_budget_reports_failure_and_owner_can_restart_after_cooldown`, `test_corrupt_storage_terminates_visibly_without_retrying_or_reviving_unloaded_metadata`.

### Late save refreshed an obsolete search

Both emitted-client tests first showed `Alpha, Beta` after the user had successfully searched `Beta`. The save completion now refreshes the synchronously recorded current query instead of its old render closure. Search stays enabled during save; the result rows, heading, field and final request agree after the held POST finishes.

Test: each client's `finishing a save refreshes the current search instead of its old query`.

## Verification

- Full Python suite: **82 passed** on CPython 3.14.7 and **82 passed** on CPython 3.11.14.
- Full Node suite: **14 passed**, including four new real-React regressions across both emitted clients.
- Deterministic bundles, Desktop syntax and whitespace checks passed. Official isolated validation returned `ok: true`, no warnings, no core overrides, declared tools matching registration and accepted SDK surface.
- Real authenticated reopen/readback/asset smoke passed all 10 GET-only checks after the changes, including unauthorized item/asset rejection, original image decoding and preview decoding.
- The simultaneous 3.11/actual-host check used unchanged candidate fingerprint `0876328a9bc68c25b10bbe3e49cae548ebfe9495baeb64da5eb37f51d27f3efb` (HEAD, staged/unstaged diff and untracked file contents before/after). This is the candidate before these evidence documents were added, not a claim about a later docs hash.
- Nonfatal asyncio slow-callback diagnostics remained visible in fixture/package setup (roughly 0.11–0.28 s in these runs). They were not suppressed or counted as failures. All suites exited 0. No remote CI is claimed.

## Deferred minors

Both reviewer Minor grades stand; neither blocks safe internal capture/worker correctness, and neither is waived for the finished v1 UX:

1. The global Retry button only reloads the library; it does not retry a failed save/upload. Use the capture action again while its preserved input is available. Give recovery an operation-specific action or an honest Reload label in the next UI pass.
2. Narrow CSS hides item processing status. Capture still works and status remains available through native/API reads, but phone users do not get the wide-layout status cue. Reposition a compact visible status in the next UI pass.

## Rulings on the review's declined-to-judge items

These remain decisions/acceptance limits, not hidden omissions:

1. Keep M2–M5 organization, imports, notes, settings, exports, final polish, full UI pagination and automatic cross-view refresh in their planned milestones. Current preview browsing/status refresh is limited; API/native pagination remains available. Cost if wrong: the preview cannot meet full-manager expectations; it must stay labeled partial.
2. Do not waive actual connected Desktop/composer acceptance because fixtures passed. Keep it blocked at the isolated app's offline overlay without modifying core or bypassing UI. Cost if wrong: M1 cannot be accepted on that target yet.
3. Keep Dashboard editable contextual handoff unavailable until a supported contract is verified or the owner explicitly revises acceptance. Navigation alone is not equivalent. Cost if wrong: the current SDK cannot meet that part of the requested experience.
4. Do not infer provider text/vision, trust or routing success from a deliberately unconfigured queue probe. Real calls require approval; no active secrets were copied. Cost if wrong: inference compatibility remains unknown until the approved test.
5. Keep independent-machine/OAuth and maximum proxy payload verification open. Loopback token-mode evidence is narrower. Cost if wrong: remote transport/limits can still expose a target-specific incompatibility.

No second review loop was dispatched. No active installation, production restart, live inference, push, merge or release occurred. Preserve the local plan workspace while these acceptance gates remain; do not report full M1 completion or begin future milestones as if those gates had passed.
