# Recoverable trash and import-first migration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans with the owner's existing hybrid workflow. Implement directly with TDD, one targeted data-integrity review and a final revision review. Steps use checkbox syntax for tracking. This is the next milestone plan, pending owner review; no approval of this new file is inferred from approval of the previous workspace plan.

**Goal:** Add recoverable trash and safe, durable normalized-record/bookmark-HTML imports to the existing library, native tools and both client UIs.

**Architecture:** Extend the shared SQLite service with atomic revision-checked trash, immutable preview staging and independently fenced import jobs. Reuse the current item/collection/tag/asset validation and public host supervision; adapters remain thin. Import operates only on supplied bytes/records, never source paths, and performs no publisher fetch or inference unless enrichment is explicitly selected.

**Tech stack:** Python standard library (`sqlite3`, `html.parser`, `hashlib`, `json`), existing FastAPI adapter, public Hermes native-tool/task APIs, existing React/shared emitted UI and Node test harness. No new runtime dependency is needed for HTML parsing.

**Spec:** `docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md`, sections 4, 7, 8, 10 and 11; the approved library-first workspace design remains binding for existing presentation/draft ownership.

## Baseline and global constraints

- Start from existing `feat/m1-native-foundation` linked worktree. Verified baseline `aa102e0fc755261441464008f4b8ee4fc58c13c9`; do not recreate PR #1 or the worktree.
- Collections/tags/grid/list/pagination/Add-Edit/Markdown notes/owned image associations/collapsible chat already exist. Do not implement them again.
- One shared installation library. Profiles are not a data privacy boundary. Chat/session identity remains profile/backend scoped.
- No Hermes core edits, private imports, copied host internals, replacement agent loop or separate credentials.
- Preserve existing manual edits, notes, tags, asset associations, original URL identity and legacy accepted data.
- Source files remain unchanged. No arbitrary local path, remote URL fetch, executable import payload or incidental-link extraction.
- Native and HTTP operations share validation/business logic. Authenticated adapters are not replaced by a standalone test server.
- Publish only into existing draft PR #1 after exact-head CI. Merge, release, active installation and production restart remain unauthorized. Synthetic provider checks are approved separately; this milestone does not require them.
- Rich-text/inline-image editor, settings/text/vision controls, portable export/restore and full target acceptance remain explicit subsequent milestones, not omitted release requirements.

## Review focus

1. Trash during in-flight enrichment: a late worker result must not revive or alter the trashed record; Task 1 adds a held-result regression.
2. Lost import-start response or two worker processes: one accepted job, one effect per input row, accurate reports; Tasks 2/3 race real SQLite connections.
3. Source import overlaps with manual notes edits: existing items must be skipped, never merged implicitly; Tasks 2/3 freeze skip-existing semantics and snapshot races.
4. Nested malformed HTML and normalized-name collisions: explicit paths, bounded parser, no flattening or silent data corruption; Task 4 covers malformed/frozen fixtures.
5. Cancel/crash after some records commit: progress counts reconcile, committed items remain, lease fencing prevents stale writes; Task 3 exercises both commit/cancel orderings.

## Public interfaces and limits

### Trash

```python
BookmarkService.trash(item_id: str, expected_revision: int) -> dict
BookmarkService.restore(item_id: str, expected_revision: int) -> dict
# Existing search accepts view='trash'; all other views exclude deleted_at != NULL.
# Existing get returns the record with deleted_at for explicit ID lookup.
```

`bookmark_delete` means move one item to recoverable trash, not permanent deletion. Both operations require the displayed expected revision. Repeating the same desired state at its current revision is a no-op; stale revisions conflict. No permanent-delete API or bulk destructive operation is introduced here.

Trash sets `deleted_at`, increments item revision and enrichment generation, cancels pending/running enrichment claims atomically and retains all attachments/notes. Restore clears `deleted_at` and increments revision/generation; it does not enqueue inference. Collection deletion still moves every affected item, including trashed items, without deleting content. Duplicate capture of a trashed URL returns that record plus an explicit `trashed_duplicate` outcome; it does not silently restore or overwrite it.

