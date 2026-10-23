# Portable export and safe full-library restore

Date: 2026-10-23 (live local date checked). Status: proposed refinement of the approved full-product export requirement, awaiting written-design review. Existing hybrid execution method remains selected. This document does not claim implementation.

Baseline inspected: `345e7d5fd6126f76415a05ec6a54d0fd0c4cc680`, existing `feat/m1-native-foundation` worktree. UX-first implementation and its review fix are complete. Owner asked to continue remaining scope. The restore-conflict question received no answer; the safe proposed default below is explicit, not represented as a user-selected answer.

## Intent and decision

Provide a usable way out of the library: browser-compatible bookmark HTML, plus a versioned content backup that can actually recover personal notes, tags, collections and owned images. Desktop, Dashboard and native Hermes chat use the same service. No publisher fetch, model inference, arbitrary output path, real-vault access, active installation or production restart is authorized.

Recommended approach: a validated domain-data bundle with a manifest and owned asset bytes. A raw database/directory copy would couple portability to runtime queues, host paths and database internals. Reusing normalized import would lose image items, manual/generated/suppressed tag provenance, Trash and identity information. The domain bundle preserves those content semantics while excluding execution state.

Proposed v1 restore policy: **full restore only into an empty content library**. It never clears or overwrites an existing library and never silently merges. Empty means zero existing items, collections, tags, registered assets and content-source records; installation config/identity and portability staging/receipts do not count as content. Empty is checked again under the final serialized write transaction, not just during preview. A user who wants to merge links can continue to use the existing import preview; it is not described as a lossless backup restore.

## User flows

### Export

Add a visible Data / Export and restore entry in the library toolbar, leaving the primary Add action and existing Import intact. The dialog offers:

- Bookmark HTML: active link items by default, optional inclusion of trashed links with an explicit warning about flattening that state. All exported links retain nested collection paths, titles, tags and plain-text descriptions where representable. Empty collections are included. Standalone image items, binary attachments, notes, generated summaries, tag provenance, flags and Trash state are not represented as losslessly preserved; show exact omitted counts/limitations before download.
- Full content backup: all items including Trash and image items, empty/nested collections, notes, descriptions, summaries, flags, source provenance, manual/generated/suppressed tag memberships and all registered owned asset bytes. Display counts, byte size, format version and integrity digest after generation. Fail rather than produce an apparently complete backup when required asset content is unavailable.

No source HTML/script is executed. Exported HTML escapes text and attributes; href values are revalidated against the existing safe URL contract. A legacy invalid URL makes full HTML export fail with a safe item-specific report instead of emitting unsafe content or silently omitting it. Full backups preserve a valid legacy content field as data but never turn it into an executable URL in the UI.

The user explicitly clicks Generate and then Download. The plugin never posts the generated content into the chat automatically. Native tools return bounded artifact metadata and authenticated references, not all notes or an unbounded base64 blob.

### Restore

Choose a backup file explicitly, upload into plugin-owned staging, and Preview. Show source format/version, item/image/Trash/collection/tag/asset counts, integrity status and the empty-target rule. Preview makes no item/collection/tag changes, starts no inference and extracts no arbitrary archive paths.

Restore requires explicit confirmation after preview. Start accepts only immutable preview ID, digest and stable request ID. Retain the request identity after a lost acknowledgement; offer read-only status lookup before any explicit retry. Reopening the dialog can inspect the operation ID. Restore is a single atomic library-content commit, not a partial row import. Cancel is available before admission; an admitted atomic commit cannot be presented as undone by closing a dialog. A failed restore leaves existing content unchanged and reports the failure without claiming success.

Target library identity remains the installation's identity. Original item/collection/tag/asset IDs, item ordering, timestamps, content revisions, asset-association order and exact content are retained in an empty target. Original library identity and export time are descriptive manifest data only; restoring a backup must not impersonate the source backend for chat/session ownership.

## Full-fidelity boundary

The portable content dataset includes:

- Collection IDs, display names, parent links, original ordering, timestamps and revisions.
- Item IDs, kind, original URL or owned primary-image ID, title, description, notes, saved summary, tags display/cache values needed for previously supported normalization aliases, collection membership, flags, timestamps, revision and deletion timestamp.
- Tag IDs, canonical label and normalized identity, membership label and manual/generated/suppressed flags. Suppressed generated tags survive so future processing cannot silently reintroduce them.
- Item-to-asset roles/order, all registered asset metadata and normalized persisted image bytes, with exactly one ZIP member per asset even when shared by multiple items. This includes registered staged/unassociated assets; unregistered filesystem orphans are excluded and never scanned into a backup.
- Ordered imported source records: source ID, source description/locator, imported summary and retained source text. These are source provenance, not newly generated summaries.
- Versioned allowlisted plugin settings without secrets. The current route's provider/model/owner-profile values can be preserved as nonsecret configuration intent, but restore must not bind or activate that route automatically. Restored intent is exposed for explicit later configuration through the settings flow. Credentials, endpoint authorization and host config are never copied.

Excluded and explicitly disclosed: chat sessions/transcripts/bindings, host profile identity, auth/token/key stores, absolute library/output paths, active worker claims/leases, in-progress import/enrichment execution, pending preview/file uploads, capture receipts and operation request history. The bundle is a library-content backup, not an exact running-Hermes checkpoint. Existing generated summaries remain content; pending/running processing is restored as an inert needs-review state, with the original processing state retained as historical metadata. No queued job is replayed.

Current imported source projection depends on `import_jobs` foreign keys. Do not restore those executable jobs to recover source text. Introduce a content-owned source-provenance representation and migrate the existing supported fields transactionally; import receipts stay operational history. Preserve ordering and search semantics for existing imported records. Its migration needs explicit regression and integrity review.

Future rich-editor/settings format changes must extend or version this content schema. This first format cannot claim to preserve features not yet implemented.

## Format and bounds

ZIP bundle with fixed names: `manifest.json`, `library.json`, and `assets/<32-lowercase-hex-id>.blob`. The manifest identifies `hermes-bookmarks-content`, format version 1, creation time, source identity, content counts, payload byte sizes and SHA-256 digests. No pickle, executable SQL, serialized Python objects or caller-selected paths. JSON uses strict key inventories, valid Unicode and finite numeric values. Unsupported versions fail without writes; unknown fields are rejected rather than discarded under a full-fidelity claim.

Proposed explicit first-version limits:

- Total archive and streamed uncompressed content at most 512 MiB; JSON content at most 32 MiB.
- At most 10,000 items, 10,000 collections, 20,000 tag definitions, 200,000 memberships/source entries and 10,000 registered assets; associations remain subject to the existing per-item bounds.
- Each asset retains existing at-most-10-MiB, at-most-20-million-pixel, PNG/JPEG/WebP and no-animation requirements.
- Detect limits before committing; never silently truncate a library. Return clear unsupported-size errors. These are portability bounds, not new limits imposed on the existing library.
- Artifact/staging chunks at most 32 KiB decoded to keep JSON transport bounded. Validate exact offsets, lengths, digests and upload ownership. A whole archive is never embedded in a native tool response or metadata POST.

Reject duplicate ZIP member names, encrypted members, symlinks/nonregular entries, directory traversal/absolute/drive paths, unlisted members, missing members, inconsistent lengths/checksums and decompression beyond streamed limits. Do not call general archive extraction. Read only explicit validated members. Digests detect corruption, not authenticity; an unencrypted backup contains private notes/images and must be handled as sensitive data.

## Persistence and crash handling

Export takes a single consistent SQLite content snapshot, retaining stable row/association ordering. Registered asset bytes are immutable under current APIs; validate metadata, file type, size and digest while copying. Concurrent item edits must produce one consistent metadata version, never mixed per-page reads. Never hold a write transaction through archive generation. Temporary artifacts live under the library's owned portability area, not a user-supplied destination.

