# Library-first workspace and organization

Date: 2026-10-21
Status: Written specification approved by the owner on 2026-10-21 with “lets implement all”. The detailed implementation plan is prepared for its required review. No implementation of this revision is claimed.
Baseline inspected: `b6b046dc13a22e3c2f071df13c8b014994edf941`, branch `feat/m1-native-foundation`.

## 1. Intent and scope

The owner wants a friendlier bookmark manager with a collapsible in-plugin chat, a collections/tags interface inspired by Raindrop, and a popup containing fields such as notes and attachments. The approved layout makes the library the primary workspace. Chat is an optional right-hand panel, initially closed, that stays inside Bookmarks and continues to use Hermes for execution.

This specification refines sections 2, 4 and 5 of the [product specification](2026-10-20-hermes-bookmarks-design.md). It brings organization and capture UX forward from M2–M4. Raindrop is an interaction reference; exact parity, synchronization with its service, and a Raindrop account are outside scope. The earlier no-mockup preference remains: a prototype is not a prerequisite.

Deliver this revision in working vertical slices, each with real storage and both emitted interfaces. The revision covers:

- Collapsible chat, library-first navigation, responsive behavior and status visibility.
- Nested collections, tag discovery/filtering, Inbox, Favorites and Read later.
- Grid/list library presentation, pagination and a usable item detail view.
- Add/Edit forms with metadata, personal notes and durable image attachments.
- Standalone image records, so choosing Image in Add creates an actual library item.
- Matching native tools and HTTP operations over the same validated service.

The first notes editor accepts Markdown with a safe preview and separate image attachments. This is an explicit incremental delivery boundary: rich-text shortcuts, inline note-image editing, cover replacement, configurable vision enrichment, import, trash/restore, settings and export remain required by the product roadmap. This revision does not finish v1 or remove those requirements. Do not display unfinished actions as working controls.

## 2. Existing implementation and constraints

At the inspected baseline, schema version 5 has link items, generated summary/tags, durable jobs, uploaded assets and profile-scoped chat bindings. Collections, item notes, attachment associations, favorites, read-later and standalone image records do not exist. The current image control saves an unassociated asset; it does not add a library item. The library has save/get/search and shows only its first default page. Chat renders alongside the library on wide screens and has dedicated Hermes-backed sessions.

Keep the existing integration boundaries:

- One explicit backend library root, shared across participating profiles. No per-profile library fallback or cross-installation synchronization.
- Chat bindings, models, permissions and transcripts stay profile/session scoped. The library model remains separate from the chat model.
- Public SDKs and exported UI components only. No Hermes core changes, private imports, host DOM interception, copied host chat, new agent loop or separate credentials.
- Shared product UI with separate Desktop and Dashboard adapters. Each client follows its active Hermes theme.
- Develop in the existing worktree. Live install/enable, production restart, merge and release remain unauthorized. Current PR remains a draft.

## 3. Workspace layout

Wide layout:

```text
+-----------------------------------------------------------------------+
| Bookmarks       Search...                  + Add       Chat [status]   |
+-----------------+-------------------------------------+---------------+
| All items       | Collection / active filters         | Chat          |
| Inbox           | item count             Grid | List  | (when open)   |
| Favorites       |                                     |               |
| Read later      | Bookmark cards or compact rows      | History       |
|                 | title / description / domain / tags | Context       |
| Collections [+] |                                     | Conversation  |
| v Engineering   | Pagination                          | Composer      |
|   AI            |                                     |               |
|   Backend       |                                     |               |
| Tags [search]   |                                     |               |
| #ai   #reading  |                                     |               |
+-----------------+-------------------------------------+---------------+
```

The toolbar has one primary Add action. Remove the large promotional heading and always-expanded URL/image capture blocks. The sidebar remains plugin-owned, distinct from Hermes's global navigation.

Use available container width, including a resized Desktop pane, rather than assuming browser viewport width. With chat closed, sidebar plus library use the full available region. With chat open, prefer roughly 220 px for navigation and 360–420 px for chat while keeping the library readable; switch to the narrow layout before the library becomes cramped. No draggable splitter is required in this revision.

On narrow containers, navigation opens as a drawer and chat is an in-plugin full-width view with an explicit Back to library action. Add/Edit becomes a near-full-height sheet with a scrollable body and reachable save controls. Preserve the same state across width changes. Do not mount two simultaneously focusable copies of the form or chat.

Use restrained type, visible focus, quiet source/date metadata, consistent cover geometry and a useful fallback for items without an image. Grid and list show the same items, filters and selection. Essential actions must be reachable through keyboard and touch, not hover alone.