### Normalized records

```json
{
  "source_id": "reading-list:42",
  "url": "https://example.org/article?keep=1#section",
  "title": "Saved article",
  "description": "Imported description",
  "collection_path": ["Engineering", "Backend"],
  "tags": ["systems"],
  "notes": "Personal **Markdown** notes",
  "imported_summary": "Unverified source summary",
  "source_text": "Source-provided text, not publisher retrieval",
  "attachment_ids": [],
  "provenance": {"source": "Selected reading list", "locator": "row 42"}
}
```

Only link records in this milestone. Existing standalone image creation remains available through capture; archive/asset-byte migration belongs to export/restore. Accept only existing owned attachment IDs, never local paths or remote images. At most 500 records and 2 MiB UTF-8 per preview; each record uses existing title/notes/tag/asset limits, collection depth at most 16. Imported summary limit 16,000 characters; retained source text at most 30,000 characters; source identifier/locator at most 300 characters each. Unknown fields appear in warnings and are not represented as preserved. No records are created from links inside notes.

Only duplicate policy `skip_existing` is supported initially. Duplicate rows within a batch and URLs already in the library, including trash, are reported separately; they never update existing metadata. `source_id` is provenance, not permission to overwrite a URL. Source summary/text are explicitly imported/unverified, not generated. Preserve their provenance in a dedicated record; do not change generated-summary provenance to pretend inference ran.

```python
BookmarkService.import_preview(records=None, html=None, options=None) -> dict
# Exactly one input. options={'duplicate_policy':'skip_existing','enrich':False}
# Returns preview_id, input_digest, expires_at, total, valid, invalid,
# duplicate_in_batch, existing, rows:[{index,status,warnings,error_code}], options.
# Persists bounded staging only, not library item/collection/tag/asset mutations.
BookmarkService.import_start(preview_id, input_digest, request_id) -> dict
# request_id canonical UUID; returns immutable accepted job identity.
BookmarkService.import_job_get(job_id, limit=50, offset=0) -> dict
BookmarkService.import_job_cancel(job_id) -> dict
BookmarkService.import_request_get(request_id) -> dict
# Read-only admission lookup; missing request returns not_found, never starts work.
```

Preview expiry is 24 hours at first start. An already accepted request remains readable/retry-idempotent after expiry. Reusing request ID with a different preview/digest conflicts. Preview options/payload are immutable; execution never accepts replacement records. Library duplicates are rechecked inside each commit transaction, not trusted from preview time. Invalid rows remain visible/reportable and do not prevent valid rows importing after explicit preview/start.

Jobs expose `pending/running/succeeded/cancelled/failed`, plus `total/processed/imported/skipped/failed/remaining`. At every checkpoint `processed = imported + skipped + failed` and `total = processed + remaining`. Terminal cancellation preserves remaining count, not falsely labels it imported. Result rows are paginated and carry stable input indexes, item IDs where applicable, outcome and safe error codes.

## Task 1: Recoverable trash across persistence, jobs and UI

**Files:** create `bookmarks/trash.py`, `tests/test_trash.py`; modify `bookmarks/migrations.py`, `items.py`, `queries.py`, `collections.py`, `jobs.py`, `service.py`, `native_tools.py`, `plugin.yaml`, `dashboard/plugin_api.py`, `ui/library.js`, `library-navigation.js`, `library-detail.js`, `library-items.js`, generated bundles; add emitted-UI regressions.

**Consumes:** schema version 6, `items.load/project`, `Storage._transaction`, `ConflictError`, current expected-revision UI controls. **Produces:** schema 7 `items.deleted_at REAL`, index on deletion/collection, trash/restore service/native/HTTP operations, Trash view and counts.

- [ ] Write RED service tests using a real temporary library:

