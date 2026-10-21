# Library-first workspace implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for direct implementation, preserving the owner's established hybrid workflow. Use an independent reviewer for the new migration/enrichment boundary and one final review of this revision, not a fresh implementer/reviewer cycle for every task. Steps use checkbox syntax for tracking.

**Goal:** Deliver the complete approved library-first UX revision: collapsible Hermes-backed chat, persistent organization, grid/list browsing and safe Add/Edit forms with Markdown notes and owned images.

**Architecture:** Keep the explicit-root SQLite service authoritative for Desktop, Dashboard and native tools. Add transactional library organization/capture operations, then bind focused React navigation/detail/form components to them. Keep the existing Hermes conversation controller/transport; separate panel visibility from controller lifetime.

**Tech stack:** Python standard library/SQLite FTS5, existing FastAPI/httpx/Pillow integration, React supplied by Hermes, existing Marked lexer and safe renderer, esbuild-generated Desktop ESM and Dashboard bundles, unittest/Node test runner/React/jsdom and actual-browser acceptance. No new production dependency is needed for this revision.

**Spec:** `docs/superpowers/specs/2026-10-21-library-first-workspace-design.md`, approved by the owner with “lets implement all”. This plan awaits its own written review before product changes.

**Baseline:** `c811880ac7739f805f4622cdb7369f04f7d4c94e`; existing worktree/branch only. Fresh baseline execution: 86 Python tests on CPython 3.14.7 and 41 Node tests passed; deterministic bundle check passed. Those are baseline results, not evidence for any new task.

## Global constraints

- One explicit backend library root shared across participating profiles; chat remains profile/session scoped. No alternate library fallback or cross-installation synchronization.
- Public Hermes SDKs/exports only. No core edits, private imports, host DOM interception, copied chat internals, new agent loop or credentials.
- Chat initially closed; keep a running controller when hiding it. 20 context references and 8,000-character prompt limit remain.
- Collections: normalized sibling identity, 100-character display name limit, maximum depth 16. Multiple tags and query/view filters combine with AND.
- At most 20 effective tags of at most 80 characters. Preserve manual/generated/removal provenance; generated results cannot restore explicitly removed tags.
- Notes: 64 KiB UTF-8; description: 16 KiB UTF-8. Metadata body: 128 KiB streamed bytes. Paginated reads: default 50, limit 1–100, nonnegative bounded offset.
- Images: PNG/JPEG/WebP only, existing 10 MiB/20-million-pixel validation, no animation; at most 10 associated images including a primary image. Upload separately from metadata.
- Use explicit Save and revision conflicts. Preserve drafts/upload IDs on failure. A lost acknowledgement is uncertain, not permission to replay blindly.
- Host theme and container-responsive layouts on both emitted clients; keyboard/touch, focus containment/return and dirty-close behavior are required.
- Markdown plus safe preview and separate image attachments is the approved editor stage. Full rich-text/inline images, vision settings, imports, trash/restore, settings and export remain roadmap work, not silently included or dropped.
- No active installation, production restart, merge, release, real-vault migration or catalog submission. Disposable synthetic host fixtures and development commits are allowed. Preserve the existing draft PR and its open target/provider gates.
- Prefix shell commands with `rtk`. Write probes under `$TMPDIR`; do not change installed plugins. Update status/evidence after verified tasks.

## Review focus

1. Multi-client edits race a late generated result: preserve manual notes/tags and tag removals while allowing the queued summary to finish. Task 4 owns the regression.
2. A connection/profile/theme/container switch occurs with an open or saving form: a late completion cannot publish into another library or drop its draft. Tasks 6–7 own the regression.
3. Two writers move A under B and B under A, or deletion reparents colliding sibling names: serialize validation and commit; reject without any partial move. Task 3 owns the regression.
4. A timed-out capture/upload may already be durable: stable operation keys reconcile before retry; duplicate URL handling never overwrites notes or attaches staged files. Tasks 4 and 6 own the regression.
5. A permission request arrives while chat is hidden and its displayed predecessor is clicked after reopening: visibility cannot grant permission or weaken request/session/generation ownership. Tasks 1 and 8 own the regression.

## File ownership and shared contracts

New backend modules:

| File | Responsibility |
| --- | --- |
| `bookmarks/library_schema.py` | One forward migration from schema 5; frozen-data backfill inside the caller's transaction |
| `bookmarks/labels.py` | Pure NFC/casefold identity and bounded display-label validation |
| `bookmarks/collections.py` | Hierarchy validation, parent-aware pages/counts and non-destructive mutations |
| `bookmarks/items.py` | Capture/update/note operations, operation receipts, image associations and full item projection |
| `bookmarks/tags.py` | Effective tag/provenance merge and transactional tag-cache refresh |
| `bookmarks/queries.py` | Literal FTS predicates, view/tag/descendant filtering and snapshot totals/pages |

`BookmarkService` remains the public facade. `Storage` remains the short-lived connection/transaction owner; no second connection inside an atomic mutation. New classes/functions accept that Storage or the active connection, never infer a root. Keep queue ownership in `jobs.py` and worker lifecycle in existing files.

New frontend modules, concatenated before their consumers by `scripts/build-ui.cjs`:

| File | Responsibility |
| --- | --- |
| `ui/library-state.js` | Validated library query/preferences and in-memory library/item draft registry |
| `ui/library-dialog.js` | Shared dialog contract, public Desktop Dialog adapter, Dashboard native-dialog adapter |
| `ui/library-navigation.js` | Collections, system views, paged tags, collection forms |
| `ui/library-items.js` | Grid/list items, selection, page controls, owned thumbnail reads |
| `ui/library-detail.js` | Saved detail/summary/Markdown notes/associated images, Edit and Ask actions |
| `ui/library-form.js` | Add/Edit state machine, uploads, revision conflict and uncertain-write recovery |
| `ui/library.css`, `ui/chat.css` | Scoped, container-responsive styling; no host/global restyling |

