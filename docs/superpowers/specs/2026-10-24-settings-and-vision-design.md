# Library settings and text/vision enrichment

Date: 2026-10-24 WIB
Status: APPROVED DESIGN — owner approval received on 2026-10-24 (“Seruju”). This is not implementation evidence. The executable plan is `../plans/2026-10-24-settings-and-vision.md` and awaits its separate plan review; preserve the already selected hybrid workflow.
Baseline: `85161559263424c4bb4e0ecc66309a78043733ca`

## Intent and inherited authorization

Continue the existing Bookmarks v1 scope, not another portability or whole-project review. The owner asked to continue implementation after identifying settings/text+vision as the next priority. The original approved product design, sections 5–7, already requires library-owned AI controls, standalone-image analysis, durable jobs, explicit retries, manual-content preservation and native-tool parity. This document resolves the new interfaces and operational choices for that slice; broad permission to continue is not a claim that this previously unwritten detailed design was reviewed.

Use the existing worktree, shared service, public Hermes inference facade and hybrid controller-TDD workflow. Ordinary implementation stays direct; use one targeted independent review for the new settings/admission/late-result boundaries, then one verified author fix pass for concrete findings. Do not repeat consumed portability reviews. Development-branch PR publication and synthetic real-provider verification are authorized. Active installation, production restarts, merge and release are not.

Success: a user can configure AI without editing files, save a link or standalone image without losing it when inference fails, inspect processing, deliberately retry or regenerate, and see persisted factual summary/tag results. Chat model/profile selection must remain independent of library enrichment.

## Current source findings

- `bookmarks/jobs.py:validate_settings` accepts only provider/model/owner_profile. `configure_route` deliberately refuses a different persisted route. Jobs contain immutable route snapshots, token/lease ownership and generation fencing.
- `worker_host.py:start_enrichment` reads bootstrap route settings from `ctx.get_config`, checks owner profile, and calls public `ctx.spawn_task`. A later DB route edit cannot safely be layered over this unchanged bootstrap/conflict behavior.
- `runtime.py:get_service` reads the persisted route on entry. Native/HTTP adapters already share the service and cancellation-draining storage lane.
- `bookmarks/enrichment.py:run_worker` fetches every job as a URL; `JobQueue.enqueue` rejects image items. `AssetStore.read_asset` provides owned normalized image bytes without arbitrary paths.
- `jobs` still has `UNIQUE(item_id,revision)`. An explicit retry must not attempt a second row at the same item revision or silently resurrect a cancelled/superseded job.
- `JobQueue.complete` preserves personal notes and uses generated-tag provenance, but summary editing/protection and per-feature result application need explicit contracts.
- Portable content version 1 has exact fields and permits only inert `enrichment_route` settings. Adding controls without extending the versioned format would silently lose them or break strict validation.

These are source findings, not successful provider/vision acceptance.

## Approach

**Recommended:** extend the existing library-config store and queue, retaining one fixed execution owner and one explicit provider/model route. The selected model must support image input when image analysis is enabled. Different chat and library models remain valid. Text-only models remain usable with image analysis disabled.

Rejected alternatives:

1. Inherit the active chat/profile model: simpler UI, but profile switches would change shared-library execution and violate the approved model-ownership requirement.
2. Add a plugin inference client, credential store or second worker: unnecessary and outside the public-API-only boundary.
3. Introduce independent text and vision routes now: possible later, but doubles routing/trust/error choices without a current product requirement. A single explicit route plus an independent image toggle is the smaller v1 design.

No owner-profile takeover through ordinary settings. The existing deployment/bootstrap owner remains authoritative. Changing the execution owner/root is a separately approved operational action, not an editable form field.

## Settings and UX

Add one **AI settings** toolbar action, separate from Data and Chat. Use the existing owned dialog, theme tokens, wide dialog/narrow sheet, focus containment, dirty-close confirmation and stable connection/library scope.

Sections:

- **Execution:** read-only owner profile and worker readiness; editable provider and model identifiers. No token, API key, endpoint, home path or hidden provider configuration fields. Model identifiers are bounded explicit strings; a model selector is only offered where the public host catalog can be proven to refer to the library execution owner. Otherwise use honest explicit inputs, not the active chat catalog.
- **Automatic processing:** separate automatic tags and automatic summaries toggles, both initially on for links, preserving current behavior; standalone-image analysis initially off. Both tags and summaries off means no automatic job. Inline-note images and ordinary attachments are never analyzed automatically.
- **Summary:** language (`auto` or a bounded explicit language label) and length (`short`, `medium`, `long`). These are prompt preferences, not guarantees of exact language detection or word counts. Preferred tags and guidance are bounded strings/lists, never executable instructions or credentials.
- **Privacy and processing:** extracted-text retention initially off; processing pause/resume; clear data-transfer/cost disclosure before enabling image analysis or initiating explicit inference. Retention off means no extracted article body is persisted. Changing retention affects future jobs only and does not imply deletion of previously retained bodies; existing retained content needs a separately explicit removal action.