```python
item = service.capture(url='https://example.org/trash', notes='Keep me')['item']
trashed = service.trash(item['id'], item['revision'])
self.assertEqual(service.search()['total'], 0)
self.assertEqual(service.search(view='trash')['items'][0]['notes'], 'Keep me')
self.assertIsNotNone(trashed['deleted_at'])
with self.assertRaises(ConflictError):
    service.restore(item['id'], item['revision'])
restored = service.restore(item['id'], trashed['revision'])
self.assertIsNone(restored['deleted_at'])
self.assertEqual(service.get(item['id'])['notes'], 'Keep me')
```

Also hold a claimed enrichment result, trash, release completion and assert no summary/tag changes; verify capture of trashed duplicate is explicit; collection/tag/count filters exclude trash; restoring an image retains primary/attachment IDs. Freeze schema-6 writer fixtures for upgrade preservation and concurrent migrations.

- [ ] Run `rtk proxy python -m unittest discover -s tests -p test_trash.py -v`; expect missing-method failures before production edits.
- [ ] Implement one migration and transaction-scoped state transition. Extend every affected count/query and manifest inventory. Register `bookmark_delete`, `bookmark_restore`, `POST /items/{id}/trash`, `POST /items/{id}/restore`; use existing bounded metadata request parser and conflict mapping. No file deletion.
- [ ] Add UI RED tests for explicit confirmation, revision conflict, Undo/restore, narrow view and filter-preserving refresh; use existing public dialog factory. Implement Trash nav and per-item actions without automatic bulk destructive effects.
- [ ] Run Python/Node full suites and deterministic build; commit `feat: add recoverable item trash and restore`.

## Task 2: Immutable validated import previews and idempotent admission

**Files:** create `bookmarks/imports/__init__.py`, `records.py`, `preview.py`, `schema.py`, `tests/test_import_preview.py`; modify migration tuple and service facade.

**Consumes:** `validate_url`, `metadata`, `normalize_tags`, `normalize_label`, owned asset validation and schema 7. **Produces:** schema 8 staging/job/result tables; the preview/start/get/cancel contracts above.

Tables: `import_previews(id,digest,payload,options,report,created_at,expires_at)`; `import_jobs(id,preview_id,request_id UNIQUE,digest,state,cursor,total,imported,skipped,failed,worker,token,expires,cancel_requested,error)`; `import_results(job_id,row_index,outcome,item_id,error,warnings,PRIMARY KEY(job_id,row_index))`; `import_provenance(item_id,job_id,row_index,source_id,source,locator,imported_summary,source_text,UNIQUE(job_id,row_index))`. Bind all values; no paths/credentials in payload/exportable settings.

- [ ] Write RED tests for limits, Unicode/commas/normalization aliases, duplicate URLs preserving meaningful parameters, owned/missing attachment IDs, unsupported fields, immutable digest/options and zero item/collection/tag writes on preview. Invalid rows return structured per-index outcomes; invalid top-level input rejects without staging.

```python
preview = service.import_preview(records=[{'url':'https://example.org/a','notes':'Keep'}])
self.assertEqual(service.search()['total'], 0)
job = service.import_start(preview['preview_id'], preview['input_digest'], request_id)
again = service.import_start(preview['preview_id'], preview['input_digest'], request_id)
self.assertEqual(job['id'], again['id'])
with self.assertRaises(ConflictError):
    service.import_start(preview['preview_id'], '0'*64, request_id)
```

- [ ] Run `rtk proxy python -m unittest discover -s tests -p test_import_preview.py -v`; expect missing preview operation. Implement canonical UTF-8 JSON SHA-256 over validated records/options, immutable SQLite staging and atomic start admission. Enforce byte bounds before parsing in adapters later, and again at service boundary.
- [ ] Test expiry with explicit controlled clock, simultaneous start calls and changed-request-ID payload conflicts using real SQLite. No mutation may precede validation.
- [ ] Run complete suites and commit `feat: stage bounded immutable import previews`.

## Task 3: Fenced durable per-record import execution

**Files:** create `bookmarks/imports/runner.py`, `apply.py`, `import_worker_host.py`, `tests/test_import_runner.py`; modify `runtime.py`, `__init__.py`, `service.py`.

