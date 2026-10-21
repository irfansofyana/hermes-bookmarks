# Hermes Bookmarks — Design specification

Date: 2026-10-20
Status: Product direction and M1 execution approved using subagents on 2026-10-20; Task 1 foundation preview implemented with concerns. Requirements below remain release targets, not completed functionality. See `docs/STATUS.md`.
Repository: irfansofyana/hermes-bookmarks (public).

Layout refinement (2026-10-21): the owner approved the library-first in-chat design with a collapsible panel, collections/tags and Add/Edit popup. The detailed [workspace design](2026-10-21-library-first-workspace-design.md) awaits written-spec review before implementation planning. It refines the experience below; it does not establish implementation or waive rich-text, vision, import/export or target-acceptance requirements.

## 1. Intent and agreed constraints

Build a standalone, Hermes-native bookmark manager inspired by Raindrop's capture, visual-library, and organization experience. It owns its library rather than requiring a Raindrop, Linkwarden, or other bookmark-service account. Raindrop is an interaction reference, not an assertion of exact feature parity.

Desktop, Dashboard, and native Hermes chat tools are equal entrypoints. AI tagging, summarization, configuration, theme inheritance, personal notes, and images are day-one requirements. No mockup is requested.

One shared library per Hermes backend installation is the v1 default and only library mode. Switching agent profiles does not change the library or enrichment settings. Clients connected to different backends do not automatically synchronize. Profile-private libraries and multi-user sharing are deferred. Profiles are not an authorization boundary; only principals authorized by the backend's access policy may use this shared library. Verify that boundary before deployment.

The owner requires adherence to official Hermes documentation and has identified irfansofyana/hermes-blogwatcher as a working implementation reference. Reuse public Hermes SDKs, exported components, libraries, and supported extension points. Do not modify Hermes core, fork its chat implementation, import private modules, monkey-patch host behavior, or reach into host DOM/React internals. Availability must be checked against the chosen host version on both surfaces.

Owner clarification on 2026-10-21: an in-plugin chat interface is required while Bookmarks is open. It is not the usual Hermes session-chat screen or a navigation handoff to it. Plugin-owned conversation presentation is allowed. Reuse documented Hermes agent/session/provider facilities underneath and exported UI components where appropriate; do not copy private chat internals, modify core, create a separate agent loop or keep separate provider credentials. This clarification supersedes the earlier prohibition on plugin-owned presentation, not the public-API/backend constraints.

## 2. User experience

Provide a dedicated Bookmarks page in Desktop and Dashboard. Navigation includes all items, Inbox/unorganized items, favorites, read later, nested collections, and tags. The main region supports searchable/filterable grid and list views. Item details expose preview, metadata, saved AI summary, and a separate personal-notes editor. Narrow layouts use a full-page detail view rather than squeezed columns.

Saving a link creates a durable item immediately. Extraction and enrichment status is visible and updates without stealing focus. A failed fetch or model request leaves the saved item usable. Show actionable errors and explicit retry actions. Reading an item or saved summary does not fetch the publisher again, invoke inference, or silently change its read state.

Support keyboard-accessible controls and visible pending, empty, failure, disabled, and save states. Do not hide essential actions behind hover alone.

### 2.1 Visual design and interaction quality

The UI must feel like a polished AI-native bookmark application within Hermes. Use the host's public components and theme tokens for controls, typography, colors, focus treatment, and spacing where available. Apply the owner's design-system guidance only where compatible with the active host theme; host appearance takes precedence over fixed branded colors or fonts. No mockup is required before implementation, but rendered visual verification is required before release.