## 4. Collapsible chat

Chat starts closed on a fresh plugin page. Opening it is explicit through the Chat button or Ask Hermes. A panel close button returns space to the library and focus to the opener. Width changes, theme changes and collapse must not clear drafts, context, history selection or transcript state.

Initialize the conversation controller/transport lazily on the first open. A user browsing the library does not need a working chat model. After initialization, keep controller ownership at the workspace level; collapse hides presentation without disposing the controller or losing its state. Hidden controls cannot remain in the tab order or expose duplicate live announcements. Do not introduce a global controller that survives backend/profile ownership changes.

Collapsing is not Stop. A running turn continues under Hermes. The toolbar reports genuine state: responding, awaiting permission/answer, uncertain delivery, or idle. The running state includes an explicit Stop action bound to that exact conversation. Clicking a pending-decision indicator reopens the panel; a background event never opens it or steals focus automatically. The indicator must never answer or approve on the user's behalf. User decisions remain bound to the displayed request/session/generation, including when a popup or collapsed panel delayed the next render.

Ask Hermes opens the panel and prepares bounded selected references without sending. Preserve the current draft; do not replace it with a default prompt if it already has text. Keep the existing 20-reference and 8,000-character prompt limits. Collection-level Ask prepares explicit visible item references up to that bound; it does not attach the whole collection silently. Notes and images are never inserted into the prompt merely because they are visible in the library.

Collapse/reopen, changing a filter, or opening an item must not create another Hermes session, replay an uncertain prompt, resume an unrelated ordinary session, or incur model inference. Existing reconnect, epoch, Stop, plan isolation and stale-decision regressions remain mandatory.

## 5. Organization and browsing

### Collections

Each item belongs to one optional collection. No collection means Inbox. All items includes Inbox and all collections; Favorites and Read later are independent boolean views. Marking an item favorite or read-later does not move it or trigger inference. Opening a detail does not change either flag.

Collections have stable IDs, a name, optional parent, revision and timestamps. Support create, rename, move and delete with explicit contents policy. Names are trimmed nonempty Unicode text, at most 100 characters; sibling identity uses Unicode NFC plus casefold, so siblings cannot differ only by letter case. Preserve display spelling. Maximum nesting depth is 16. Validate the whole resulting subtree depth and reject self/descendant moves inside the same serialized write transaction.

Selecting a collection includes its descendants; the collection header makes this visible. Sidebar counts use the same rule. All items, Inbox, Favorites and Read later show whole-library totals, independent of the current search/tag filter. Collection counts include descendant items once. Search-result counts reflect every active predicate. Do not compute counts from the currently loaded item page.

Delete never deletes items. Require a choice of moving the collection's items and direct child collections to its parent (Inbox/root if it has none), or moving them to Inbox/root explicitly. Preflight sibling-name collisions and depth limits. Any invalid reparenting leaves the entire operation unchanged. This revision does not add recursive destructive deletion or drag-and-drop as the only move interface.

### Tags and filters

Show tag chips on items and a searchable, paginated tag list with whole-library item counts. Selecting tags adds visible removable filter chips. Multiple selected tags use AND semantics. Search, the selected view/collection, and tag predicates also combine with AND. Clearing search does not clear organization filters. Filter changes reset pagination, not chat state or an open form.

Tag identity uses trimmed Unicode NFC plus casefold; preserve a readable display label. Reject empty tags, NUL and invalid Unicode. Each item supports at most 20 visible tags of at most 80 characters each, consistent with the current generated-output limit. Manual tags take precedence when generated suggestions exceed the bound. Tag counts and duplicate matching use normalized identity, not display case.

Manual creation of a collection or tag requires an explicit picker action; typing a query is not a write. Collection suggestions display the full parent path. A search or tag page request is bounded to at most 100 results. Paged hierarchy responses include ancestor identities so navigation does not require an unbounded fetch of every collection in the installation.

Generated tags remain distinguishable from manual tags in detail/edit UI. Editing tags is explicit; opening and saving an unchanged form must not convert every AI tag into a manual tag. Track explicit removals so a late job cannot reintroduce an AI tag the user just removed. Tag rename/merge across the whole library is deferred; adding/removing item tags and discovering existing tags are included.

### Search, view state and pagination

Search titles, URLs, description, personal notes, saved summary and effective tags. Treat user input as literal search text, retaining the existing parameterized/literal FTS approach. Index source text only if retained under the existing product policy; this revision does not add source fetching on browse.

