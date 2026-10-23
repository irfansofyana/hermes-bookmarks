# Portable export and restore — execution evidence

Date: 2026-10-23 (WIB). This is a development slice, not v1/release or installed-client acceptance. Owner approved the written design and direct implementation with “Gas langsung implementasi”; existing hybrid method retained. Plan: `../superpowers/plans/2026-10-23-export-and-restore.md`.

## Implemented boundaries

- Version-1 ZIP content backup and explicitly lossy bookmark HTML. ZIP includes all supported library content, Trash, exact normalized owned-image bytes, ordered collection/tag/association/source rows and allowlisted inert route intent. Operational queues, chat, receipts, secrets and paths are excluded. Checksums detect corruption, not authenticity; backups are **unencrypted**.
- Strict JSON/domain/graph and ZIP inventory/path/type/length/digest/image validation. No general archive extraction. 512 MiB total/archive, 32 MiB JSON, 32 KiB transport chunks; supported image bounds remain 10 MiB/20 million pixels. No silent truncation.
- Content provenance migrated into content-owned `content_sources` (migration9), separate from executable imports; operations receipts are migration10. Existing supported aliases, suppressed generated tags, item/association ordering, timestamps and revisions have focused regression coverage.
- Backend-owned artifact/upload/preview/restore IDs, stable request identities, exact/idempotent upload offsets, integrity-checked chunks, sealed previews, lazy known-owned 24-hour expiry cleanup. No caller-chosen server paths. Neither portability reads nor writes activate inference/import supervisors.
- Atomic **empty-content-target-only** restore. Preview does not write content. The final write transaction rechecks emptiness, restores content and commits its successful receipt together. Target installation identity is retained. Pending/running processing becomes inert `needs_review` history; route hints do not bind a live route.
- File content and owned directory entries are synchronized before readiness/content receipts. Failed content commit rolls back all content references; known-owned orphan files are recoverable by the same request. An existing unrelated/unclaimed asset leaf is never overwritten. Expired known-owned unregistered files are cleaned without scanning or deleting unrelated files.
- Eight matching native tools and authenticated HTTP routes. Admitted executor writes drain through repeated coroutine cancellation. Data dialog is scope/library-owned: separate Generate/Download, explicit file upload/preview/confirm, Stop transfer wording, retained request IDs and read-only uncertain-result lookup, bounded integrity-checked Blob download with URL revocation. Reload inspection does not replay writes.

## Local automated gates

Latest controller gates after visible integrity metadata and directory-durability fixes:

- CPython3.14: **236 tests passed**.
- CPython3.11: **236 tests passed** with inherited `PYTHONPATH/PYTHONHOME` removed.
- Node: **213 tests passed**, exercising both emitted clients; Data cases include delayed profile/connection/file/download/admission completions, A→B→A restore completion, lost upload/export/restore acknowledgement, explicit resume, multichunk/hash/offset/size faults, pending-export fences, draft discard and Blob cleanup.
- Focused portability controller tests: **16 passed**, including synthetic subprocess exit after asset publication, rollback/receipt recovery, directory-sync failure before readiness/commit, post-preview competing writer, replay/conflict/expiry and cancellation drain.
- Both bundles rebuilt. The final deterministic-build/syntax/whitespace and exact-head CI gates will be recorded after review disposition; these counts are local execution, not remote CI.

The independent backend and final adapter/UI reviews were dispatched at immutable `c0ff5f264d5675ebcc7cf5f1e8b371d69f5d6f37` and `4f7b6fb1b04018e4844fb54e37f220058356031f`, respectively. The final adapter/UI result is now consumed: REQUEST CHANGES with two Important findings, fixed in author pass0cfd958. [Original report](portability-final-review.md), [disposition](portability-review-fixes.md). Both Hermes backend attempts failed on provider credits before a verdict. Independent local Codex completed at immutablee20e0f6 with REQUEST CHANGES, one Important/no Critical. [Original backend report](portability-backend-review.md) and [author fix/verification](portability-backend-review-fixes.md) preserve the finding and its fixb3fef77; both review scopes are now consumed. No independent re-approval is claimed.

## Actual authenticated Dashboard/backend round trip

Three disposable HOME/HERMES_HOME roots and explicitly configured libraries under a generated TMPDIR fixture were used; no active installation, personal data, provider credentials or service restarts. Source fixture: four total items (three active/one Trash), three collections including a nested and an empty folder, four tag definitions with manual/generated/suppressed provenance, one owned image shared by a link and image item, retained notes, saved summary, flags and imported-source text. No model calls.