**Consumes:** immutable accepted jobs/validated staged records, current item/collection/tag validators. **Produces:** restartable supervised importer; original item and result/provenance commit atomically with cursor/count advancement.

Refactor only as needed to expose transaction-scoped item capture/collection resolution shared with existing writers; do not call a separate committing `service.capture` then advance cursor in a later transaction. Claim tokens/lease clocks are sampled after write-lock acquisition; each apply validates current claim, cancellation and cursor. Maximum 120-second claim lease; recover expired claims before choosing pending work. No network or inference under a SQLite lock.

- [ ] Write RED executor tests for create/skip/invalid counts, two simultaneous workers, crash after accepted claim, crash immediately after committed row, repeated completion and stale lease. Preserve user edits made after preview and never resurrect trashed duplicates.

```python
# Given a three-row preview with one good URL, one duplicate and one invalid URL:
run_import_to_terminal(service, job_id)  # Test helper drives real production steps.
report = service.import_job_get(job_id)
self.assertEqual((report['imported'], report['skipped'], report['failed']), (1,1,1))
self.assertEqual((report['processed'], report['remaining']), (3,0))
self.assertEqual(len({r['index'] for r in report['rows']}), 3)
```

- [ ] Implement bounded apply steps and sanitized terminal failures. Check current schema/route snapshots, create normalized nested collection paths within the same row transaction, save only new items, link imported provenance and commit result/counts together. Invalid rows consume one failed result, not an infinite retry.
- [ ] With `enrich=False`, call shared capture with no enrichment settings and prove zero queued inference jobs. With explicit `enrich=True`, snapshot the current library route at admission and atomically queue only imported links, never skipped rows; missing compatible route is an actionable start error rather than silent automatic enabling.
- [ ] Test cancellation while the first row is held both before and after commit: already committed effects remain, remaining rows stop. Resume after process death uses persisted cursor/results; cancelled jobs are not resumed by later activation.
- [ ] Start through public `ctx.spawn_task` on the original registered async context, independently of enrichment being configured. Reuse typed transient-storage bounded recovery, exact-task observation and unload draining; do not invent a new scheduler. Verify progression after initiating API request returns using synthetic data.
- [ ] Run suites, perform the one targeted data-integrity/concurrency review for this new slice, fix Important findings RED→GREEN and commit `feat: execute durable fenced bookmark imports`.

## Task 4: Bookmark HTML parsing and native/HTTP parity

**Files:** create `bookmarks/imports/html.py`, `tests/test_import_html.py`, synthetic HTML fixtures; modify `native_tools.py`, `plugin.yaml`, `dashboard/plugin_api.py`, `tests/test_tools.py` and router tests.

**Consumes:** Task 2/3 service contracts. **Produces:** identical normalized records from supplied Netscape bookmark HTML, bounded API/tool contracts.

Parser: `HTMLParser(convert_charrefs=True)`, maximum 2 MiB UTF-8 input, 500 bookmark records, 16 folder levels, bounded accumulated text. Interpret `H3` folders followed by `DL`, `A HREF` links and associated `DD` description as source metadata; preserve `TAGS` as comma-separated source-format tags with explicit format warning. Do not execute scripts/styles, fetch icons, trust arbitrary attributes or extract incidental anchors outside bookmark entries. Report unsupported dates/attributes and malformed folder structure. No claim of complete Raindrop parity without representative fixture evidence.

