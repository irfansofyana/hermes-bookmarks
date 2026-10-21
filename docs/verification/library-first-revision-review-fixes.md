# Library-first final review fixes

Scope: the approved eight-task workspace revision, still a development preview. This is author verification, not a second independent review or permission to merge.

## Original review

The independent final report reviewed `e3cbfc90f0db21b1238023962a6e9a308972b8f4..d26a7bbe8e09545336ab938f34ed0c3ce2e2e1c3`. It found six Important issues and two Minor issues, with no Critical issue identified in its reviewed surface. Its quality/security verdict was FAIL and its spec verdict NOT SATISFIED. The later B1 migration fix was excluded from that review.

The original is preserved unchanged in [library-first-revision-review.md](library-first-revision-review.md), SHA-256 `eb428da2602c077451ffbcf16f6c5b8555e7c9f0af7ea4840e992df8e35f2fa4`. The separate backend report and its B1 fix retain their own original verdicts and evidence. No original FAIL verdict has been rewritten as PASS.

## One author fix pass

`tests/test_library_review_fixes.cjs` and the emitted-client helper reproduce the six findings. The test command was run before the product changes and failed. An additional frozen `9850b4eecbb4c0351a4ee3abb259ef2277c71cd7` counterproof, with only the new test/helper copied into disposable scratch, failed all 14 new cases with zero passing or skipped. The fixed emitted bundles pass all 14, and the complete Node suite passes 100 tests.

| Finding | Fix | Regression and additional evidence |
| --- | --- | --- |
| I1: SDK exceptions bypass domain handling | The common public-request boundary parses only bounded recognized domain errors from Dashboard `ApiError.status/body`; unknown transport outcomes remain uncertain. Missing receipts enable only explicit original-key retry. | Both loaders test SDK-shaped 400/404; 409 is exercised by I4. Actual Dashboard/public SDK returned real 400/404/409 and completed recovery. |
| I2: unchanged comma-containing tags are rewritten | Untouched tags retain their original array. Edited labels use quoted CSV in a multiline field, preserving commas, quotes and newlines; tag deltas are explicit. | Notes-only saves preserve generated-label identity, Unicode, case aliases and newlines. Actual saved comma tag survives a conflict-resolved notes edit. |
| I3: remounted form loses operation ownership | Operation completion updates its immutable connection/library/draft record and notifies current subscribers. Accepted responses and asset IDs survive same-library profile remounts; visible publication still checks the active scope. Pre-dispatch rejection is distinct from an unknown post-dispatch result. | Desktop profile ABA accepted save and participating-profile upload recovery; existing different-backend late-save and discarded-upload isolation tests remain green. |
| I4: Keep editing repeats the stale revision | Keep editing fetches and displays the saved version without replacing local fields. Use reviewed revision explicitly rebases local dirty fields while adopting unedited remote fields; a separate Save still checks that revision. | Both loaders submit revisions `[1,2]` and retain local notes plus the remote description. Actual concurrent HTTP edit produces a real SDK 409, then compare/rebase/save succeeds. |
| I5: navigation resize discards collection form | One navigation owner survives responsive presentation changes. Collection drafts and pending outcomes also live at the connection/library identity and notify current subscribers. | Both loaders retain a typed collection name through narrow/wide changes and close the correct form after its pending save. Actual Dashboard resizes an open collection form, then saves it. |
| I6: refresh appends a duplicate page | Paging cursors include scope/query/parent/revision. Invalidation resets and replaces page zero; extension merges by stable row identity. | Both loaders load 51 tags and 51 collections, save, then show unique rows and refreshed first-page counts. Existing item/tag paging remains green. |

## Complete gate

Command: `rtk proxy python /home/irfansofyana/.hermes/cache/scratch/library-final-gate.py` (local test orchestration, not a plugin dependency).

- CPython 3.14.7: **147 tests passed** with `-W error`.
- CPython 3.11.14: **147 tests passed** with `-W error`.
- Node: **100 tests passed**, zero failed/cancelled/skipped.
- Deterministic bundles, Desktop ESM syntax and working-tree whitespace: passed.
- Tracked/nonignored tree fingerprint stayed `5e67cfa4e4f1e3ac71e71145686d578d6dac35a81a3383106b907e9601b6d2f7` throughout all six checks. This identifies the tested fix tree over `9850b4e`; evidence/documentation added afterward is not retroactively included in that fingerprint.
- Official isolated validation: `ok: true`, host-ready, declared registrations match. The same two disclosed bundled-Marked scanner cautions remain. Nonfatal asyncio slow-callback diagnostics remain visible.
- Real native registry read parity passed for get/counts/library identity/capture status, against the existing synthetic item and receipt.

## Fresh actual Dashboard

The real loopback Dashboard loaded the regenerated bundle and public SDK against disposable, credential-free library settings. There were no page JavaScript errors, no document/workspace/dialog horizontal overflow, and no provider inference or prompt/session creation.

The browser passed real SDK validation rejection, real missing-receipt recovery, actual revision conflict comparison/rebase, unchanged comma-tag preservation, image upload/association/edit/readback, collection draft resize, forward **and reverse** Tab containment, dirty Escape/keep/discard/focus return, theme switching, dark/light at 1440/390 px, container-resized chat/library, preserved unsent chat text and page-reopen persistence.

The unknown-outcome test explicitly aborts one capture before network dispatch. The subsequent receipt 404 and explicit retry are actual HTTP/SDK operations. No successful API or provider result is fabricated. These fault assertions supplement the existing separate lost-acknowledgement protocol/service tests; they do not claim that an already committed request lost its acknowledgement in this particular browser case.

The eight synthetic library/form screenshots were refreshed. Detailed sanitized observations are in `library-first-workspace.json`. This is actual Dashboard acceptance, not connected packaged Electron acceptance.

## Deferred minors

- Author formatting note: the byte-identical original final report contains an intentional two-space Markdown hard line break at line 3. The staged diff check flags it as trailing whitespace. Those original bytes and its checksum are preserved; the staged/range whitespace checks are not described as clean.
- M1: saving outside the active filter lacks the promised View item notice action. The save persists correctly and the current filter stays intact; finding the new item requires changing filters/search.
- M2: `ui/chat.css` retains one trailing blank line. Working-tree `git diff --check` passes, but the original approved-baseline committed-range check fails with `new blank line at EOF`. This has no attributed runtime effect. It remains an explicit deferred Minor, not a falsely green range check.

## Remaining limits

Connected packaged Electron/public Desktop Dialog, successful real-provider text/vision, OAuth, independent-machine transport and maximum proxy payload acceptance remain open. Module-memory draft retention does not survive a full page reload or process exit; abandoned staged assets are retained without garbage collection/quotas in this slice. Full screen-reader/short-height accessibility certification, rich-text/inline images, configurable vision/settings, import/export and trash/restore remain outside this revision's proved scope.

The one independent review and the one author fix pass are consumed. Continue through the existing draft PR and exact-head CI; no speculative re-review, live installation, merge or release is authorized. See `docs/STATUS.md` for the current publication state.