- Establish a clear hierarchy: page title and search, collection/filter context, item titles, then quieter source/date metadata. Keep secondary actions out of the reading path without making them inaccessible.
- Make grid cards image-led with consistent cover geometry and a deliberate missing-image fallback. List view favors scanning titles and metadata. Avoid oversized empty cards, dense badge stacks, decorative gradients, and competing primary buttons.
- Keep notes and summaries comfortable to read with restrained line length, clear headings, and adequate whitespace. Label generated, imported, and user-authored content distinctly without turning the detail view into a status dashboard.
- Use one clear Add action with URL paste and image upload. Preserve manual organization as optional during capture. Contextual bulk actions appear after explicit selection and show the affected count.
- Provide a visible Ask Hermes action for an item, selection, or collection. Make the context being handed to chat understandable before sending. AI status should be useful and unobtrusive; never invent progress percentages or present queued work as completed.
- Preserve search, filters, selection, and scroll position when moving between library, detail, and native chat. Keep in-progress note edits safe. Native-chat navigation must not reset the library or discard a draft.
- Use responsive layouts with no page-level horizontal overflow. On narrow screens, use a full-height detail flow and reachable actions rather than squeezing the desktop columns. Do not depend on hover or drag-and-drop as the only interaction.
- Provide visible keyboard focus, accessible names, keyboard alternatives to drag actions, adequate contrast, and reduced-motion behavior. Loading placeholders reserve layout space; errors preserve user input and offer a clear retry.
- Pending actions disable only conflicting controls. Prevent duplicate submissions; show saved confirmation only after persistence succeeds. Provide recoverable trash and a straightforward restore path.

### 2.2 Bookmarks-owned conversation experience

The user wants a chat UI inside Bookmarks, available while the plugin remains open. The owner supplied Hermes Learning as the implementation reference. Its inspected source has its own TutorPanel and controller over real Hermes sessions, using Desktop host request/events and Dashboard SDK-authenticated WebSocket transport. See `docs/verification/in-plugin-chat-reference.md` for pinned source and focused tests; this is reference evidence, not implemented Bookmarks chat. The visible conversation belongs to the plugin experience rather than the usual Hermes session-chat screen. Reusing Hermes underneath does not require reusing or navigating to that screen.

Keep library/item context and conversational interaction within the open plugin on Desktop and Dashboard. The owner-approved layout direction is library-first with a collapsible right-side chat panel, initially closed; narrow layouts switch between Library and Chat within the plugin. See the workspace refinement for lifecycle, organization and form behavior. Publicly exported components may be reused, but the UI must not be contingent on exporting the entire usual Hermes chat screen. A handoff to that screen is not a substitute for this requirement. Dedicated Hermes-backed sessions and profile-scoped binding metadata are now implemented in the foundation; runtime evidence and remaining per-client gates are recorded separately in `docs/verification/in-plugin-chat.md`.

Expected conversation behavior includes Markdown, tables/code, streaming replies, actual tool activity/results, user-visible plans/progress, approvals/clarification, stop and history/resume. Render real backend events using public contracts; do not fabricate progress or implement a replacement agent/approval engine. Provider credentials and execution remain Hermes-owned. Verify supported capabilities and public reusable controls for each target. Planning means user-visible plans emitted by Hermes, not hidden reasoning.

An Ask Hermes action selects bounded bookmark, selection or collection references as context for the plugin chat and exposes a user-editable request there. It must not navigate away to the usual session-chat screen. Let native tools retrieve authorized details on demand. Do not inject the entire library, private notes, or embedded note images automatically. Showing or preparing a draft does not itself submit a message or incur inference cost. Any Send action must be explicit and target the intended session; do not overwrite an existing draft or fall through to an unrelated chat.

Keep backend conversation ownership explicit: profile, session/thread, tool permissions, approvals, history and cancellation target must be defined by the public integration contract. Do not silently attach the plugin to whichever ordinary chat happens to be focused. Whether a dedicated Hermes-managed session underlies the UI is an implementation decision still to verify. Shared library access does not merge unrelated histories. Conversation inference and background library enrichment remain separately scoped; reuse Hermes configuration and credentials rather than building a second credential system.

Library changes made by native tools must refresh the relevant view through supported events or bounded query invalidation, without losing unsaved notes or current selection. Bookmark summaries and chat responses remain separate records; do not copy a conversation response into personal notes without an explicit save action.

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

### Proposed tool inventory

These are intended native registrations, not tools already implemented. Final argument schemas require review in the implementation plan.

