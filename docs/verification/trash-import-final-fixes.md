# Final trash/import review — author fix pass

Original independent review at `775cfa855c474a6a07adf3ff2f07e960e477ead9`: **changes requested**, no Critical, three Important. Original preserved unchanged in [report](trash-import-final-review.md). This document records author verification, not independent re-approval. Backend no-findings review at `ebbf973` did not cover this later integration.

## Controller UI fixes (commit `8b592c1a4c479110a745a6d339013f78602f07eb`)

- **I1 reproduced RED in both emitted clients:** `trashed_duplicate` removed the Add form; staged personal notes became unavailable. Fix classifies this as retained duplicate phase, keeps the entire draft, describes Trash/explicit restoration, and prevents the parent from reporting successful creation. Regression verifies Open existing then reopening Add keeps the notes. No overwrite or implicit restore.
- **M1 reproduced RED in both clients:** trashed card still offered Read later. Fixed to omit both mutating flag controls consistently while preserving Restore.
- **M2 reproduced RED in both clients:** cancel on offset 50 returned page zero but Previous remained enabled. `accept()` now adopts a validated integer server offset; result rows and page controls agree.
- **M4 added 20 deterministic ownership tests, all pass:** both emitted clients cover discarded delayed preview, close/reopen during Start and a pending poll, no duplicate Start/poll, unmount late-poll suppression and timer cleanup. Desktop covers profile and backend/library switch during file read, preview, Start, request lookup, inspection, cancellation and polling; old responses do not alter or refresh the replacement draft. Dashboard uses a mounted authenticated SDK scope; unmount is tested rather than inventing a live profile-switch SDK API. Timer injection is confined to the test harness.

Controller full **136 Node tests pass** after these UI fixes. Parser/native fixes are independent parallel author tasks and require completion/readback and final dual-Python tests before the whole milestone is considered verified.

## Actual Dashboard UI confirmation

[`import-review-browser.json`](import-review-browser.json), actual isolated Hermes Dashboard/public SDK, no providers: imports a synthetic item, trashes it, attempts Add of the same URL with a new personal note, sees explicit Trash explanation, opens existing, returns to Add and retains the original unsaved draft. Backend readback confirms original imported note unchanged and item still trashed until explicit Undo. All four theme/viewport/focus/no-overflow cases and reload job inspection pass, no page errors. Initial browser driver attempted to fill a closed Notes disclosure; driver corrected to open it through the visible summary, then full run passed (no product patch for that harness error). Disposable UI-only copy over previously verified backend; this is I1/UI evidence, not a claim to have exercised the pending native/parser fixes in the host. Owned server stopped and port closure verified.

## Pending author tasks

I2 native cold-start opt-in activation and I3/M3 HTML metadata ownership/warnings are assigned scoped test-first fixes. Consume their real outputs and inspect actual diffs before updating this disposition. No final publication or CI green is claimed here yet. No additional speculative review loop is required after justified fixes and exact-head CI are verified.
