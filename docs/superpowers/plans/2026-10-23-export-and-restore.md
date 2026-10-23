# Export and restore implementation plan

> Execute the owner's explicit “Gas langsung implementasi” using the retained hybrid workflow: ordinary TDD, scoped parallel independent modules, targeted integrity review and final milestone review. This request approves implementation of the preceding written design. Do not ask for another approval of unchanged scope.

**Goal:** authenticated portable HTML/content backups and explicit atomic empty-target restore across native tools and both UIs.
**Architecture:** content snapshot/restore transaction module, strict bounded ZIP codec, plugin-owned artifact/upload operations with immutable preview and receipts. Existing SQLite facade and host JSON transport remain authoritative; no scheduler or inference activation.
**Tech stack:** stdlib sqlite3/json/zipfile/hashlib/tempfile, Pillow validation, existing React/public SDK and FastAPI adapters.
**Spec:** `docs/superpowers/specs/2026-10-23-export-and-restore-design.md`, approved for immediate implementation 2026-10-23.

## Global constraints

No active install/restart, merge/release, real data, credentials or model calls. Existing worktree only, all shell commands rtk-prefixed. Explicit library root. Output fixed generated paths, artifact IDs never paths. Bounds: 512 MiB archive/uncompressed, 32 MiB library JSON, 32 KiB decoded transport chunks, asset 10 MiB/20 million pixels. No silent truncation, arbitrary extraction or inference/job replay. Restore only empty content target; check under final write transaction. Target library identity preserved. Unencrypted backups contain sensitive notes/images. Artifacts expire after 24 hours; cleanup lazy, not timed guarantee.

## Shared contracts (freeze before parallel work)

`bookmarks/portability/content.py`:
- `snapshot(connection) -> dict` keys `items,collections,tags,item_tags,item_assets,assets,sources,settings`. Each table list preserves rowid ordering; rows include `rowid`. Items exclude runtime `enrichment_job_id,enrichment_generation`; include optional processing history. Settings allowlisted nonsecret route intent only, never automatic activation.
- `validate_content(data) -> None` rejects unknown keys/types/graph refs/invalid bounds and content with no exact supported meaning. Full Unicode and finite numbers, existing metadata invariants, no arbitrary SQL. May use isolated in-memory SQLite for domain validation, not user data.
- `empty(connection) -> bool`, `restore_content(connection,data) -> None`: caller owns transaction; recheck emptiness, retain item/collection/tag/asset identities/order/revisions. Pending/running status becomes inert `needs_review` with prior state retained. No jobs/receipts/chat bindings copied. Settings go only to inert `restored_enrichment_route`.
- Migration 9: content-owned `content_sources` retains ordered source projection independent of executable import jobs. Backfill and switch importer, item projection and search. New `items.processing_history` TEXT optional.

`bookmarks/portability/archive.py`:
- `write_bundle(target: Path,data: dict,read_asset: callable,source_identity: str) -> dict` writes fixed ZIP members `manifest.json,library.json,assets/<id>.blob`; returns `{counts,limitations}`. `read_asset(id)->bytes`. Stream limits enforced; SHA256 per member.
- `read_bundle(source: Path) -> (data:dict, assets:dict[id,bytes], manifest:dict)` validates exact entry inventories, sizes/checksums, MIME/dimensions/decode/no animation, no symlinks/encryption/duplicates/traversal/unknown versions. Calls `validate_content`. Assets dict bounded by global total. No filesystem extraction.
- `write_html(target:Path,data:dict,include_trash:bool=False)->dict` safely escaped bookmark HTML, nested/empty collections, active links default, explicit omissions counts. Safe URLs only; reject invalid legacy href. Returns `{counts,limitations}`.

`bookmarks/portability/store.py` parent-owned `PortabilityStore(storage)`:
- `export_create(format='bundle',include_trash=False,request_id)` -> metadata `{id,state,format,filename,size,digest,expires_at,counts,limitations}`. Idempotent stable request; status lookup `export_get(request_id)` or artifact id through `export_read(artifact_id,offset=0)`.
- `export_read(artifact_id,offset=0)` -> `{artifact_id,offset,next_offset,eof,content_base64,size,digest,filename,mime_type}`; max32KiB decoded, no raw paths.
- `upload_create(size,digest,request_id)` -> `{id,size,offset,digest,expires_at}`; `upload_chunk(upload_id,offset,content_base64)` monotonic exact/idempotent bytes -> same metadata.
- `backup_preview(upload_id)` -> `{preview_id,input_digest,counts,empty_target,format_version,limitations}` verifies sealed uploaded bytes/domain; immutable staged upload retained. Existing target refused without writes. Stable preview per upload.
- `backup_restore(preview_id,input_digest,request_id)` -> `{id,state,counts}` uses one final DB transaction and durable receipt, asset file publication preceding references. `backup_restore_get(request_id)` read-only reconciliation, not retry. No separate worker needed for bounded synchronous executor operations; no ad-hoc loops.
- Portability schema for operation/upload/preview/restore receipts added migration10 by parent after content migration9 in coordination with content child. File lock/DB serialization for chunk offsets; generated IDs, symlink refusal; expiry on every read, lazy cleanup ownership. No writable caller path.