Return page, total, limit and offset from one consistent read snapshot. Keep the existing 1–100 limit, default 50. Expose pagination in grid and list. Preserve the current ordering when no explicit sort is requested so old clients do not silently reorder records. Stable secondary IDs prevent ties from making rows jump. An empty page after removal/filter changes falls back to a valid page.

Scope library preferences by client/backend connection and durable library identity; scope chat drafts/history by connection, library and profile. Preserve search, filters, selection, view mode and scroll while opening chat/detail. Never restore a draft into another backend because profile names happen to match. Validate stored preferences and tolerate unavailable client storage. Private form/chat text stays in scoped memory in this revision, not shared library settings or browser localStorage.

## 6. Add, detail and Edit

Add opens a dialog with Link and Image choices. Clicking an item body opens its saved detail; the title/domain has a separate explicit Open original action. Detail shows metadata, a saved AI summary, personal notes and associated images with Edit and Ask Hermes actions. Reading the saved detail does not fetch the publisher or enqueue inference.

Fields:

| Field | Add | Edit |
| --- | --- | --- |
| Source | Validated HTTP(S) URL, or one uploaded primary image | Source shown read-only; replacing the source is outside this revision |
| Title | Optional for a link; editable for an image | Editable without replacing generated content |
| Description | Optional secondary field, at most 16 KiB UTF-8 | Editable independently of notes and the generated summary |
| Collection | Current collection by default, or Inbox from non-collection views | Current value; explicit move through the picker |
| Tags | Optional manual chips with existing-tag suggestions | Preserve generated/manual provenance and explicit removals |
| Notes | Optional Markdown personal notes with safe preview | Editable separately from the AI summary |
| Attachments | Up to 10 owned PNG/JPEG/WebP images | Add/remove associations; never arbitrary file paths |
| Favorite / Read later | Optional toggles | Independent editable toggles |
| AI summary/status | Explain configured save-time processing | Read-only saved summary/status; no implicit regeneration |

Personal notes support up to 64 KiB UTF-8 text. Keep metadata requests bounded to 128 KiB of actual streamed bytes before JSON parsing. Upload images separately through existing bounded upload routes, then submit their owned IDs. Do not base64-encode images inside metadata writes. Describe the attachment picker as image-only; arbitrary documents, PDFs and video are not supported by the current asset service.

Render note preview through the existing allowlisted Markdown renderer. Raw HTML stays literal; executable links and automatic remote images remain blocked. Show associated images through authenticated owned-asset references below the note. Inline asset syntax is not part of this editor and must not be presented as supported rich-image embedding.

The dialog initially shows source, title and collection. Notes, tags and attachments are clearly labeled expandable sections, with badges for existing content. Advanced sections are optional, not hidden required fields. Required-field errors are associated with their controls. Preview is a read mode, not a separate place where edits can disappear.

Use explicit Save for this capture/edit form. Preserve every field and successfully uploaded asset ID on validation, network or conflict failure. Disable duplicate submissions synchronously while leaving nonconflicting library actions usable. On success, close the form and refresh the currently active view/counts; do not navigate back to the collection captured when the request began. If the saved item is outside the current filter, show a saved notice with a View item action.

Closing a dirty dialog through Escape, backdrop, Cancel or navigation asks Keep editing / Discard. Focus returns to the original opener if it still exists. A save in progress cannot be mistaken for cancellation. For a lost acknowledgement, retain the operation key and reconcile that operation before another create; do not silently retry a potentially accepted save. A duplicate URL returns the existing item and offers explicit Open/Edit; it must not silently overwrite notes or attach newly staged images to that record.

A form draft is owned by connection/library and item ID or new-item draft ID. Profile changes can remount the host view, so retain the draft in scoped in-memory state and restore it only in that same library. Do not intercept host internals to block a profile switch. Page reload/process exit cannot guarantee recovery of unsaved text or a not-yet-uploaded browser File; disclose this limit instead of claiming durable offline drafts.

## 7. Persistence and update semantics

Add forward-only, transactional migrations from schema 5. Preserve IDs, original URLs, existing summaries/tags, job leases/settings, assets, library identity and chat bindings. Test migration of a populated library and concurrent migrators. Record migration failures without rebuilding or resetting a user's database.

Separate the following concerns in the data model:

- Collections with parent/revision/name identity and indexes.
- Item kind (`link` or `image`), optional URL, optional primary asset, description, collection, favorite/read-later, notes, timestamps and item revision. A link requires its original unique URL; an image requires a valid owned primary asset and no fabricated URL. Existing records become links in Inbox with empty notes and false flags.
- Item-to-asset associations with role and stable asset IDs. A primary image may also be its item's preview; association count includes it within the 10-image item bound.
- Normalized tag identities and per-item manual/generated/removal state. Existing JSON tags migrate as legacy generated tags, preserving their spelling and the effective set. Keep the public `tags` list as a projection for old callers; there must be one authoritative tag-update path.
- Idempotent capture operation keys bound to a canonical validated payload and library. Reuse with the same payload returns the original result; reuse with different content is a conflict. An edit conflict or duplicate-create result must not consume the user's draft as a successful overwrite.