GET reads must not enqueue, resume or call providers. Settings Save changes only configuration and may make the existing owner worker eligible to start on an admitted public async entry; it never reprocesses existing items. The UI states: **Changes apply to future jobs. Existing accepted jobs retain their settings.** Pause stops new claims; already admitted extraction/inference may finish. Do not falsely label pause as immediate remote cancellation.

Owner-offline, route-unconfigured, trust denial, extraction failure, invalid structured output and provider failure are distinct actionable states where the public contract supplies that distinction. Do not infer unsupported vision from arbitrary exception text or leak provider exceptions. If capability cannot be proven, say model compatibility needs verification; never silently downgrade image input to text.

## Persistence, concurrency and migration

Store validated settings plus a monotonically increasing settings revision in the shared DB. Library data/settings are not profile-private. Use one transaction for expected-revision validation and configuration replacement. Reject unknown fields, invalid booleans, overlong values, lone surrogates and credentials rather than normalizing them into accepted settings.

Bootstrap behavior:

1. On first initialization, seed route intent from explicit existing host configuration; never from chat defaults.
2. Existing persisted route wins after initialization. A stale bootstrap value does not overwrite a later UI setting or prevent the same owner from restarting its worker.
3. Preserve the configured execution owner, and validate the current public context before worker activation. A request handled by another profile may edit shared nonsecret settings, but does not acquire execution ownership or credentials.
4. Incomplete route can be saved as a visible unconfigured state; item saving remains available. Jobs requiring inference fail configuration checks without publisher/model requests.

Add a transactional migration rather than rewriting an old migration. Existing jobs retain their original snapshots; interpret legacy snapshots with documented legacy defaults. Expand job identity to allow multiple generations for the same item revision while retaining old IDs/states/results. Add a durable request receipt for explicit admission. No destructive job replacement.

Every new capture or explicit import opt-in snapshots settings in the admission transaction, not in a stale service-instance cache. A settings save racing capture must resolve to one complete version, never a mixture. Each job stores settings revision, feature flags and route/options; ordinary settings changes do not mutate accepted jobs. Global pause is checked at claim time.

## Jobs, retries and manual ownership

Add service/native/HTTP parity for settings get/update, enrichment request, enrichment status and enrichment cancel. Freeze exact argument and response schemas in the implementation plan before parallel adapter work. Existing `bookmark_job_get`/`bookmark_job_cancel` currently represent import jobs; do not silently change their meaning or collide IDs. Prefer explicit `bookmark_enrichment_get`/`bookmark_enrichment_cancel`, alongside the originally intended `bookmark_enrich`.

Explicit enrichment accepts one item at a time for this slice, expected item revision, request ID and requested generated fields. The UI reviews that tags and/or generated summary will be replaced and personal notes/manual tags will not. Bulk scheduling is not introduced.

Admission atomically records the request tuple, fresh generation/job and active-item pointer. Same request/same tuple returns the original receipt; same request/different tuple conflicts. Unknown acknowledgements use read-only receipt lookup, not replay with a new request ID. A human retry after terminal failure/cancellation is a new deliberate operation and job generation. Pending/running work is not duplicated implicitly.

Cancellation revokes application ownership and stops undispatched work; host/provider requests already admitted may continue and incur charges. Existing token/lease/generation fences reject their late result. Trash/restore does not reactivate cancelled work. Expired claims retain bounded attempts. Provider retries/fallbacks remain Hermes-owned and are reported separately from queue attempts.

Preserve personal notes, description/title, collection, favorite/read-later and manual/suppressed tag choices. Add explicit summary provenance/protection before permitting manual summary edits. A user-edited summary is not overwritten by a delayed generation; a result can apply only the requested still-owned generated fields. If a result is superseded or conflicted, preserve the user's content and expose the conflict rather than reporting false success. Disabled fields cannot be erased by a structurally valid model response.

## Text and image inference