Use the following contracts consistently in every task:

```text
Item = existing public item fields plus:
  kind: 'link'|'image', url: string|null, description: string, notes: string,
  collection_id: string|null, favorite: bool, read_later: bool,
  primary_asset_id: string|null, created_at: number, updated_at: number,
  tags: string[], tag_details: [{name: string, source: 'manual'|'generated'}],
  attachments: [{asset_id, role: 'primary'|'attachment', mime_type, size, width, height}]
Collection = {id, name, parent_id: string|null, revision, created_at, updated_at}
CollectionPage = {collections: [Collection + {count, path: [{id,name}]}], total, limit, offset}
TagPage = {tags: [{name, count}], total, limit, offset}
ItemPage = {items: Item[], total, limit, offset}
Counts = {all, inbox, favorites, read_later}
Receipt = {operation_key, item_id, accepted_revision, outcome: 'created'|'duplicate'}

BookmarkService.identity() -> {library_id}
BookmarkService.save_link(url, title='') -> Item       # legacy signature/duplicate behavior
BookmarkService.capture(*, kind='link', url=None, title='', description='', notes='',
  collection_id=None, tags=(), favorite=False, read_later=False,
  primary_asset_id=None, attachment_ids=(), operation_key=None) -> {item: Item, receipt: Receipt|null}
BookmarkService.capture_status(operation_key) -> {item: Item, receipt: Receipt}
BookmarkService.update(item_id, expected_revision, changes: dict) -> Item
BookmarkService.note_update(item_id, expected_revision, text, mode='replace') -> Item
BookmarkService.get(item_id) -> Item
BookmarkService.search(query='', limit=50, offset=0, *, view='all',
  collection_id=None, tags=()) -> ItemPage
BookmarkService.counts() -> Counts
BookmarkService.collection_list(limit=50, offset=0, *, parent_id=None, query='') -> CollectionPage
BookmarkService.collection_create(name, parent_id=None) -> Collection
BookmarkService.collection_update(collection_id, expected_revision, changes: dict) -> Collection
BookmarkService.collection_delete(collection_id, expected_revision, contents_policy) -> {deleted_id}
BookmarkService.tag_list(query='', limit=50, offset=0) -> TagPage
```

`changes` for an item accepts only `title`, `description`, `notes`, `collection_id`, `favorite`, `read_later`, `add_tags`, `remove_tags`, `attachment_ids`. Source/kind/primary image are immutable on Edit. Collection changes accept only `name`/`parent_id`. `contents_policy` is exactly `move_to_parent` or `move_to_inbox`. For root collection listing, `parent_id=None` means direct root children; search finds bounded matches across the tree with full ancestor paths. Counts include descendants, but children lists remain paginated.

`ConflictError` extends `BookmarkError` with public `code='conflict'`, safe message and optional `current_revision`; the dispatcher includes only that bounded detail, not raw submitted/current notes. Native/API success remains `{ok:true,result:Item}` for saves. When a supplied operation key has a receipt, add a top-level `receipt` field; legacy save/get payload equality remains unchanged when no operation key was supplied. Receipt lookup returns `{ok:true,result:{item,receipt}}`. Image capture requires a supplied operation key. Link callers without one retain URL idempotency and do not create an operation row on every duplicate read/save.

## Task 1: Collapse chat without changing its authority

**Files:** Modify `ui/chat-panel.js`, `ui/chat.css`, `ui/library.js`, `tests/test_chat_ui.cjs`, `scripts/build-ui.cjs`; create `tests/test_workspace_ui.cjs`, `tests/helpers/emitted-client.cjs`; rebuild both emitted bundles.

**Consumes:** Existing `BookmarkChat`, safe Markdown and both transports. **Produces:** a workspace Chat control, lazy initialization, hide/reopen behavior and genuine toolbar status. Extend the shared chat presentation with `onState`, `onStopReady` and `onClose` callbacks; the owned controller remains mounted after first open, scoped to the workspace connection/profile identity.

The Chat trigger keeps a stable accessible name `Chat` while its visible status text changes. The test helper `button(app,name)` resolves that accessible name (or exact visible text for controls without a label), so a responding indicator cannot break the test's locator.

- [ ] Write a shared emitted-client test harness by extracting the existing real React/jsdom setup without weakening its protocol doubles. Export `mount(target, options)`, `click`, `typeField`, `button` and `flush`. `mount` returns `element`, `calls`, `emit`, `apiCalls`, `setScope`, `rerender` and `close`; `typeField` supports input/textarea/select native value setters. `setScope` updates the public fixture atoms, not host DOM. Tests live in top-level `tests/test_*.cjs`; helper files do not register tests.

```javascript
for (const target of ['desktop','dashboard']) test(`${target}: collapse retains one running conversation`, async () => {
  const app=await mount(target);
  try {
    assert.equal(app.element.querySelector('[aria-label="Bookmarks conversation"]'),null);
    assert.equal(app.calls.length,0);
    await click(button(app,'Chat'),app);
    await typeField(app,'Message Hermes','Keep this draft');
    await click(button(app,'Send'),app);
    await click(button(app,'Close chat'),app);
    app.emit('message.delta',{text:'Still working'});
    await flush();
    assert.match(button(app,'Chat').textContent,/responding/i);
    await click(button(app,'Chat'),app);
    assert.match(app.element.querySelector('[role="log"]').textContent,/Still working/);
    assert.equal(app.calls.filter(c=>c.method==='session.create').length,1);
    assert.equal(app.calls.filter(c=>c.method==='prompt.submit').length,1);
  } finally { await app.close(); }
});
```

