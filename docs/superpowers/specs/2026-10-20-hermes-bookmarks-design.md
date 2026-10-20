# Hermes Bookmarks — Design specification

Date: 2026-10-20
Status: Draft for written-spec review; not an implementation approval.
Repository: irfansofyana/hermes-bookmarks (public).

## 1. Intent and agreed constraints

Build a standalone, Hermes-native bookmark manager inspired by Raindrop's capture, visual-library, and organization experience. It owns its library rather than requiring a Raindrop, Linkwarden, or other bookmark-service account. Raindrop is an interaction reference, not an assertion of exact feature parity.

Desktop, Dashboard, and native Hermes chat tools are equal entrypoints. AI tagging, summarization, configuration, theme inheritance, personal notes, and images are day-one requirements. No mockup is requested.

One shared library per Hermes backend installation is the v1 default and only library mode. Switching agent profiles does not change the library or enrichment settings. Clients connected to different backends do not automatically synchronize. Profile-private libraries and multi-user sharing are deferred. Profiles are not an authorization boundary; only principals authorized by the backend's access policy may use this shared library. Verify that boundary before deployment.

The owner requires adherence to official Hermes documentation and has identified irfansofyana/hermes-blogwatcher as a working implementation reference. Avoid Hermes core modifications and private-API assumptions.

## 2. User experience

Provide a dedicated Bookmarks page in Desktop and Dashboard. Navigation includes all items, Inbox/unorganized items, favorites, read later, nested collections, and tags. The main region supports searchable/filterable grid and list views. Item details expose preview, metadata, saved AI summary, and a separate personal-notes editor. Narrow layouts use a full-page detail view rather than squeezed columns.

Saving a link creates a durable item immediately. Extraction and enrichment status is visible and updates without stealing focus. A failed fetch or model request leaves the saved item usable. Show actionable errors and explicit retry actions. Reading an item or saved summary does not fetch the publisher again, invoke inference, or silently change its read state.

Support keyboard-accessible controls and visible pending, empty, failure, disabled, and save states. Do not hide essential actions behind hover alone.

## 3. Theme behavior

Follow the active host theme by default, independently on each client. Desktop may be dark while Dashboard is light without changing shared data or settings. Theme changes must repaint the plugin without a page reload. Use each host's documented theme tokens and components; scope plugin CSS so it cannot alter host styling. Verify both host adapters in light and dark themes. A separate plugin appearance selector is not required in v1.

## 4. Items, collections, and search

Support link items and standalone image items. Shared fields include stable ID, title, description, one collection, multiple tags, notes, saved summary, favorite/read-later state, creation/update timestamps, revision, and processing status. Link items also store the original URL and cover reference. Image items refer to durable uploaded assets.

Collections are nested. Reject cycles. Proposed deletion behavior: nonempty collections require an explicit move-to-parent/Inbox choice; deleting a collection must not implicitly destroy its items. Tags are independently editable.

Detect duplicate link saves without silently overwriting manual edits. Preserve the originally supplied URL. The implementation plan must define conservative URL identity rules and test meaningful query parameters; do not aggressively strip parameters or merge distinct resources. Return the existing item when a save is a duplicate.

Search titles, URLs, descriptions, tags, notes, summaries, and retained extracted text using full-text indexing. Support collection, tag, favorite, and read-later filters. Semantic search is deferred.

Use recoverable trash for ordinary item deletion. Permanent deletion is a separately confirmed action. Trashed content is excluded from normal search. Define attachment ownership so deletion cannot remove an image still referenced elsewhere.

## 5. Notes and images

Personal notes are separate from generated summaries. Provide rich-text editing, Markdown shortcuts, headings, lists, links, code blocks, and inline images. Paste screenshots, drag images into the editor, or insert files without requiring attachment-path syntax. Autosave exposes Saving, Saved, and Failed states and preserves unsaved edits on failure. Use revision-aware updates to avoid silently replacing concurrent edits. Native tools support read, append, and explicit replacement.