`portability-host.json` records real loopback HTTP authorization rejection, explicit export creation/repeated stable request/read-only lookup, bounded download and full SHA-256, upload resume/exact offsets, preview with no target-content mutation, atomic restore/idempotent repeated request/read-only lookup, target identity preservation, item projections, preview bytes, rejection of another preview into the now-nonempty target, and explicit HTML losses. No responses were fabricated.

After stopping both owned source/target servers and confirming their old ports closed, they were restarted against the same libraries. `portability-restart.json` records exact whole item projections (all active and Trash), byte-for-byte owned binary image and MIME equality through authenticated asset endpoints, full persisted artifact checksum, successful durable restore receipt and preserved target identity. **Four items and one distinct owned asset compared**, not just counts.

`portability-native-source.json` and `portability-native-target.json` record real `PluginManager`/`model_tools` dispatch of all eight new native tools across source and a separate empty target, including byte transfer, preview, restore and receipt replay. Core imports appear only in the test harness `tests/host/portability_native.py`, never runtime plugin code. These are registry checks without invoking an LLM.

### Actual UI and visual evidence

The real built Dashboard SPA, real plugin loader, actual public SDK and authenticated plugin backend were used in Chromium. `portability-browser.json` records:

- Explicit Generate then actual Blob Download; saved ZIP byte count and SHA-256 match the backend artifact.
- Source dialog in dark/light at1440/390, measured horizontal/viewport bounds and forward/reverse focus containment.
- Upload into a different empty backend, immutable preview, disabled Restore until explicit checkbox confirmation, then a real successful restore with matching library counts.
- Page reload followed by read-only exact request-ID inspection, with **zero new mutation requests**.
- Source close returned focus to its Data opener; no page errors.

Seven actual screenshots are linked by that manifest in `screenshots/bookmarks-data-*.png`. Direct visual inspection covered wide dark export, narrow light export and wide restore preview. The target retained its independent dark theme while the source was switched to light; initial restore filename/theme labels were corrected from the captured computed color and pixels. No pixels or checks were synthesized. These are Dashboard screenshots with synthetic content, not connected Electron proof.

### Harness startup constraints, not hidden successes

The normal top-level CLI attempted a new-home dependency bootstrap and timed out. Setup instead used the **unmodified official config command handler**, followed by exact configuration readback. Native discovery and the unmodified Dashboard `start_server` loaded the real plugin/SPA. A subsequent core borrowed-runtime re-exec selected the base interpreter instead of the prepared virtualenv and failed importing `ruamel`; diagnostics showed the changed `sys.executable/sys.prefix`. The fixture then used the supported `HERMES_DISABLE_LAZY_INSTALLS=1` guard with already installed dependencies. No core changes, private host-state manipulation or fake HTTP/model responses were used. This does not certify the ordinary new-home CLI bootstrap path.

Official isolated `plugins validate --json` subsequently returned `ok:true`, matching declared/actual capabilities, host-ready, no core override and a public Desktop surface. Known bundled Marked regex `inline_shell_exec` scanner cautions remain disclosed. An earlier `--install-deps` invocation returned the capability pass but printed a PM-runtime dependency-preparation refusal under the lazy-install guard; **that dependency-install step is not claimed successful**. The final validation ran with the already prepared scratch environment instead. No production environment was repaired or installed.

## Remaining gates

All owned disposable servers are now stopped; `portability-process-cleanup.json` verifies every old/restarted port is closed. Final local gates passed236 Python on each3.11/3.14,213 Node, deterministic bundles, syntax and whitespace. Continuation author gates passed237 Python each3.11/3.14 and217 Node; actual failed-restore recovery and post-reload export download passed, plus official isolated validation. Final post-backend-fix gates passed242 Python each3.11/3.14 and217 Node. Six subprocess/security crash regressions pass; final actual HTTP/browser/restart evidence is in portability-final-host.json, portability-browser.json and portability-final-restart.json. Exact-head remote CI remains to be recorded for publication; review verdicts and author dispositions are complete. Connected packaged Electron, independent-machine/OAuth transport and maximum proxy payload acceptance remain unverified. Real synthetic text/vision provider checks, settings controls and rich-text/inline-image notes remain separate required product work. No merge/release or live deployment is authorized.