- [ ] Run `rtk proxy node --test tests/test_workspace_ui.cjs`; verify failure is absent collapse/lazy behavior, not a broken helper. Add tests for pending/uncertain toolbar states, Stop from the collapsed toolbar, Ask preserving an existing draft, no background opening/focus steal, and hidden controls excluded from focus. Existing restore tests must explicitly open Chat; assertions about thread ownership/decisions stay intact.
- [ ] Add `chatOpened` and `chatVisible` at workspace level, plus the genuine latest owned state. Render the chat once `chatOpened` is true; hide its wrapper with semantic `hidden`/inert presentation rather than conditionally removing its controller. Scope change still disposes the old owner. Retire the unsupported status callback before an old controller can update a new toolbar. Pass explicit `onClose` to presentation and keep Stop tied to the owned controller.

```javascript
function openChat() { setChatOpened(true); setChatVisible(true); }
function closeChat() { setChatVisible(false); opener.current?.focus(); }
// Keep identity/transport initialization inside the first-open lifecycle.
// The wrapper's hidden state must not be overridden by display:flex in CSS.
```

- [ ] Run `rtk proxy npm run build && rtk proxy npm test && rtk proxy npm run check:build`. Preserve existing real-emitted-client tests, replacing only superseded always-open/inline-capture assumptions as later tasks land.
- [ ] Update STATUS with actual results and commit source/tests/bundles: `rtk git commit -m "feat: make the library chat panel collapsible"`.

## Task 2: Migrate library records without losing existing data

**Files:** Create `bookmarks/library_schema.py`, `bookmarks/labels.py`, `tests/library_fixtures.py`, `tests/test_library_migration.py`; modify `bookmarks/migrations.py`, `bookmarks/storage.py`, `tests/test_storage.py`. Update the expected schema version once, only after migration tests pass.

**Consumes:** Existing schema 5 and `Storage._transaction`. **Produces:** schema 6, pure `normalize_label(value,max_chars)->(display,key)`, foreign keys on every connection and the new nullable-URL item model. Existing operations must still run before new UI/API operations are added.

- [ ] Add a frozen prior-schema fixture independent of production migration code. The fixture executes the following baseline shape, inserts one legacy link with revision 7 and tags `["AI","Reading"]`, one pending job with revision 7, one cancelled job, route settings, an asset and a chat binding, then sets `user_version=5`. Copy the existing synthetic tiny PNG to its owned `.blob` path. Save the actual IDs/rowid/job tokens/library identity before upgrade for assertions.

```python
V5_SQL = """
CREATE TABLE items(id TEXT PRIMARY KEY NOT NULL,url TEXT NOT NULL UNIQUE COLLATE BINARY,
 title TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=1),
 enrichment_status TEXT NOT NULL DEFAULT 'not_started',summary TEXT NOT NULL DEFAULT '',
 tags TEXT NOT NULL DEFAULT '[]',enrichment_job_id TEXT);
CREATE VIRTUAL TABLE items_fts USING fts5(title,url,content='items',content_rowid='rowid',tokenize='unicode61');
CREATE TRIGGER items_fts_insert AFTER INSERT ON items BEGIN
 INSERT INTO items_fts(rowid,title,url) VALUES(new.rowid,new.title,new.url); END;
CREATE TRIGGER items_fts_delete AFTER DELETE ON items BEGIN
 INSERT INTO items_fts(items_fts,rowid,title,url) VALUES('delete',old.rowid,old.title,old.url); END;
CREATE TRIGGER items_fts_update AFTER UPDATE ON items BEGIN
 INSERT INTO items_fts(items_fts,rowid,title,url) VALUES('delete',old.rowid,old.title,old.url);
 INSERT INTO items_fts(rowid,title,url) VALUES(new.rowid,new.title,new.url); END;
CREATE TABLE library_config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE jobs(id TEXT PRIMARY KEY,item_id TEXT NOT NULL,revision INTEGER NOT NULL,
 settings TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',worker TEXT,token TEXT,
 expires REAL,attempts INTEGER NOT NULL DEFAULT 0,error TEXT,result TEXT,UNIQUE(item_id,revision));
CREATE INDEX jobs_claim ON jobs(state);
CREATE TABLE assets(id TEXT PRIMARY KEY,mime_type TEXT NOT NULL,size INTEGER NOT NULL,width INTEGER NOT NULL,height INTEGER NOT NULL);
CREATE TABLE chat_threads(id TEXT PRIMARY KEY NOT NULL,profile TEXT NOT NULL,session_id TEXT NOT NULL,
 title TEXT NOT NULL,model TEXT NOT NULL,created_at REAL NOT NULL DEFAULT 0,UNIQUE(profile,session_id));
CREATE INDEX chat_threads_profile ON chat_threads(profile,created_at DESC);
"""
```

- [ ] Run `rtk proxy python -W error -m unittest discover -s tests -p 'test_library_migration.py' -v`. Add failing cases for retained IDs/rowids/URLs/tags/summary/assets/jobs/chat, populated multi-process upgrades, invalid legacy tag JSON rolling the entire upgrade back, unknown future version, failed DDL rollback and per-connection foreign-key enforcement.
- [ ] Append one callable migration step to the existing ordered migration tuple; do not edit historical steps. `migrate()` invokes callable steps inside the same caller-owned transaction and advances `user_version` only after success. In schema 6: create collections; drop old FTS triggers/table; copy rows into a constrained `items_next` preserving rowid; replace `items`; build item-tag/association/operation tables and six-column FTS; backfill labels in Python for Unicode correctness. Do not use `executescript` or commit from a migration helper.

```python
# Storage._transaction: before BEGIN, on every fresh connection.
connection.execute('PRAGMA foreign_keys=ON')
# migrate: each statement remains ordered and in one outer transaction.
if callable(statement):
    statement(connection)
else:
    connection.execute(statement)
```