Standalone image items can be dropped directly into the library and organized without a URL. Link covers can be replaced or removed. Proposed v1 upload formats are PNG, JPEG, and WebP; validate signatures, decoded dimensions, and file sizes rather than trusting filenames or declared MIME types. Size limits and quotas must be explicit and tested in the implementation plan.

Store assets on the shared backend and reference stable attachment identifiers. Never persist a client-local path or temporary browser URL as the portable asset reference. Serve files through authenticated, authorization-checked routes. Generate thumbnails and sanitize rendered note content. Remote image URLs must not become an unrestricted server-side fetch mechanism. Full-fidelity exports must carry attachments.

Standalone-image tagging and visual summarization are required, subject to a clearly disclosed setting and a compatible model. Images embedded in notes are not automatically sent for AI analysis. Unsupported vision capability must produce an actionable configuration state, not an invented description or a silent downgrade.

## 6. AI enrichment and configuration

Individual saves default to automatic tagging and summarization. Bulk imports default to no enrichment and require explicit opt-in. Explain at first use that extracted text or eligible standalone images are sent to the configured inference provider and may incur charges. Users can disable these features independently.

Save first, persist a job, extract or prepare content, invoke inference, and persist results. Jobs survive restarts, expose stages and failures, and support pause/resume and explicit retries. Processing must continue independently of an open UI while the owning backend service is running. Automatic retries are bounded; distinguish plugin job retries from host-owned provider retries/fallbacks. A paused or unavailable worker must not prevent saving.

Preserve manual tags and user-edited summaries against late results. Track generated versus manual provenance and revision conflicts. Explicit regeneration must state which generated fields it replaces and must not touch personal notes. Failed extraction must not produce a summary claiming to describe the unread article. Record coverage and model metadata for successful summaries.

Library-owned settings include automatic-tagging and summarization toggles, standalone-image analysis, enrichment model, summary language and length, preferred tags/guidance, extracted-text retention, and processing controls. UI and chat use the same validation. Changes affect future jobs; reprocessing existing content is explicit. Record a settings version/snapshot for jobs so profile switching or later edits do not silently change an accepted job's behavior.

Reuse documented Hermes provider/inference configuration where supported and avoid a separate credential store. Do not assume active-profile model inheritance satisfies the shared-library requirement. Verify a stable library-selected execution context and model selection path, including vision inputs and lifecycle ownership, before approving implementation. If the host cannot provide a required capability, report the limitation and obtain a revised design rather than patching core or claiming support.

## 7. Native chat tools

Native registered tools must use the same business logic as UI routes, not browser automation. Provide capabilities to save links, add image items, search/filter, retrieve details and saved summaries, update metadata and notes, manage nested collections, trash/restore, request enrichment, inspect jobs, manage settings, and import/export.

Names such as bookmark_save, bookmark_search, bookmark_get, bookmark_update, bookmark_enrich, bookmark_settings_get, and bookmark_settings_update are provisional. Define schemas in the implementation plan. Return stable IDs, structured errors, processing status, and pagination metadata. A save response must not claim enrichment has finished while a job remains pending. Reading saved data has no inference side effect.

Writes require explicit scope and validation. Bulk destructive actions and permanent deletion require a genuine user-approval mechanism, not a model-provided boolean treated as proof. Validate any filesystem/attachment reference passed to a tool; arbitrary paths are not an implicit file-access grant. Verify the host-supported upload mechanism for chat attachments.

## 8. Import and export

Both are product requirements. Prioritize import implementation for the first release; export remains required and may not be silently omitted from the release scope without owner approval.

Initial import target: browser/Raindrop-compatible bookmark HTML. Verify actual source-format behavior with representative fixtures before claiming compatibility. Preview counts and nested collection mappings, detect duplicates, preserve supported metadata, offer explicit enrichment opt-in, and provide progress/cancellation and imported/skipped/failed results. Cancellation retains already committed items and reports partial completion. Retry behavior must not create duplicate items. Unsupported fields should be disclosed, not silently represented as preserved.

