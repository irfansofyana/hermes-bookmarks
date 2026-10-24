# Final trash/import review — author fix pass

Original independent review at `775cfa855c474a6a07adf3ff2f07e960e477ead9`: **changes requested**, no Critical, three Important. Original preserved unchanged in [report](trash-import-final-review.md). This document records author verification, not independent re-approval. Backend no-findings review at `ebbf973` did not cover this later integration.

## Controller UI fixes (commit `8b592c1a4c479110a745a6d339013f78602f07eb`)

- **I1 reproduced RED in both emitted clients:** `trashed_duplicate` removed the Add form; staged personal notes became unavailable. Fix classifies this as retained duplicate phase, keeps the entire draft, describes Trash/explicit restoration, and prevents the parent from reporting successful creation. Regression verifies Open existing then reopening Add keeps the notes. No overwrite or implicit restore.
- **M1 reproduced RED in both clients:** trashed card still offered Read later. Fixed to omit both mutating flag controls consistently while preserving Restore.
- **M2 reproduced RED in both clients:** cancel on offset 50 returned page zero but Previous remained enabled. `accept()` now adopts a validated integer server offset; result rows and page controls agree.
- **M4 added 20 deterministic ownership tests, all pass:** both emitted clients cover discarded delayed preview, close/reopen during Start and a pending poll, no duplicate Start/poll, unmount late-poll suppression and timer cleanup. Desktop covers profile and backend/library switch during file read, preview, Start, request lookup, inspection, cancellation and polling; old responses do not alter or refresh the replacement draft. Dashboard uses a mounted authenticated SDK scope; unmount is tested rather than inventing a live profile-switch SDK API. Timer injection is confined to the test harness.

Controller full **136 Node tests pass** after these UI fixes. Parser/native author commits have now been inspected and the combined suite passed: **184 Python tests on each of CPython 3.14 and 3.11; 136 Node tests**, deterministic build/Desktop syntax/whitespace. Slow-callback diagnostics remain nonfatal.

## Actual Dashboard UI confirmation

[`import-review-browser.json`](import-review-browser.json), actual isolated Hermes Dashboard/public SDK, no providers: imports a synthetic item, trashes it, attempts Add of the same URL with a new personal note, sees explicit Trash explanation, opens existing, returns to Add and retains the original unsaved draft. Backend readback confirms original imported note unchanged and item still trashed until explicit Undo. All four theme/viewport/focus/no-overflow cases and reload job inspection pass, no page errors. Initial browser driver attempted to fill a closed Notes disclosure; driver corrected to open it through the visible summary, then full run passed (no product patch for that harness error). Disposable UI-only copy over previously verified backend; this is I1/UI evidence, not a claim to have exercised the pending native/parser fixes in the host. Owned server stopped and port closure verified.

## Remaining findings resolved

- **I2**, commit `211b37cfa588fbc7256153dcb67518f90c059c0b`: native import Start/get/request lookup/cancel checks the durable accepted job settings off the host loop and activates the registered enrichment supervisor only for persisted opt-in. Default false, previews and rejected requests do not activate inference. New regression observed RED `0 != 1` tasks, then passed real plugin cold synchronous registration (`host_loop_unavailable`), native-only supervised import/enrichment progression with synthetic extraction/completion, persisted-job recovery and unload. No real provider call.
- **I3/M3**, commit `b875772cbe7a32ce8149f1391f225a9989d9b0c7`: ambiguous/unclosed H3 rejected rather than silently losing title/path; explicit DD owner prevents folder text contaminating preceding bookmark descriptions. Unsupported folder attributes/descriptions emit warnings. Exact reported malformed/content cases observed RED then GREEN; focused HTML/preview and final combined suites passed.

All three Important and four minor/coverage findings have an author disposition. Original changes-requested verdict remains unchanged; this is author verification, not a second independent approval. No additional speculative review loop is required. Exact-head remote publication/CI must be read back separately; local tests alone do not establish it.