`items` gains the public metadata fields, internal `enrichment_generation` and constrained kind/source validity. `collections` enforces parent existence and normalized sibling uniqueness with separate root/nonroot indexes. `tags(id,label,identity UNIQUE)` and `item_tags(item_id,tag_id,manual,generated,suppressed)` hold provenance; the existing `items.tags` JSON column becomes a transactionally maintained effective-label cache for compatibility/FTS. `item_assets(item_id,asset_id,role)` references existing assets. `capture_operations(operation_key PRIMARY KEY,payload_hash,item_id,accepted_revision,outcome)` stores receipts, not raw notes/credentials. Foreign keys from item children cascade associations when an item is genuinely deleted; collection and asset deletion use restrict. Existing jobs remain intact and gain `generation`, initialized to their original revision; item generation starts at its original revision, preserving stale-job rejection. Nullable image URLs are never synthetic URLs. New legacy link defaults are Inbox, false flags, empty notes/description and null primary image.

- [ ] Verify `PRAGMA foreign_key_check`, `PRAGMA integrity_check`, literal FTS behavior and full original Python suite. Compare preserved legacy fields by projection rather than freezing the entire expanded public item dict. An intentionally corrupt fixture must retain version 5 and its original rows after failure.
- [ ] Update evidence and commit: `rtk git commit -m "feat: migrate shared library organization and image records"`.

## Task 3: Persist collections, tags, filtered browsing and counts

**Files:** Create `bookmarks/collections.py`, `bookmarks/queries.py`, `bookmarks/tags.py`, `tests/test_collections.py`, `tests/test_library_queries.py`; modify `bookmarks/service.py`, `bookmarks/storage.py`, `bookmarks/jobs.py`, `bookmarks/errors.py`.

**Consumes:** Schema 6/labels/Storage. **Produces:** the `collection_*`, `tag_list`, `counts` and extended `search` service signatures above, plus `identity()`. `CollectionStore` consumes Storage; queries and tag projection accept the active connection to preserve count/page atomicity.

- [ ] Write the first persistent hierarchy/filter test using real temporary SQLite.

```python
class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.service=BookmarkService(Path(self.temp.name))
    def test_parent_filter_includes_descendants_and_move_rejects_cycle(self):
        parent=self.service.collection_create('Engineering')
        child=self.service.collection_create('AI',parent['id'])
        item=self.service.save_link('https://example.org/a','One')
        with self.service._storage._transaction(write=True) as connection:
            connection.execute('UPDATE items SET collection_id=? WHERE id=?',(child['id'],item['id']))
        self.assertEqual(self.service.search(collection_id=parent['id'])['total'],1)
        with self.assertRaises(ConflictError):
            self.service.collection_update(parent['id'],parent['revision'],{'parent_id':child['id']})
        self.assertEqual(self.service.collection_list()['collections'][0]['id'],parent['id'])
```

The collection assignment is fixture setup, not a new public write path. Task 4 adds a public-update parity test; the cycle check and filtered query here must fail on missing Task 3 operations, not on a missing Task 4 method.

- [ ] Run `rtk proxy python -W error -m unittest discover -s tests -p 'test_collections.py' -v`. Add tests for NFC/casefold sibling collisions, root null uniqueness, subtree depth 16, cross-process reciprocal moves, deletion policies/collisions/rollback, unknown IDs, stale collection revisions, descendant counts independent of search and paged paths. Query tests seed more than 50 items/tags, combine query/view/collection/tags with AND, exercise huge offsets, literal FTS punctuation and restart readback.
- [ ] Implement serialized hierarchy mutation in `BEGIN IMMEDIATE`; recursively inspect target ancestors and subtree height before any update. For delete, validate all target sibling identities first, reparent direct children and move direct items, then delete only the chosen collection. Increment revisions of affected children/items with timestamps; never delete their records. Root listing returns direct children with paths/counts; query matches return full bounded ancestor paths. Build query predicates and parameter values separately; descendant IDs use a recursive CTE capped by the valid depth. Aggregate counts over the full eligible dataset in the same read transaction as each page, not over the returned page.

Define the shared conflict error in this task so collection callers and Task 4 consume one type:

```python
class ConflictError(BookmarkError):
    code='conflict'
    message='The saved state changed or the requested organization conflicts. Review it before saving again.'
    def __init__(self,current_revision=None):
        super().__init__()
        self.current_revision=current_revision
```

```python
# All selected tags are separate EXISTS predicates, so matching is AND.
for identity in identities:
    predicates.append('EXISTS (SELECT 1 FROM item_tags it JOIN tags t ON t.id=it.tag_id '
                      'WHERE it.item_id=items.id AND t.identity=? '
                      'AND (it.manual=1 OR it.generated=1) AND it.suppressed=0)')
    parameters.append(identity)
```

`tags.effective_tags(connection,item_id)` returns at most 20 labels and matching provenance; manual labels are first and suppressions always win. `tags.refresh_cache(connection,item_id)` updates `items.tags` with that projection. `tags.merge_generated(connection,item_id,labels)` replaces only generated membership, retains manual/removal state and refreshes the cache. Task 4 uses these same functions, not another merge implementation.

Wire the existing `JobQueue.complete` success path to `merge_generated` in its existing transaction in this task, retaining its original revision/lease eligibility until Task 4. Add a real queue-completion test proving `get().tags`, tag counts, search and generated provenance agree. Do not leave tag discovery stale until the later generation refactor.

- [ ] Run both focused test files and the entire Python suite. Verify empty/root cases, all system counts and `get` projections agree with filtered pages. Ensure service reads never enqueue jobs.
- [ ] Update status/evidence and commit: `rtk git commit -m "feat: add persistent collections and library filtering"`.

## Task 4: Safe capture, metadata/notes/images and enrichment merging