Record operation/artifact identity before long processing so acknowledgement loss can be reconciled. Publish only completed, fsynced artifacts by atomic rename plus durable readiness metadata. On failure or process death, incomplete artifacts are unavailable, reported failed/recoverable through status, and removed by owned cleanup; do not claim crash recovery by inventing success. Expiry is checked at every read. Staging/artifact cleanup is lazy on operations/startup with a disclosed 24-hour retention threshold, not a promise of timed deletion without a running host.

Restore validates the full dataset/graph and every owned asset before content mutation. Stage verified assets under a generated operation identity. Use one write transaction to recheck target emptiness, publish metadata/associations/provenance and a successful restore receipt together. Filesystem publication precedes database references; never leave committed metadata referring to a missing file. Crash before commit may leave only unreferenced staged/owned files for cleanup. Rollback must not remove assets another operation owns; no deletion based on archive-supplied paths.

Use the existing public host async lane and task ownership where needed; no private loop, custom agent runtime or global thread scheduler. Cancellation/unload drains any admitted executor transaction before acknowledging termination. Do not activate enrichment/import queues merely to read/download an artifact; existing accepted work elsewhere must remain explicitly distinguished.

## Interfaces and authorization

Separate portability service code from the existing import runner. Proposed native tools: `bookmark_export_create`, `bookmark_export_get`, `bookmark_export_read`, `bookmark_backup_upload_create`, `bookmark_backup_upload_chunk`, `bookmark_backup_preview`, `bookmark_backup_restore`, and `bookmark_backup_restore_get`. Exact schema names/field types will be frozen in the implementation plan. Names and descriptions remain literal English.

Matching authenticated HTTP routes live under the existing plugin namespace. Every artifact/upload/preview/restore ID resolves only inside the configured library and current authenticated backend authority. An opaque ID is not an authorization token. No unauthenticated static mount, secret in query strings, arbitrary server path or unbounded response. Downloads must use the public documented host transport; use bounded JSON chunks if authenticated binary transfer cannot be demonstrated on both clients. Browser download uses a plugin-owned Blob and revokes its URL; filenames are fixed/sanitized and never from archive input.

Update native declarations, actual registrations, common dispatcher, HTTP adapters and capability tests together. Desktop/Dashboard UI ownership includes library identity, scope, operation and upload epoch. Profile/connection switch stops further chunk requests/mutations and cannot download or display a former backend's bytes in the new scope. An admitted write may finish only in its original backend; read-only reconciliation stays possible there.

## Verification and exit criteria

Test first, focused commits and existing hybrid workflow. Required tests:

1. Exact logical round trip through service-produced fixtures: Unicode/normalization aliases, empty and nested collections, manual/generated/suppressed tags, link/image items, shared/staged assets, Trash, long notes, summaries, flags, timestamps, revisions, ordering and imported source text/search. Verify bytes and metadata, not just item counts.
2. Empty library export/restore; existing target refusal both at preview and after a concurrent writer between preview/Start; no partial changes or overwrite. Repeated request IDs are idempotent; mismatched identities conflict. Lost acknowledgement uses read-only status, no new restore by default.
3. Missing/corrupt/symlink assets, truncated/malicious archive/JSON, duplicate members/keys, unknown versions, traversal and zip bombs, quotas, unknown fields, invalid graph cycles/references, unsupported image data, archive secrets/paths not present in allowlisted output.
4. Fault injection at staging/rename/transaction/receipt; process death before/after durable commit and exact-target restart readback. Cleanup affects only owned incomplete files. Concurrent export/manual edits and shared asset references are snapshot-consistent.
5. Both emitted clients: chunk upload/download, explicit preview/confirm, error retention, scope changes during each await, uncertain Start, cancellation wording, operation lookup, light/dark wide/narrow, keyboard and Blob URL cleanup. Actual isolated Dashboard auth and real native registry checks; connected Electron/remote gates remain explicit if blocked.
6. Full Python 3.11/3.14 and Node suites, deterministic bundles, official isolated package validation, targeted archive/transaction integrity review and one final milestone review with one author fix pass. Exact-head draft PR CI readback; no merge/release/active installation.

Following portability, continue the owner's remaining AI settings/text+vision and rich-editor requirements. This design neither drops them nor claims v1 complete.