| Tool | Responsibility |
| --- | --- |
| `bookmark_save` | Save a link or image item, with optional metadata, notes, attachment references, and enrichment preference. |
| `bookmark_search` | Search/filter with bounded pagination. |
| `bookmark_get` | Read details, notes, saved summary, attachment references, and processing status. |
| `bookmark_update` | Revision-aware updates to metadata, tags, collection, favorite/read-later state. |
| `bookmark_note_update` | Append or explicitly replace personal notes without altering generated summaries. |
| `bookmark_delete` | Move an item to recoverable trash. |
| `bookmark_restore` | Restore a trashed item. |
| `bookmark_attachment_add` | Store an authorized image and return a durable attachment ID. |
| `bookmark_attachment_get` | Return metadata and a supported authorized access reference. |
| `bookmark_attachment_remove` | Remove an association safely, checking remaining references. |
| `bookmark_collection_list` | Read the collection hierarchy. |
| `bookmark_collection_create` | Create a root or nested collection. |
| `bookmark_collection_update` | Rename or move a collection, rejecting cycles. |
| `bookmark_collection_delete` | Delete a collection with an explicit contents policy. |
| `bookmark_tag_list` | Discover existing tags and reduce near-duplicates. |
| `bookmark_import_preview` | Validate normalized records or a supported file and preview changes without library writes. |
| `bookmark_import_start` | Start a persistent import from a validated preview and explicit options. |
| `bookmark_job_get` | Read import, export, or enrichment progress and reconciled results. |
| `bookmark_job_cancel` | Cancel remaining work and report already-completed effects. |
| `bookmark_export_start` | Create a downloadable selected/full-library export. |
| `bookmark_enrich` | Request tags and/or summaries for selected items and return a job ID. |
| `bookmark_settings_get` | Read library configuration without secrets. |
| `bookmark_settings_update` | Apply validated library-setting changes through supported mechanisms. |

Return stable IDs, structured errors, processing status, and pagination metadata. A save response must not claim enrichment has finished while a job remains pending. Reading saved data has no inference side effect.

Writes require explicit scope and validation. Bulk destructive actions and permanent deletion require a genuine user-approval mechanism, not a model-provided boolean treated as proof. Validate any filesystem/attachment reference passed to a tool; arbitrary paths are not an implicit file-access grant. Verify the host-supported upload mechanism for chat attachments.

## 8. Import and export

Both are product requirements. Prioritize import implementation for the first release; export remains required and may not be silently omitted from the release scope without owner approval.

Initial import target: browser/Raindrop-compatible bookmark HTML. Verify actual source-format behavior with representative fixtures before claiming compatibility. Preview counts and nested collection mappings, detect duplicates, preserve supported metadata, offer explicit enrichment opt-in, and provide progress/cancellation and imported/skipped/failed results. Cancellation retains already committed items and reports partial completion. Retry behavior must not create duplicate items. Unsupported fields should be disclosed, not silently represented as preserved.

### Chat-driven migration from existing files

Accept normalized records as a first-release import input alongside bookmark HTML. Hermes can read explicitly selected source files with its existing authorized file tools, interpret their structure, and submit records to the plugin. No dedicated Obsidian, X, or GitHub importer, live-account connector, or two-way vault sync is required in v1. Reading a source file is not permission to scan the entire vault or upload all its contents.

Records may carry original URL, title, collection path, tags, personal notes, imported source text/summary with provenance, attachment references, and a stable source identifier. Preserve imported content without labeling it as newly generated or independently verified. A local path must be transferred through a supported attachment mechanism when the backend is remote.

Use bounded batches or an authorized staged file for large migrations. Preview field mappings, duplicates, unsupported content, and errors without changing the library. Bind execution to the validated input and options; reject a changed payload rather than executing a stale preview. Support explicit duplicate/conflict policy, idempotent retries, durable job IDs, cancellation, and a report reconciling imported/skipped/failed entries. Never overwrite notes edited after import without an explicit conflict decision.