**Files:** Create `bookmarks/items.py`, `tests/test_item_updates.py`, `tests/test_capture_receipts.py`, `tests/test_enrichment_edits.py`; modify `bookmarks/service.py`, `bookmarks/storage.py`, `bookmarks/errors.py`, `bookmarks/jobs.py`, `tests/test_jobs.py`, `tests/test_assets.py`.

**Consumes:** Schema 6, collection validation, tag merge/cache and existing AssetStore metadata/validation. **Produces:** capture/status/update/note signatures and expanded Item projection, idempotent receipts, `ConflictError` and generation-aware completion. No image analysis is added.

- [ ] Add a failing late-result test with real JobQueue and user metadata edits.

```python
class EnrichmentEditTests(unittest.TestCase):
    def test_late_result_merges_without_clobbering_manual_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); service=BookmarkService(root)
            item=service.save_link('https://example.org/queued','Original')
            queue=JobQueue(root)
            job=queue.enqueue(item['id'],item['revision'],{'provider':'fixture','model':'fixture','owner_profile':'fixture'})
            lease=queue.claim('worker',100,30)
            saved=service.update(item['id'],service.get(item['id'])['revision'],
                {'notes':'My private note','add_tags':['Manual'],'remove_tags':['AI']})
            result={'summary':'Saved summary','tags':['AI','Reading'],'provider':'fixture','model':'fixture','coverage':'extracted_text'}
            self.assertTrue(queue.complete(job,'worker',result,token=lease['token'],now=110))
            got=service.get(item['id'])
            self.assertEqual(got['notes'],saved['notes'])
            self.assertEqual(set(got['tags']),{'Manual','Reading'})
            self.assertEqual(got['enrichment_status'],'succeeded')
```

- [ ] Run `rtk proxy python -W error -m unittest discover -s tests -p 'test_enrichment_edits.py' -v`. Add capture tests for same-key same/different payloads, competing processes, duplicate URL with differing notes/assets, interrupted acknowledgement followed by receipt lookup and image item retries. Add update tests for stale revisions, invalid asset/collection causing total rollback, UTF-8 byte bounds/NUL/surrogates, true boolean validation, tag provenance/no-op form roundtrip, explicit note append versus replace, image associations surviving restart and unlink preserving shared files. Assert image captures do not enqueue URL-extraction jobs.
- [ ] Implement normalized/validated capture before a single write transaction. Canonical payload hashing uses sorted JSON with explicit defaults and SHA-256; the operation key is UUID-shaped bounded text and scoped by the selected library database. Lookup/conflict-check it before applying a mutation. A duplicate URL produces a duplicate receipt pointing at the existing item and leaves every manual field/association untouched. Require image operation keys and real primary assets. Item `update` checks expected revision before applying all fields/tags/associations atomically; source replacements/unknown fields reject. `note_update` translates append/replace into the same guarded update transaction, preserving the 64 KiB final byte bound.

```python
row=connection.execute('SELECT * FROM items WHERE id=?',(item_id,)).fetchone()
if row is None: raise NotFoundError()
if row['revision'] != expected_revision:
    raise ConflictError(current_revision=row['revision'])
# Only after validating every supplied field/reference: update fields,
# apply tag deltas, replace attachment associations, refresh cache and read Item.
```

For jobs, preserve lease token, exact active job ID, post-lock time sampling, immutable route/settings and cancellation/retry behavior. Automatic capture stores the generation in its job. Explicit queue admission checks the supplied current item revision, idempotently reuses an existing same-revision job and advances the generation only for a genuinely new accepted job. Complete/fail/recover/cancel update item processing state only while both `enrichment_job_id` and generation match that job. Completion merges generated tags through Task 3's transaction-owned merge and updates only generated summary/status plus item revision/timestamp; ordinary edits leave generation unchanged. Superseded job completion returns false and records a sanitized conflict without touching current status. Migrate stale snapshots conservatively. The old test that rejects every raw title-revision edit is superseded by the approved metadata semantics: replace it with public metadata-edit survival and an explicit stale-generation rejection test; retain all token/lease/cancel/lock-clock regressions unchanged.

- [ ] Run all capture/update/enrichment-edit tests and the full Python suite with `-W error`. Use real SQLite locks/processes to prove receipt and revision races; no provider calls. Request one independent read-only migration/enrichment/manual-edit boundary review after Tasks 2–4 are green, reproduce any Important findings RED→GREEN, then consume that review.
- [ ] Update status/evidence and commit: `rtk git commit -m "feat: add revision-safe notes images and capture receipts"`.

## Task 5: Native tool and authenticated HTTP parity

**Files:** Modify `native_tools.py`, `runtime.py`, `dashboard/plugin_api.py`, `tests/test_tools.py`, `tests/test_host_bindings.py`, `tests/test_host_smoke.py`; create `tests/test_organization_api.py`. Existing assets/chat endpoints retain their separate limits.

**Consumes:** Service contracts in Tasks 2–4. **Produces:** strict nested schemas, native/HTTP parity and these exact routes under `/api/plugins/hermes-bookmarks`:

| Route | Dispatcher operation / request |
| --- | --- |
| `GET /library/identity` | service `identity`, no chat/profile resolution |
| `GET /counts` | service `counts` |
| `GET /items` | `bookmark_search`; repeated `tag` parameters parsed as `tags` |
| `POST /items` | `bookmark_save`; old URL-only request still valid |
| `POST /items/{item_id}/update` | `bookmark_update`; body expected_revision, changes |
| `POST /items/{item_id}/notes` | `bookmark_note_update`; body expected_revision, text, mode |
| `GET /captures/{operation_key}` | `bookmark_capture_status` |
| `GET /collections` | `bookmark_collection_list` |
| `POST /collections` | `bookmark_collection_create` |
| `POST /collections/{collection_id}/update` | `bookmark_collection_update` |
| `POST /collections/{collection_id}/delete` | `bookmark_collection_delete`, expected_revision, contents_policy |
| `GET /tags` | `bookmark_tag_list` |