Continue public `ctx.llm.acomplete_structured` with explicit provider/model, bounded timeout/tokens and untrusted source data. No agent tools, new loop or direct provider SDK. Validate parsed output before mutation. Store actual provider/model and coverage metadata, not merely requested identifiers, without credentials or raw exception messages.

Text: retain the existing public-HTTP extraction protections and bounded body. Summary coverage remains extracted text, not full publisher coverage. A failed extraction cannot yield an article summary. Retain extracted text only when the accepted snapshot enables it.

Images: admit only a standalone image item's existing owned primary asset. Read through `AssetStore`, validate the bounded normalized content and use the public multimodal input shape verified against the target host. Do not fetch external image URLs or send inline/attachment assets implicitly. Missing/deleted/replaced primary assets must produce a safe failure or generation conflict, not analyze a different asset under the original receipt. Snapshot the primary asset ID at admission. Model-visible image instructions and any visible image text are untrusted source data, not commands. If image input/structured output is not supported, retain the saved image and report the failure without a fabricated description.

## Portability compatibility

Do not weaken the existing exact version-1 validator. Define a version-2 full-fidelity content/manifest schema carrying the new allowlisted nonsecret settings and summary/retention provenance, while continuing to read version-1 backups. Version-1 clients must reject version-2 data rather than restore a silently truncated library. Keep HTML explicitly lossy.

Restore imported settings as inert intent, never live owner reassignment, provider calls, queue activation or executable receipts. The destination keeps its identity and execution owner. UI adoption of restored settings is a separate explicit settings save. Existing empty-target-only restore, digest/inventory validation, transactional content and owned atomic asset publication stay unchanged. This is a compatibility extension, not a reimplementation or fresh review of the consumed portability subsystem.

## Verification and completion criteria

Use controller TDD with real RED observations, then focused and full gates:

1. Settings validation/defaults/legacy migration, concurrent expected-revision saves, full snapshot admission, restart/profile invariance and bootstrap not overwriting persisted changes.
2. Pause versus admitted work; same-request receipts; explicit new generations; stale completion/cancellation/trash fencing; repeated async cancellation drains.
3. Independent tags/summary toggles; summary manual protection; suppressed/manual tags; retention on/off and no accidental body retention in job errors or receipts.
4. Image-owned-primary-only admission, exact snapshotted asset, invalid/missing image, unsupported inference/denied trust, malformed structured output and no fabricated success. Provider doubles are labeled synthetic.
5. Native/HTTP response parity and manifest inventory; read-only settings/status must not trigger inference. Test both shipped UI bundles without rebuilding substitutes in tests.
6. Existing version-1 backup fixtures still read; version-2 text/image/settings round-trip; inert restored settings; legacy unknown-version rejection. No loss of personal content.
7. Actual isolated authenticated Dashboard/public SDK settings save/reload, text/image queue outcomes, dirty/error/conflict/uncertain state, theme and wide/narrow screenshots. No actual-host claim based solely on jsdom tests.
8. Approved real-provider tests send only a newly authored synthetic text fixture and synthetic image through the public Hermes facade. Use documented host authentication without copying credentials into the repo, artifacts or clients. Record actual route/result/coverage and possible host retries/costs. If public integration/auth fails, report the real blocker; never substitute a mock result. No production plugin enable/restart.
9. Full Python 3.11/3.14 and Node gates, deterministic delivered bundles, official isolated validator, scoped independent boundary review and verified author disposition. Exact-head CI only after actual PR publication. Connected Electron/remote/OAuth acceptance remains independently open unless actually exercised.

Rich-text/inline-note-image editing follows this slice and remains required for full v1; it is not silently satisfied by the current Markdown/attachment UI.

## Source and documentation checks

Repository observations above are from the baseline's actual source, not live deployment. The official plugin, Desktop SDK and Dashboard extension documentation was fetched on 2026-10-24. The two clients have distinct public SDKs with a shared authenticated plugin backend namespace. The guessed standalone `/developer-guide/plugin-llm/` and `/developer-guide/plugin-inference` pages returned 404; they are not evidence of capability absence. Before implementation, resolve the inference reference through the installed public documentation and target-version contract rather than guessing another URL or importing host internals. Successful multimodal execution remains a verification criterion, not a design-time claim.

## Review gate

The owner approved this detailed design on 2026-10-24 with “Seruju”. Do not request this design approval or workflow selection again. The executable plan is `../plans/2026-10-24-settings-and-vision.md`; its separate review gate is pending. After that review, execute continuously using the retained hybrid/controller-TDD workflow. Approval and planning are not implementation or active-deployment evidence.