Source files remain unchanged. Import defaults to no publisher fetch and no AI enrichment; either needs explicit opt-in. The preview validates submitted records, not the completeness of the agent's extraction. Preserve source references and extraction warnings so missing or ambiguous entries can be reviewed. Do not create bookmarks from every incidental link without user-approved extraction criteria.

Export targets: portable bookmark HTML for links and a versioned full-fidelity bundle covering items, collections, tags, notes, summaries, settings without secrets, and attachments. Define round-trip behavior and validate it with fixtures. Protect against traversal and unsafe payloads when importing archive-based backups. Browser HTML cannot be presented as a lossless backup of rich notes and uploaded images.

## 9. Architecture proposal

Use one shared backend service layer, SQLite persistence, backend-owned attachment storage, and persistent enrichment jobs. Thin native-tool and authenticated HTTP adapters call the same service. The plugin owns its conversation presentation and contextual library actions; Hermes supplies the public backend execution/session/provider/approval facilities. Verify that integration rather than implementing another agent loop or replacing provider authentication. Background enrichment and conversational agent turns are separate integration paths. Share UI components and scoped styles where feasible, but emit distinct Desktop and Dashboard entrypoints using their documented SDKs.

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
- Chat is usable while Bookmarks stays open on both clients. Ask Hermes selects context in that plugin-owned UI, preserves drafts/library state and targets its explicitly owned backend conversation. It must not mutate an unrelated ordinary Hermes chat or substitute navigation to it.
- Plugin conversation Markdown, real streaming/tool/plan events, approval/stop and history behavior are exercised against the supported backend contract per host version. Plugin-owned presentation is permitted; copied private UI, fabricated events and a replacement agent loop are not.
- Chat profile/model selection remains independent of shared-library enrichment settings. Context transfer is bounded and explicit.
- A chat-driven normalized-record import preserves notes, tags, provenance, and attachments, survives retry/cancellation, and leaves source files unchanged.
- Real rendered UI is reviewed in both themes and at wide/narrow widths, including long titles, missing covers, rich notes, multi-selection, empty/error states, keyboard navigation, and theme changes. Capture screenshots and check layout and console errors.
- Source and dependency review confirms no Hermes core changes, private-module imports, DOM interception, copied internal chat components, or duplicate agent/provider implementation. Plugin-owned conversation presentation is intentional.

Use unit, integration, emitted-bundle, browser, and real-host verification. Run the official plugin validator against the targeted host version. Report mocked inference, synthetic preview data, skipped tests, and real model tests separately. Paid inference tests require authorization. Deployment/restarts require separate approved scope; do not alter live plugins while developing.

## 12. Deferred scope and remaining engineering gates

Deferred: profile-private libraries, semantic search, multi-user sharing, independent-backend sync, browser extension, highlights, full-page archival, PDF/video support, and separate appearance overrides.

Resolve these engineering gates inside the first development milestone before dependent feature work, not through a separate prerequisite research project. Record a host-version compatibility matrix for the plugin-owned UI's public backend execution/streaming/session contract, exported presentation components and provider configuration separately on Desktop and Dashboard. Missing automatic handoff to the usual chat screen is not itself a blocker for this design; missing supported backend execution is. Do not replace that backend with a custom agent loop or a core patch. Also inspect official contracts for shared storage, job/service lifecycle, Desktop and Dashboard adapters, inference model overrides and vision input, chat attachments, authentication, and approvals. Resolve numeric resource limits, exact schemas, and importer compatibility with evidence. These are explicit engineering gates, not claims of supported behavior.

This specification does not establish runtime compatibility, installation, catalog listing, or release. M1 execution is now approved; Task 1's isolated package validation and unresolved host limits are recorded in `docs/verification/compatibility.md`. Continue through the detailed plan and `docs/STATUS.md`; do not reopen execution-method selection.

## References

Official contract to verify: https://hermes-agent.nousresearch.com/docs/

Owner-requested implementation reference: https://github.com/irfansofyana/hermes-blogwatcher

References identify the intended authorities; they do not substitute for API verification at the chosen version.