Route identities must not be overridden by body/query identities. Mutating requests stream-bound actual bytes to 128 KiB before parsing. Collection/tag/search query keys are strictly validated, including repeated tags; don't collapse repeated parameters with `dict(query_params)`.

- [ ] Add a real-ASGI/native roundtrip test using the existing `ToolTests` setup and new `OrganizationAPITests` fixture.

```python
async def test_conflict_is_409_and_notes_are_shared(self):
    item=(await self.call('bookmark_save',{'url':'https://example.org/shared'}))['result']
    body={'expected_revision':item['revision'],'changes':{'notes':'A saved note','favorite':True}}
    updated=await self.client.post('/api/plugins/hermes-bookmarks/items/'+item['id']+'/update',json=body)
    self.assertEqual(updated.status_code,200)
    self.assertEqual((await self.call('bookmark_get',{'item_id':item['id']}))['result']['notes'],'A saved note')
    stale=await self.client.post('/api/plugins/hermes-bookmarks/items/'+item['id']+'/update',json=body)
    self.assertEqual(stale.status_code,409)
    self.assertEqual(stale.json()['error']['code'],'conflict')
```

- [ ] Run `rtk proxy python -W error -m unittest discover -s tests -p 'test_organization_api.py' -v`. Add native/UI symmetry tests for collection deletion policies, image receipts, tags/counts, repeated tags, unknown nested fields, bool-versus-int confusion, duplicate keys, 128 KiB chunked metadata (regardless of Content-Length), owned assets, invalid profile/root/credential fields and read-only receipt lookup. Plain ASGI tests do not claim host auth middleware passed.
- [ ] Extend the common validation helper to validate strict object/array/nullable/boolean types and bounded nested fields before service use. Dispatch new names explicitly; do not leave the current catch-all `else=search`. Expose read-only library identity/counts without deriving profile or accepting credentials. Include safe conflict revision details; map conflict→409, oversized metadata→413, not_found→404 and existing storage/config errors→503. Retain public async native handlers and existing worker activation rules. Keep `bookmark_save` URL/title legacy callers and normal `result` shape; add `receipt` only when requested. Schema image choices validate XOR source constraints in service.

Use a duplicate-key-rejecting `json.loads(..., object_pairs_hook=...)` for bounded metadata bodies, including nested objects. Reject repeated scalar query parameters as ambiguous; allow only the documented repeated `tag` parameter. Do not change the chat endpoint's independent 16 KiB limit or the existing image/base64 limits while factoring metadata parsing.
- [ ] Run all API/native tests, original chat/asset tests and full Python suite. Verify actual isolated-host unauthorized GET/POST rejection separately in Task 8. Update tool inventory expectations to the exact implemented set; do not delete strict-registration assertions.
- [ ] Update docs/status and commit: `rtk git commit -m "feat: expose organization and safe edits through native tools and API"`.

## Task 6: Add/Edit dialog, notes, uploads and detail

**Files:** Create `ui/library-state.js`, `ui/library-dialog.js`, `ui/library-form.js`, `ui/library-detail.js`, `tests/test_library_form.cjs`, `tests/test_library_detail.cjs`; modify `ui/library.js`, `scripts/build-ui.cjs`, `ui/library.css`, the emitted-client helper; rebuild both bundles.

**Consumes:** Task 5 routes and Task 1 chat opener. **Produces:** `createLibraryForm(React,adapter,components)`, `createLibraryDetail(React,adapter,components)`, `createLibraryDialog(React,components)`, `libraryDrafts` keyed by connection/library/item/new-draft. `LibraryForm` props are `{ctx,scope,libraryId,item,defaultCollection,onSaved,onClose}`; `LibraryDetail` props are `{ctx,scope,libraryId,itemId,onEdit,onAsk,onClose}`. `onSaved` receives `{item,receipt}`. Adapters supply authenticated `request` and a public `Dialog` presentation on Desktop; Dashboard uses a native dialog adapter. No private selector/portal target.

- [ ] Add failing both-emitted-client tests using the shared helper. Extend `mount` options with a strict `overrideApi(route,init)` hook; unmatched routes must throw instead of pretending every read is an item page.

```javascript
for(const target of ['desktop','dashboard']) test(`${target}: failed Save retains notes and uploaded asset ids`,async()=>{
  const app=await mount(target,{overrideApi:(route,init)=>{
    if(route==='/items'&&init?.method==='POST')throw Error('synthetic network failure');
  }});
  try{
    await click(button(app,'Add'),app);
    await typeField(app,'Bookmark URL','https://example.org/new');
    await typeField(app,'Personal notes','Keep this note');
    await app.uploadImage('Attachment images','tests/fixtures/tiny.png');
    await click(button(app,'Save'),app);
    assert.equal(app.field('Personal notes').value,'Keep this note');
    assert.equal(app.uploadedAssociations().length,1);
    assert.match(app.element.querySelector('[role="alert"]').textContent,/uncertain|verify/i);
    assert.equal(app.apiCalls.filter(c=>c.route==='/items'&&c.init?.method==='POST').length,1);
  }finally{await app.close();}
});
```

`app.field`, `app.uploadImage` and `app.uploadedAssociations` are helper methods added here: label-based real DOM lookup, dispatch a synthetic `File` through the file input using bytes from the fixture, and return rendered owned-asset IDs. They may not fabricate a saved result; the API double must return the fixture upload only when that route is actually called.