New edit operations require an expected item revision. Validate metadata, collection and assets and commit the edit/associations/tag changes/FTS update in one transaction. A mismatch returns a structured conflict and current server revision without partial writes. UI keeps the local draft and offers Reload saved / Keep editing; it never applies automatic last-write-wins. Retry after comparison is an explicit new save against the refreshed revision.

Keep content/enrichment generation separate from ordinary metadata revision. Existing jobs retain their immutable claim/lease fence. A collection, favorite, title or note edit must not discard a valid pending article summary or allow the job to overwrite those manual fields. Migrate the existing job's revision snapshot into an equivalent enrichment-generation check; a previously stale or cancelled job must not become eligible again during migration. On successful completion, read current tag provenance inside the transaction, merge permitted generated tags without restoring explicit removals, update the summary/status and increment item revision. Changing an attachment association is not permission for new image analysis. Refactoring this queue boundary needs focused regression review; do not weaken lease/cancellation checks to make UI tests pass.

For new image items, use existing validated owned assets and authenticated previews. Creation succeeds independently of model availability. This revision reports standalone-image AI as unavailable/not configured until the separate public vision path is implemented and verified; do not schedule text URL extraction against a made-up image URL or invent visual summaries. Automatic standalone-image analysis remains a v1 gate.

FTS updates must include changes from both manual edits and worker completion. Effective tags, counts, search results and public item projections must agree after restart and across processes. Enable and test SQLite foreign keys on every connection before beginning its transaction; no foreign-key relationship may depend on a pragma that was set only during migration. Validate existing rows before imposing new relations so migration does not silently discard invalid legacy data.

## 8. HTTP, native tools and assets

Extend the common validated dispatcher rather than adding UI-only database writes. Preserve existing save/get/search callers. New optional arguments have conservative defaults and strict unknown-field validation. Update native tool schemas, HTTP adapters and error mapping together.

Required capabilities:

- Save link or image with metadata, notes, optional owned image associations and an operation key.
- Retrieve full detail and search with collection/system-view/tag predicates and pagination.
- Revision-aware item update and personal-note update; note append and explicit replacement retain the product's native workflow requirement.
- Collection list/create/rename/move/delete with revision and contents policy.
- Paginated tag discovery and counts.
- Add/remove image associations through item edits; no arbitrary-path access.

Use the product inventory's descriptive names (`bookmark_update`, `bookmark_note_update`, `bookmark_collection_list/create/update/delete`, `bookmark_tag_list`) rather than a separate UI vocabulary. The implementation plan specifies exact schemas and route methods against the existing dispatcher. Do not accept a caller-supplied profile as authorization or as a library-root selector. State-changing requests retain host authentication/security checks and bounded input handling. Return structured `conflict`, `invalid_argument`, `not_found` and sanitized configuration/storage failures; map HTTP revision conflicts to 409.

Image files retain existing validation/re-encoding limits: PNG/JPEG/WebP, 10 MiB input and 20 million decoded pixels, no animation, metadata stripped. Use backend-owned asset IDs and authenticated transport on both clients. Failed/abandoned drafts can leave staged assets, as they already can at baseline. Unlink removes only the association; this revision never deletes bytes that another item might reference. Disclose retained unassociated assets and leave audited garbage collection/quotas to the required asset-retention work. Do not delete a file merely because a late upload response belongs to a closed dialog.

The common HTTP dependency can activate an already accepted enrichment worker on a read request. This design prohibits initiating new work on browse; it does not claim all GET requests are globally inference-free when existing jobs are queued. Use a disposable no-enrichment fixture for charge-free UI probes.

## 9. UI modules and public host integration

Keep `chat-session.js` and `chat-transport.js` as the Hermes protocol boundary. Refactor workspace/presentation ownership only as required for collapse; preserve the existing adversarial tests. Split the growing library UI into focused navigation, query/list, detail and form modules instead of putting all behaviors in `library.js` or `chat-panel.js`. Continue generating both bundles from source.

