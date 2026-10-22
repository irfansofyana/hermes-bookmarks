# UX polish and reviewed selection actions

Date: 2026-10-22. Tested snapshot `63bea80cac78ec882737ffc70e27c9aca3a8203c`; base `a31b5be4544198325f10f609aafe40c2f632a2c5`. Owner approved the in-chat UX direction and immediate implementation. Development-only copies; active installation untouched.

## Delivered

- Add/Edit dialog variant with 760 px desktop width, responsive essential fields, readable optional sections and sticky primary footer. Same existing state machine, field labels, uploaded IDs, duplicate guards, uncertain receipts and expected revisions. Native/public SDK adapters both retain close guards.
- Detail variant at 800 px separates personal notes, saved AI summary, import/source provenance and images. Source-provided summaries are not labeled generated. No remote page/image loading on read outside authenticated owned assets; Markdown remains allowlisted.
- Select visible page, capped explicit selection (100 items), reviewed batch actions for collection, quoted Unicode tags, Favorite/Read later and recoverable Trash/Restore. Existing single-item revision-checked APIs remain authoritative. No new batch scheduler/database or separate native API.
- Review reads saved detail first. Apply freezes those revisions and one action, sends sequential writes without automatic retry/rebase, and reports applied/conflict/failed/skipped/uncertain/not-processed separately. Successful partial changes remain. Stop/unmount prevents further dispatch; an in-flight request cannot be recalled. Lost acknowledgement halts remaining writes and requires saved-state inspection before a new action. Reports are scoped in-memory only, not durable jobs; reload loses the report and never resumes mutations.
- Saved notice has View item even when the new item is outside the current filter; reading it does not change the filter or create a chat turn.

## Tests and review

At the snapshot above, **184 Python tests pass on each CPython 3.14.7 and 3.11.14; 165 Node tests pass**. Deterministic bundles, Desktop syntax, browser-driver syntax and whitespace pass. Existing nonfatal asyncio slow-callback diagnostics remain visible.

New emitted-client tests: 23 selection cases (both hosts plus Desktop backend switch) cover read-only review/refresh, failed hydration, pagination, 100 cap, reviewed revision payloads/double Apply, partial conflicts, unknown acknowledgement halting subsequent writes, tag quoting, Stop, Trash compatibility and View item. Six presentation tests cover both adapters and safe detail rendering. New interaction tests were observed RED before implementation; additional boundary checks that passed existing behavior were retained as coverage, not called new RED fixes.

Official isolated `plugins validate` passed: registration inventory, no collisions/core overrides and supported Desktop surface. Two known scanner cautions on bundled Marked JavaScript regex syntax remain (`inline_shell_exec`), not shell execution. Host isolation is not a security sandbox.

Final independent UX review `deleg_24791731` returned REQUEST CHANGES: one Important refresh defect and one minor Unicode limit mismatch. Important was reproduced and fixed; final gates **184 Python each on 3.11/3.14; 167 Node** pass. [Original](ux-polish-final-review.md) and [author fix/deferred minor](ux-polish-review-fixes.md). No independent re-approval or exact-head remote CI is claimed by this document. The earlier import slice's exact-head push and PR runs at `a31b5be` were both read back successful before this work; they are not CI for UX.

## Actual Dashboard/public SDK

[`polish-browser.json`](polish-browser.json) and twelve `screenshots/bookmarks-polish-*.png` files come from a real built Hermes Dashboard using the plugin loader/backend and SDK. Synthetic records only; no real model call or personal vault input.

Verified:

- Dark/light form and detail at 1440/390 px. Actual form width 760 px desktop / 378 px phone; detail 800 / 378 px. No dialog/document horizontal overflow. Forward/reverse Tab stays inside each tested modal. Save footer reachable after scrolling; screenshots intentionally show the scrolled editing position, not a missing heading.
- Dirty Escape/Keep editing, discard, preserved notes through resize, and narrow 480 px plugin tile in a wide viewport. Invalid `file:///not-authorized` save returns real validation and keeps the edited title with Save available.
- Save outside search then View item shows saved detail while preserving the query.
- Real reviewed multi-item Favorite, then concurrent note edit after review: two items applied and one revision conflict. Bulk Trash then Restore kept all records and the concurrently edited note. Narrow bulk review also passed focus/bounds checks. No silent all-or-nothing claim.
- No page errors. Wide dark form, narrow light form, library dark and detail light screenshots were inspected directly. Layout is more spacious; light remains the selected Nous Blue theme by design, without a plugin-owned/global recoloring override.

Driver preparation exposed intermittent seed-read timing when using an async browser wait predicate. The completed driver uses explicit bounded native-side job polling and asserts exactly three newly imported records before UI search. Earlier timeouts were preserved as failed harness runs, not product acceptance or fabricated screenshots. Final run passed all recorded checks.

Disposable Dashboard was stopped and its owned port closure verified. Connected packaged Electron remains unproven; emitted Desktop React tests are not a substitute. Remote/OAuth, successful real provider and full release gates remain open.

## Remaining product scope

This delivers UX-first work only. Export/lossless backup-restore, settings/text+vision controls, full rich-text/inline images and final acceptance/docs remain required next. No merge, release, catalog submission or active deployment is authorized.