- [ ] Run `rtk proxy node --test tests/test_library_form.cjs tests/test_library_detail.cjs`. Add tests for all fields/default collection, conditional Link/Image, strict primary asset requirement, duplicate outcomes, dirty Escape/backdrop/Cancel/keep/discard, disabled double-save, successful Save focus return, revision conflict with no draft overwrite, stale upload response after closing/reopening a different draft, late save refreshing the current query and connection/profile remount isolation. Cover safe Markdown and authenticated missing-image fallbacks. Verify no model/prompt calls on opening/previewing detail.
- [ ] Implement a form state machine `editing -> uploading/saving -> editing|conflict|uncertain|saved`. A known validation rejection stays editing. A transport failure after submission becomes uncertain and exposes Verify save; lookup `/captures/{operation_key}` first. A confirmed not_found allows an explicit retry using that same key; a found receipt recovers success/duplicate outcome. Changed payload uses a new key only after the previous outcome is resolved. Track upload ownership by immutable draft ID plus generation; late results can update only that draft, not whichever dialog is now visible. Do not auto-delete files on discard. Duplicate receipts keep staged user fields and offer Open existing/Edit existing rather than silently applying them.

```javascript
const operation={draftId:draft.id,scope,payload,key:draft.operationKey};
// Every async continuation compares immutable operation/draft ownership before UI writes.
// Request payloads include asset IDs, not File bytes or local browser URLs.
```

Use public Desktop Dialog exports (verified from the target SDK), with a small adapter so the product form is shared. Implement Dashboard `<dialog>.showModal()/close()` with return focus, labels and scoped styles. Escape/backdrop/Cancel call one dirty-close handler. A dirty prompt stays within the same dialog instead of opening stacked competing modals. Use a narrow-width sheet layout with internal scroll and reachable footer. Keep note text in scoped memory only; route-scoped module maps preserve the draft across a profile remount in the same library but never across backend identity. Declare reload/exit limits honestly.

- [ ] Run full Node tests/build/syntax checks and Python API regressions. Replace the old inline URL/image capture tests with equivalent dialog tests retaining failed-input, duplicate-guard and current-search-refresh assertions. Do not count a synthetic dialog shim as actual browser focus acceptance; Task 8 verifies that.
- [ ] Update status/evidence and commit: `rtk git commit -m "feat: add safe bookmark capture edit and detail dialogs"`.

## Task 7: Library-first navigation, cards, tags and pagination

**Files:** Create `ui/library-navigation.js`, `ui/library-items.js`, `tests/test_library_navigation.cjs`, `tests/test_library_items.cjs`; modify `ui/library.js`, `ui/library-state.js`, `ui/chat-panel.js`, `ui/library.css`, `ui/chat.css`, `scripts/build-ui.cjs`; rebuild both bundles.

**Consumes:** All earlier tasks. **Produces:** `createLibraryNavigation(React,adapter,components)` and `createLibraryItems(React,adapter,components)`; the library composes toolbar/navigation/items/detail/form rather than duplicating query ownership. Query state is `{query,view,collectionId,tags,limit,offset,mode,selectedIds,scroll}`. Defaults are empty query, all view, no collection/tags, limit 50/offset 0, grid, no selection.

`LibraryNavigation` props are `{ctx,scope,libraryId,query,onQueryChange,onAskCollection,onChanged}`. `LibraryItems` props are `{ctx,scope,libraryId,page,query,onQueryChange,onOpen,onAsk,onUpdate,selection,onSelectionChange}`. Every async publication checks that immutable scope/library owner before updating presentation.

- [ ] Write a both-client test for organization filters and safe delayed updates.

```javascript
for(const target of ['desktop','dashboard']) test(`${target}: changing filters preserves the hidden chat draft`,async()=>{
  const app=await mount(target);
  try{
    await click(button(app,'Chat'),app);
    await typeField(app,'Message Hermes','An unsent question');
    await click(button(app,'Close chat'),app);
    await app.chooseCollection('Engineering / AI');
    await app.chooseTag('Reading');
    assert.match(app.lastItemQuery(),/collection_id=/);
    assert.equal(new URLSearchParams(app.lastItemQuery()).getAll('tag').length,1);
    await click(button(app,'Chat'),app);
    assert.equal(app.field('Message Hermes').value,'An unsent question');
    assert.equal(app.calls.filter(call=>call.method==='prompt.submit').length,0);
  }finally{await app.close();}
});
```

The helper's `chooseCollection`, `chooseTag` and `lastItemQuery` click real rendered controls and inspect actual adapter calls; they do not inject state. `lastItemQuery()` returns only the query substring after `?`. Modal forms keep background navigation inert; do not claim a programmatically dispatched click on an inert background element is a physically possible user interaction. Any in-form navigation or close action that would discard a draft uses the Task 6 dirty-close guard.

- [ ] Run `rtk proxy node --test tests/test_library_navigation.cjs tests/test_library_items.cjs`. Add cases for nested create/rename/move/delete via real form payloads, paged collections/tags/items beyond 50, ALL/Inbox/Favorites/Read later counts, AND chips/removal, offset reset, two simultaneous stale query completions, empty-last-page correction, view/selection/scroll retention, long titles, missing covers/images and library identity independent from chat configuration. Test select item/selection/collection Ask with visible max-20 context and no prompt submission. Favorite/read-later use guarded item updates; conflict notices do not lie about saved state.
- [ ] Implement one query owner with monotonic generation and immutable scope checks. Current-view refresh reads latest query state, not the request's captured filter. Collection operations invalidate navigation/counts/current page and guard against stale tree responses. Tag list counts are independent of current text query; results/header count reflect all active filters. Build repeated `tag` query params intentionally. UI preferences validate enum/type/bounds; private drafts remain memory-only. Paginated path data makes each nested match navigable without fetching the entire tree.

```javascript
const params=new URLSearchParams({query:state.query,view:state.view,
  limit:String(state.limit),offset:String(state.offset)});
if(state.collectionId) params.set('collection_id',state.collectionId);
for(const tag of state.tags) params.append('tag',tag);
```

