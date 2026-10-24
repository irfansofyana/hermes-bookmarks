# Final independent UX polish / selection review

Reviewed immutable `63bea80cac78ec882737ffc70e27c9aca3a8203c` against `a31b5be4544198325f10f609aafe40c2f632a2c5`.

**Verdict: REQUEST CHANGES — one Important async/interaction defect. No Critical finding.**

## Important

### I1. A late admitted batch result never refreshes a remounted owner of the same scope

**Locations:** `ui/library-bulk.js:23`, `ui/library-bulk.js:62-71` (particularly line 71); integration at `ui/library.js:73`.

**Exact reproduction (controlled emitted Desktop harness, immutable bundle):**

1. In connection A, select two active, non-favorite items and open Edit selection. Apply Add to Favorites; hold the first `/items/a/update` response while its request is admitted.
2. Switch connection A → B → A before releasing that response. The returning A library loads the still-old records. Open Edit selection again; the scoped report is still running.
3. Commit/resolve the held response with item a favorite=true, revision=4.
4. The report updates to Applied: 1 / Not processed: 1, correctly sends no second mutation, but the returning A item page is not refreshed. Close the report: item a still displays the non-favorite control and old revision.

**Observed probe output:** `writes=1`, item-page reads before/after resolution `3/3`, fixture saved favorite `true`, visible `Mark favorite Probe a` has `aria-pressed="false"`, and no `Remove favorite Probe a` control exists.

**Cause / impact:** the surviving report listener only repaints the report (line 23). Completion invokes `onChanged` exclusively through the now-unmounted initiating component's `current()` (line 71), so it suppresses the necessary refresh even when a new, correctly scoped owner is already mounted. Metadata and filter/count membership remain stale after an acknowledged successful mutation; Trash/Restore have the same completion path. Expected revisions still protect backend integrity, but the UX completion/refresh acceptance fails and subsequent card actions use stale records.

**Required direction:** make completion invalidate/refresh the currently mounted owner of the matching scoped report, including a remount that precedes the admitted result. Retain the current protection against refreshing B, and never resume the stopped remainder. Add this A → B → A ordering as a focused regression; do not merely remove the scope guard or invoke the old component callback.

## Minor

### M1. Bulk tags reject valid supplementary-Unicode labels prematurely

**Location:** `ui/library-bulk.js:12`.

The new tag limit uses JavaScript UTF-16 `.length`, whereas the existing authoritative API validates NFC-normalized Unicode characters (`bookmarks/tags.py:11`, `bookmarks/labels.py:11,18-21`). Repro: select an item, choose Add tags, enter `"😀".repeat(41)`, then Apply. The emitted Dashboard probe reports 41 Unicode code points / 82 UTF-16 units, sends zero writes, and shows “at most 80 characters each.” The API's 80-character bound permits that label. Normalize/count consistently with the API; retain strict bounds and malformed-Unicode rejection.

## Verification and acceptance assessment

- All source, reviewed tests, helper code and loaded emitted bundles were obtained from `git show` at the immutable reviewed commit. The shared worktree HEAD advanced independently during review; no conclusion is based on its moving source.
- Ran only the immutable focused `test_library_bulk.cjs` and `test_library_polish.cjs`: **29 passed, 0 failed**. No full suite, build, install, external service or provider/model call.
- Added in-memory adversarial probes, without creating test files: reproduced I1; independently confirmed late read-only hydration after a scope switch sends zero writes and no further requests; reproduced M1.
- Inspected the recorded Dashboard manifest and the narrow light form, narrow light bulk review, and wide dark detail screenshots. Those samples show reachable actions and distinct personal/generated/source sections. The manifest records broader wide/narrow/theme, validation-retention, save/View and real metadata/conflict/Trash/Restore evidence; this review did not rerun those service-backed browser checks.
- Focused tests cover explicit reviewed revision writes, synchronous duplicate-Apply prevention, partial conflict, lost-ack stop/no replay, Stop preserving admitted outcomes, bounded selection, paged collection lookup, quoted Unicode tags, dirty-close/validation retention, safe separated detail content and save/View outside filters.
- Immutable diff whitespace check passed. No code, index, HEAD, generated bundle or tracked artifact edits were made. Only this ignored report was written.
- Connected packaged Electron acceptance remains open; emitted React fixtures and recorded Dashboard browser evidence do not establish it. Old import/enrichment/M1 behavior was not re-reviewed.
