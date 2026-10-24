# Final independent trash/import milestone review

**Verdict: changes requested.** No Critical defect found; three Important findings below. Scope is immutable `775cfa855c474a6a07adf3ff2f07e960e477ead9` against `c1abe3cf7b5da7d3d4b5dea615e9a7d7c77e5f0c`, concentrating on later HTML/native/HTTP/UI integration. This does not reopen the earlier M1 foundation review or repeat the completed targeted backend review.

All source and emitted-client fixtures were obtained with `git show` from the immutable snapshot. Focused probes ran snapshot code in memory, with synthetic input and stubbed API/host dependencies. No full suites, publisher/provider requests, installation, service changes, index/HEAD/source edits, or publication were performed. Only this ignored report was written. Existing controller test/browser/restart evidence was supplied context, not independently repeated here.

## Important

### I1 — Capturing a trashed duplicate silently destroys the Add draft and reports success

**Locations:** `bookmarks/items.py:139-140` introduces `trashed_duplicate`; `ui/library-form.js:32-35` only recognizes `duplicate`; `ui/library.js:51` also treats every other outcome as successful creation.

Repro on either emitted client:
1. Trash URL A.
2. Add A again with new personal notes or other staged metadata.
3. Backend correctly returns the existing trashed item and receipt outcome `trashed_duplicate`, without applying those fields.
4. `finish()` takes the saved path, deletes the draft through the saved-phase listener (`ui/library-form.js:24-28`), closes Add and displays “Saved to your library.” No existing-item/restore explanation appears, and A remains absent from All.

Independent real-React emitted-client probe supplied that exact backend receipt after a normal Add form submission. Both Desktop and Dashboard returned `notice=true`, `draftField=false`, `openExisting=false`: the new notes draft disappears without being saved or warning about the duplicate.

Handle `trashed_duplicate` as a retained duplicate draft with an explicit trashed-state explanation; do not silently restore. Offer inspection/explicit restore separately. Extend the existing duplicate/uncertain-save tests to cover this new receipt outcome. This violates the plan's explicit trashed-duplicate outcome and preservation of personal draft ownership.

### I2 — Native opt-in imports never activate the enrichment worker on a cold synchronous host

**Locations:** `native_tools.py:152-155`; startup context `__init__.py:7-11`, `worker_host.py:29-36`, and `runtime.py:117-133`. Contrast HTTP `dashboard/plugin_api.py:11-15`, which activates enrichment on every request.

Repro:
1. Use the supported synchronous registration path with a valid configured enrichment owner/route. Startup persists the route but returns `host_loop_unavailable` because no event loop is running yet.
2. Through native tools only, preview with `options.enrich=true`, Start, then poll with `bookmark_job_get`.
3. Each native import tool calls only `ensure_imports()`. The importer completes and atomically queues enrichment jobs, but no call retries `start_registered_enrichment()` on the now-available async host lane. The jobs remain pending until an unrelated `bookmark_save` or HTTP request activates enrichment.

Independent handler-dispatch probe of the snapshot recorded only `['imports']` for native Start/get/cancel/request-get; no enrichment activation. The cold-registration outcome and pending-work consequence follow directly from the production startup/activation code, not a live provider test.

Ensure the native import path activates the configured enrichment owner when needed, without enabling inference for `enrich=false`. Add a cold synchronous-registration/native opt-in import regression with a synthetic supervised worker; assert worker activation/progression without requiring a save or HTTP request.

### I3 — HTML folder/description state silently imports incorrect metadata instead of reporting malformed/unsupported structure

**Locations:** `bookmarks/imports/html.py:18-29,37,43,49-53,65-67`.

Two independently executed snapshot-parser repros:

A. Missing H3 closer:
```html
<DL><DT><H3>Folder<DL><DT><A HREF="https://example.org/a">A</A></DL></DL>
```
Actual result: one row with `title=''`, `collection_path=[]`, `_html_warnings=[]`. The folder accumulator remains active and consumes the link title, while only `</H3>` can establish the pending folder. Balanced DL tags suppress even the unclosed-structure warning. Preview therefore presents a valid row with silently lost title/hierarchy. The approved plan explicitly requires malformed nested HTML to be bounded and reported, without silent flattening. Reject this ambiguous structure or recover it deterministically with an explicit warning; do not report it as a clean valid import.

B. A folder description after an existing bookmark:
```html
<DL><DT><A HREF="https://example.org/a">A</A><DD>Actual A description
<DT><H3 ADD_DATE="123">Folder</H3><DD>Folder description
<DL><DT><A HREF="https://example.org/b">B</A></DL></DL>
```
Actual result: A's description is `Actual A descriptionFolder description`; neither row has a warning. `DD` attaches to `rows[-1]` regardless of whether the immediately preceding entry was a bookmark or folder. Folder metadata must not be attributed to a preceding bookmark. Track DD ownership explicitly and warn about unsupported folder metadata.

Both repros are supplied bytes only; no source files/network were used. Add exact-content/path assertions for these cases, not only reconciled row-count assertions.

## Minor findings / plan gaps

- **M1 — Trashed cards retain an enabled Read later mutation:** `ui/library-items.js:12` guards Favorite with `!item.deleted_at`, but not Read later. Clicking Read later on Trash always conflicts because `bookmarks/items.py:187-190` rejects updates to trashed items. Hide/disable it consistently rather than advertise an operation guaranteed to fail.
- **M2 — Cancellation desynchronizes result pagination:** `ui/library-import.js:23` accepts the cancel response without changing `state.offset`; `bookmarks/imports/preview.py:87-92` returns the default offset-0 results. Cancel while viewing offset 50 displays rows 1–50 while UI pagination remains at offset 50. Adopt `job.offset` when accepting the response or re-fetch the selected page. This affects presentation, not persisted counts/effects.
- **M3 — Folder attributes are silently dropped:** `bookmarks/imports/html.py:21,34-35` reports unsupported A attributes but never inspects H3 attributes. `H3 ADD_DATE="123"` produces no unsupported-date/attribute warning. Plan Task 4 requires unsupported metadata to be reported, not represented as preserved.
- **M4 — Required integration/race evidence is narrower than the plan:** snapshot `tests/test_import_ui.cjs` covers explicit preview/start, discarded file-read epoch, uncertain Start lookup and saved-job pagination. It does not exercise profile/library switch during each await, close/reopen during Start and polling, stale polling response ownership, or cancellation during running state as called for at plan line 188. This is a coverage gap, not an assertion those races currently fail. Existing scoped draft keying and request ownership were inspected; no additional concrete cross-scope write was established.

## Boundaries and positives

The HTTP import routes reuse strict streamed metadata parsing, reject duplicate keys/nonfinite constants, and use the persisted import-kind APIs rather than enrichment/chat job dispatch. The importer continues to use immutable admission, transaction-scoped duplicate checks, row/cursor/result commits, revision-checked trash and lease fencing; no new concrete transactional regression was established in this final integration review. This is not a fresh whole-backend approval.

Future export/restore, settings/text/vision controls and rich editor work remain explicitly outside this approved milestone; their absence is not listed as a defect. Full target acceptance, publication/CI and active installation are not claimed by this review.