Use `ResizeObserver` or CSS container queries against the plugin workspace, not only viewport media queries. At narrow width, show navigation drawer, one library/chat view and form sheet. At wide width, use the optional right panel and expand the library when closed. Hidden controls cannot receive focus; a container resize must not dispose a chat controller or form. Quiet source/date text, readable summaries and real processing status remain visible in cards/list; primary image covers use only owned authenticated previews and bounded lazy thumbnail loads. No automatic third-party image requests. Remove promotional/placeholder capture UI once the working form replaces it.

- [ ] Run full Node and Python suites plus deterministic bundle/syntax checks. Verify all prior stale-decision/reconnect/history/model tests still run. Review source inventory to ensure the split did not create unowned timers/listeners or duplicate query/transport ownership.
- [ ] Update docs/status and commit: `rtk git commit -m "feat: add library navigation grid and tag organization"`.

## Task 8: Actual-host/browser acceptance and final revision review

**Files:** Create `scripts/library_workspace_smoke.py`, `scripts/library_workspace_browser.cjs`, `docs/verification/library-first-workspace.md`, `docs/verification/library-first-workspace.json`; update README/STATUS/ROADMAP and save sanitized real screenshots under `docs/verification/screenshots/`. Keep disposable auth/server logs outside the public repo.

**Consumes:** The actual emitted bundles, real shared backend service and existing public host interfaces. **Produces:** a requirement-by-requirement evidence matrix and an honestly labeled revision result, not an implied v1 release.

- [ ] Add failing real-ASGI integration and browser checks before making acceptance-only fixes. The smoke script accepts explicit origin/token-file and an explicit synthetic-write flag; reject redirects and nonselected origins. It captures an operation key, creates a collection/link/image, edits notes/tags, verifies search/counts/native parity and reads exact IDs after reopening/restart of the disposable host only. Missing/invalid credentials must fail authenticated GET and POST. It never accesses real bookmarks or provider credentials.

```python
# Core smoke assertions after authenticated synthetic writes:
assert created['result']['notes']=='Synthetic note'
assert fetched['result']['id']==created['result']['id']
assert fetched['result']['attachments'][0]['asset_id']==uploaded_id
assert search['result']['total']==1
assert stale_update.status_code==409
assert receipt['result']['receipt']['item_id']==created['result']['id']
```

- [ ] Browser automation must exercise actual emitted Desktop/dashboard UI rather than a fabricated screenshot. Use a disposable Hermes home with enrichment disabled and a separately owned loopback process. Run wide/narrow/resized-container cases in both host themes, create/edit/reopen with notes/images, filter/tag/page, dirty-close/focus containment/return, theme changes, grid/list/selection, collapse during a real or explicitly simulated stream, collapsed pending/uncertain status and exact-request approval rejection. A synthetic stream double is labeled protocol evidence; it cannot claim provider success. Capture page/console errors and horizontal overflow. Inject no fake provider response into a real-host success claim.
- [ ] Run final stable-tree gates with outputs saved in scratch and summarized in evidence:

```sh
rtk proxy python -W error -m unittest discover -s tests -q
rtk proxy npm test
rtk proxy node scripts/build-ui.cjs --check
rtk proxy node --check desktop/plugin.js
rtk git diff --check
```

Resolve the existing isolated CPython 3.11 test interpreter from the previous verification directory before running that same Python suite there; do not guess an executable or mutate Hermes's managed environment. Rerun official plugin validation in a disposable HOME/HERMES_HOME with the public CLI and sanitized output, preserving disclosed scanner warnings. Fingerprint tracked/nonignored source before/after the gates to detect changes during verification. Source/generated bundles must agree.

- [ ] Commission one final read-only independent review from the revision's actual implementation base to verified head, with separate quality/security and spec verdicts. Focus on real regressions and acceptance omissions. The earlier Task 4 boundary review and historical M1/chat reviews are consumed, not restarted. Fix proven Important/Critical findings in one RED→GREEN pass and rerun the complete gate. Update the evidence matrix with actual counts/versions/results and all skipped runtime checks; do not turn an author's fix pass into independent approval.
- [ ] Commit the finished revision and documentation. Re-read draft PR #1 and remote head before an authorized development-branch push; update the same PR, then verify its exact published head, expected push/PR CI events and all jobs. Do not merge or mark release-ready while connected Electron/provider/OAuth/independent-machine gates remain open. Keep worktree for follow-up; stop only after all revision acceptance rows are either verified or identified as a concrete external blocker, never merely because the task checklist ended.

## Spec coverage and execution gate

| Design requirement | Owning task |
| --- | --- |
| Library first, lazy chat, status/Stop, no remount/replay | 1; regression acceptance 8 |
| Schema preservation/shared root/relational integrity | 2; boundary review 4 |
| Collections, cycles/depth/counts/deletion; tags/query paging | 3 and 7 |
| Revision-aware notes/metadata, image records/associations, receipts | 4 and 6 |
| Manual/generated/removal state and lease/generation safety | 4; real SQLite adversarial tests |
| API/native tool parity, limits/auth/structured conflicts | 5 and 8 |
| Add/Edit/detail, dirty close, drafts and uncertain writes | 6; browser acceptance 8 |
| Grid/list, filters, selection, themes/container/mobile | 7 and 8 |
| Remaining v1 features and host/provider acceptance stay explicit | Documentation in every task and final evidence 8 |

Self-review: every public operation is defined in the shared-contract block; nested limits and response shapes are explicit; each Review Focus condition has an owner test; every new helper in a snippet is defined in its task; no new dependency/framework or unsupported inference path is required.

Next gate: owner reviews this written plan. The already chosen hybrid execution method remains; do not ask the owner to choose it again. Product changes start after that review, with Task 1's failing interaction tests. This file itself is planning, not completed implementation.