- [ ] Write RED fixtures for nested DL/H3, Unicode entities, missing closing tags, empty folders, malicious schemes/attributes, deep nesting and oversized input. Assert exact collection paths and reconciled record counts.
- [ ] Implement one parser yielding the same normalized record validator and row warning contract. Top-level structural/size violations reject safely without writes; per-entry malformed URLs stay preview errors.
- [ ] Register `bookmark_import_preview`, `bookmark_import_start`, `bookmark_import_request_get`, `bookmark_job_get`, `bookmark_job_cancel` with strict no-extra-property schemas and explicit supplied-input semantics. Job operations dispatch by actual persisted job kind; never let an import operation accidentally cancel enrichment/chat work.
- [ ] Add authenticated routes: `POST /imports/preview`, `POST /imports/start`, `GET /imports/{job_id}`, `POST /imports/{job_id}/cancel`, and read-only `GET /imports/requests/{request_id}`. Register the request-status route before any ambiguous dynamic route. Preview streaming body cap 2 MiB plus 128 KiB JSON framing, decoded HTML/record cap 2 MiB. Other writes retain existing 128 KiB limit. Reject duplicate JSON keys/nonfinite constants/query ambiguity.
- [ ] Run native-versus-HTTP tests with identical payloads, invalid JSON/limits, changed digest, missing job and cancellation. Verify declared native tools with official isolated validator. Commit `feat: expose validated HTML and record imports`.

## Task 5: Import preview/progress UI and portable evidence

**Files:** create `ui/library-import.js`, `tests/test_import_ui.cjs`; modify `ui/library.js`, `library-navigation.js`, shared CSS and `scripts/build-ui.cjs`; update README/STATUS/ROADMAP and `docs/verification/trash-and-imports.md`.

**Consumes:** Task 4 endpoints and existing scope/library ownership/error/dialog primitives. **Produces:** accessible Import dialog with explicit source/options, preview and Start confirmation, job progress/readback/cancel/resume inspection on both clients.

- [ ] Write real-React emitted-client RED tests for upload/normalized paste, explicit Preview before Start, enrichment off by default, visible imported/skipped/invalid counts, unknown-field warnings and unchanged input after validation errors.
- [ ] Add an Import action separate from Add. File contents are supplied as text; no client-local path is sent. Store only selected draft input/job identity in current backend/library scope; do not persist source bytes in unrelated browser storage. `Start import` sends immutable preview ID/digest and a stable request ID, not replacement records.
- [ ] Freeze uncertain Start identity; reconcile by request ID through a read-only admission-status route before another attempt. Use Task 4's `GET /imports/requests/{request_id}` or `bookmark_import_request_get`. This lookup must not start or enqueue a job. Show terminal job errors as errors, not success notices. Cancel is explicit and partial effects/counts remain visible.
- [ ] Test profile/library switch and close/reopen during each await, cancel during running state, stale polling responses and dirty source draft dismissal. Preserve unrelated note/chat drafts and the current library filters. Refresh after committed imports without automatically opening chat or invoking a model.
- [ ] Run full Python suites on 3.11/3.14, Node suite, deterministic build, Desktop syntax and whitespace. Exercise actual Dashboard authentication, preview/start/progress/cancel/restart with synthetic HTML and native-registry parity. Check light/dark and wide/narrow public SDK controls, focus and overflow. Label unavailable Desktop/provider/OAuth topology checks, never infer them from fixtures.
- [ ] Dispatch one final review of this milestone's stable range; consume one Important-fix pass using TDD, record minors and rulings. Update current status without rewriting historical original verdicts.
- [ ] Commit, push existing feature branch and verify local/upstream/remote/PR head plus both exact-head event runs and expected jobs using `gh api` (installed `gh run list` does not support `--branch`). Keep PR #1 draft/unmerged. No release/install is authorized.

## Completion and subsequent work

This milestone is complete only when trash/restore and both import entrypoints preserve validated content, accurate reports, cancellation and retry effects across a real restart. Publication alone does not satisfy target acceptance.

Next separate plans, in order: portable HTML/lossless asset bundle export/restore; settings and real text/vision processing controls; rich-text/inline-image/autosave editor; final UI/bulk/accessibility and actual-target release verification. Imports do not remove required export. No unsupported field or absent milestone is to be described as implemented.

## Plan self-review

Existing schema, item capture/receipt, collection transactions, native validation, streamed HTTP limits and current UI ownership were read before defining these contracts. Task dependencies are explicit; mutations require transaction-sharing rather than nested standalone writers. Review-focus cases map to Tasks 1–4. New worker activation reuses public host facilities without requiring a configured inference route. The owner-approved workspace plan is not reopened; this new data-ingestion plan still requires review before execution.