The public Desktop SDK documents dialog controls, theme tokens, host state/events and scoped REST. Dashboard has a separate SDK and must not be assumed to export the same control set. Use the verified public Desktop dialog components through an adapter, and a plugin-owned native `<dialog>` adapter for Dashboard. Both implement equivalent focus return, Escape/backdrop behavior, proper labels, focus containment and dirty-state handling, and must be exercised in the actual emitted client. If the targeted Desktop export is unavailable, report that capability mismatch before choosing a replacement; do not silently import private host UI. No portals into undocumented DOM targets.

Check the exact target SDK version when implementing. The source/documentation read for this design is not runtime acceptance of the new feature. Do not fix a missing host export by editing Hermes core or copying its internal dialog implementation.

## 10. Acceptance and evidence

The revision is complete only when these behaviors are verified:

1. First open is library-first with chat closed. Collapse/reopen and narrow/wide transitions preserve a live stream, unsent draft, selection and Stop target without another session or prompt.
2. Hidden running/pending/uncertain states remain visible through the Chat control. A delayed approval click cannot target a replacement request.
3. Collections and descendants have persistent create/rename/move/delete behavior, cycle/depth checks and collision-safe non-destructive deletion across UI and tools.
4. Inbox/Favorites/Read later and tag/search predicates return the same records/counts through both adapters. More than 50 items and tags remain reachable with correct pagination.
5. Add and Edit persist metadata, notes and associations; duplicate/lost-ack paths never overwrite an existing record or create duplicate image items. Reload and another client see the same saved fields.
6. Failed saves preserve all form inputs. A stale revision returns a conflict with no partial association/tag writes. Late success refreshes the current filter rather than restoring an older one.
7. A late enrichment result cannot overwrite notes/manual tags or resurrect removed tags. Metadata edits do not strand the pending enrichment status. Existing lease, cancellation, contention and restart tests still pass.
8. Actual image records appear in the library with durable owned previews, without pretending visual inference succeeded. A link attachment and a primary image remain distinct roles.
9. Unsafe Markdown, HTML, URLs and malformed uploads remain inert/rejected. Missing assets, long text and empty/error/loading states render usefully.
10. Both emitted entrypoints pass real React interaction tests. Browser evidence covers light/dark, wide/narrow/resized containers, keyboard focus, dialog close/discard, scroll preservation, theme changes and no horizontal overflow or page JS errors.
11. Python suites on supported tested runtimes, Node suite, deterministic bundles, syntax/diff checks and official isolated plugin validation pass. Published code requires exact-head CI readback. Existing warnings and skipped target/provider checks remain explicit.

Use test-first implementation and the established hybrid workflow. Review the new migration/enrichment/manual-edit boundary independently once; consume existing reviews instead of redispatching the old M1/chat review. Author fixes need reproducing regressions and the full gate, not speculative review loops.

The actual connected Electron and successful real-provider/OAuth/independent-machine acceptance gates remain open from M1. New fixture/browser tests do not close them. No live installation, merge or release is implied by approving this design.

## 11. Design choices and next gate

The selected approach extends the shared service and refactors plugin presentation. A CSS-only sidebar would misrepresent collections and attachments that do not exist in storage. Replacing the complete application with another UI framework would add build/host risk without improving ownership; both alternatives are rejected for this revision.

Delivery ordering is: workspace/collapse and form shell; organization/persistent metadata; safe notes/association/image-record flows; full interaction and boundary verification. A shell slice must label unavailable fields/actions and cannot be reported as the completed revision. Imports/export and the remaining rich-editor/vision/settings work retain their roadmap milestones.

The owner approved this written specification on 2026-10-21. The [test-first implementation plan](../plans/2026-10-21-library-first-workspace.md) preserves the existing hybrid execution method and awaits its required review before product changes. All capabilities in this design remain acceptance targets until implemented and verified.

## References

- [Current status](../../STATUS.md) and [delivery roadmap](../../ROADMAP.md).
- [Product requirements](2026-10-20-hermes-bookmarks-design.md).
- [Implemented chat and remaining gates](../../verification/in-plugin-chat.md), [review fixes](../../verification/in-plugin-chat-review-fixes.md).
- Official Hermes Desktop Plugin SDK: `https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk` (read 2026-10-21).
- Official Hermes Dashboard guide: `https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard` (read 2026-10-21); verify the linked Dashboard extension contract at implementation time.
- Official Dashboard extension contract: `https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard` (read 2026-10-21); exact component availability still requires target-version inspection.
- Inspected baseline source: `ui/library.js`, `ui/chat-panel.js`, `bookmarks/migrations.py`, `bookmarks/storage.py`, `bookmarks/service.py`, `bookmarks/jobs.py`, `dashboard/plugin_api.py`, `scripts/build-ui.cjs`.