Public facade methods match names prefixed `export_`, `backup_upload_`, `backup_preview`, `backup_restore`, `backup_restore_get`. Native names `bookmark_export_create/get/read`, `bookmark_backup_upload_create/chunk`, `bookmark_backup_preview/restore/restore_get`. Chunk schemas bounded. HTTP `/exports`, `/exports/requests/{request_id}`, `/exports/{artifact_id}?offset=N`; `/backups/uploads`, `/backups/uploads/{upload_id}/chunks`, `/backups/preview`, `/backups/restore`, `/backups/requests/{request_id}`. All POST metadata bounded128KiB and strict. Portability namespace bypasses automatic worker activation.

## Tasks

### 1. Content ownership, migration and atomic restore (scoped worker)
- [x] Write service-produced full-content roundtrip/migration tests; run RED before code.
- [x] Implement content projection/strict validation, migration9 content schema, source migration and import/read/search integration. Existing target rejected atomically; settings inert/no jobs; exact order/provenance and bytes metadata retained.
- [x] Focused tests: aliases/suppression/Unicode/empty folders/shared image/Trash/pending processing/history, concurrent target writer/revision preservation, foreign keys/rollback. Preserve source writer tests then commit owned files.

### 2. Safe archive and lossy HTML codecs (scoped worker)
- [x] Write failing malicious ZIP/HTML/roundtrip tests against contract.
- [x] Implement bounded strict codec; no extractall. Archive size, ZIP duplicates/paths/flags/members/digest, JSON duplicate keys/NaN, supported version and image validation. HTML nested paths and explicit losses.
- [x] Run focused tests using synthetic tempfile artifacts under TMPDIR; report errors rather than fabricated success. Commit owned files.

### 3. Durable artifact/upload/preview/restore orchestration (controller)
- [x] TDD stable requests, download chunks/digest/expiry, upload resume/idempotency/strict offsets, sealed staging tamper rejection, preview no content writes, final emptiness recheck and exact receipt retry/mismatch.
- [x] Implement store plus facade and operation tables in migration10 after content migration9; file publication before transaction content refs. Reject pre-existing destination/orphan collisions without deleting other's files; recover only exact known owned restore operation.
- [x] Failure injection on file/receipt/content commit; no partial content, no lost ownership; process restart readback. Full Python gate.

### 4. Thin adapters and UI
- [x] RED native/HTTP strict parity and no inference activation. Extend tool inventory, bridge dispatch, manifest, query decoding for offsets. All writes executor-backed and no new credentials.
- [x] TDD Data dialog chunked download/upload with explicit generate/preview/confirm, idempotent admission and read-only lost-ack lookup; bounded buffers/URL revocation and scoped epochs, cancellation never claims undo.
- [x] Build both emitted hosts; real SDK/browser auth/download/import-to-empty-restore synthetic probe plus native registry. Label untested Electron/remote separately.

### 5. Integrity review and release-development gate
- [x] Targeted risky archive/transaction boundary review (after immutable backend commit), consume once, RED→GREEN justified findings.
- [x] Final milestone review of adapters/UI/cross-layer contract, one author fix pass. No old whole-M1 loops.
- [x] Exact logical roundtrip/file bytes, malicious archive corpus/faults/concurrent writes, Python3.11/3.14 and Node, deterministic build/syntax/diff, official isolated validator.
- [ ] Update docs/STATUS/evidence, push existing draft PR and verify exact SHA runs and job conclusions. No merge/release/live deployment.

## Review focus

A concurrent ordinary capture after preview must defeat restore without partial content; a malicious archive must never publish an executable path/file; process termination around asset publication/DB receipt cannot lose committed references or delete another writer's data; lost admission acknowledgement cannot create a second restore; source-provenance migration and export snapshots preserve legacy aliases/order while runtime jobs/credentials remain excluded. Tests belong to tasks1–4 respectively, plus one independent boundary review.