Export targets: portable bookmark HTML for links and a versioned full-fidelity bundle covering items, collections, tags, notes, summaries, settings without secrets, and attachments. Define round-trip behavior and validate it with fixtures. Protect against traversal and unsafe payloads when importing archive-based backups. Browser HTML cannot be presented as a lossless backup of rich notes and uploaded images.

## 9. Architecture proposal

Use one shared backend service layer, SQLite persistence, backend-owned attachment storage, and persistent enrichment jobs. Thin native-tool and authenticated HTTP adapters call the same service. Share UI components and scoped styles where feasible, but emit distinct Desktop and Dashboard entrypoints using their documented SDKs.

Keep storage, item/collection operations, notes/assets, import/export, extraction, inference, jobs, and host adapters separately testable. Database migrations must preserve existing user data. Resolve a shared installation-level data root explicitly; do not silently use an active-profile path and thereby create separate libraries.

Multiple profile processes must not run duplicate enrichment for the same job. Define transactional claiming, leases/recovery, ownership, cancellation, and clean unload/shutdown before implementation. Persisting a queue alone is not proof of correct worker lifecycle.

Blogwatcher is an example for manifests, build outputs, host adapters, and inference integration. Its read-only tools, profile-scoped cached summaries, and lack of persistent workers are not the target behavior here. Do not copy those semantics unmodified.

## 10. Security and data handling

Treat fetched HTML, imported files, and model responses as untrusted. Fetch only allowed public HTTP(S) destinations with protections against private/loopback/link-local targets, unsafe redirects, DNS rebinding, oversized payloads, and unbounded runtime. Sanitize rich-text rendering and reject executable upload formats. Do not execute instructions embedded in saved content.

Keep credentials out of the database, notes exports, client bundles, and logs. Disclose provider data transfer, local retention, and real deletion/eviction behavior. Keep remote Hermes authentication enabled. Protect state-changing routes using the host's documented authentication and request-security mechanisms. Capture tests for authorization and upload boundaries.

## 11. Verification and acceptance

The implementation must demonstrate:

- One item saved through a native tool appears through Desktop and Dashboard connected to the same backend.
- Profile switching does not change library data or chosen enrichment settings.
- Links and image items persist and remain available after restart.
- Notes formatting and inline images survive autosave, reload, and access from the other client.
- Nested collections, duplicate detection, full-text search, pagination, and trash/restore behave consistently across adapters.
- Individual-save enrichment produces persisted tags/summaries; opening saved data does not invoke inference.
- Bulk imports do not invoke inference without opt-in; real import fixture counts reconcile with the report.
- Manual edits survive late AI output and concurrent saves.
- Job recovery does not create duplicate processing or silently lose failures.
- Model/image capability failures and extraction failures produce actionable states without losing items.
- Host theme switching works on both interfaces at wide and narrow widths.
- Export/restore preserves supported metadata, notes, and assets; lossy HTML limitations are explicit.
- URL, upload, note-rendering, and authorization protections are exercised.

Use unit, integration, emitted-bundle, browser, and real-host verification. Run the official plugin validator against the targeted host version. Report mocked inference, synthetic preview data, skipped tests, and real model tests separately. Paid inference tests require authorization. Deployment/restarts require separate approved scope; do not alter live plugins while developing.

## 12. Deferred scope and remaining engineering gates

Deferred: profile-private libraries, semantic search, multi-user sharing, independent-backend sync, browser extension, highlights, full-page archival, PDF/video support, and separate appearance overrides.

Before implementation planning is finalized, inspect official contracts for shared storage, job/service lifecycle, Desktop and Dashboard adapters, inference model overrides and vision input, chat attachments, authentication, and approvals. Resolve numeric resource limits, exact schemas, and importer compatibility with evidence. These are explicit engineering gates, not claims of supported behavior.

No runtime compatibility, installation, catalog listing, or release is established by this document. Next: owner review of this written spec, then an implementation plan and execution-method selection.

## References

Official contract to verify: https://hermes-agent.nousresearch.com/docs/

Owner-requested implementation reference: https://github.com/irfansofyana/hermes-blogwatcher

References identify the intended authorities; they do not substitute for API verification at the chosen version.
