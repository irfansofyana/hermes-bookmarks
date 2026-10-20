# M1 native foundation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a development-only vertical slice that saves and finds bookmarks from native tools and both host interfaces, hands context to native chat, and exercises persistent enrichment and image transport.

**Architecture:** A small Python domain service owns a shared SQLite library and durable jobs. Native tool and authenticated HTTP adapters call that service. Shared UI source emits host-specific entrypoints; actual chat stays entirely host-owned. Discover public host integration capabilities inside the first task and stop only affected work when a contract is unavailable.

**Tech stack:** Python standard-library SQLite and unittest for the domain, the host's documented Python plugin API and HTTP stack for adapters, JavaScript/React through each host's public SDK, Node test runner for emitted bundles. Pin additional security/image dependencies only after checking the host environment and compatibility. No standalone app server or chat runtime.

**Spec:** `docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md`

## Global constraints

- One shared library per Hermes backend installation is the v1 default and only library mode.
- Native Hermes chat integration is required.
- Do not modify Hermes core, fork its chat implementation, import private modules, monkey-patch host behavior, or reach into host DOM/React internals.
- Individual saves default to automatic tagging and summarization.
- Bulk imports default to no enrichment and require explicit opt-in.
- Images embedded in notes are not automatically sent for AI analysis.
- Follow the active host theme by default, independently on each client.
- No paid inference, active-plugin install, production restart, real user data migration, merge, or release without explicit action-specific approval.
- This is a partial milestone. Full release requirements remain mapped in `docs/ROADMAP.md`.

## Review focus

1. Two profile processes target the same data directory: one logical record and one active job claim; test in Tasks 2 and 5.
2. Chat focus changes or an existing draft is nonempty: never send to an unrelated session or overwrite it; test in Task 4.
3. Worker dies after claiming a job: lease recovery permits retry, stale results cannot overwrite newer edits; test in Task 5.
4. Untrusted files or URLs resemble supported inputs: reject executable uploads, traversal, invalid schemes, and unauthorized paths; test in Tasks 2 and 6.
5. Both emitted bundles are valid but one uses an unavailable SDK: fail clearly per host and record real-host status separately; test in Tasks 1, 3, and 4.

## Proposed file boundaries

```text
__init__.py                         plugin lifecycle and registration only
plugin.yaml                        documented capabilities/dependencies
bookmarks/__init__.py              package marker
bookmarks/errors.py                typed domain errors
bookmarks/storage.py               SQLite migrations and transactions
bookmarks/service.py               save/get/search boundary
bookmarks/jobs.py                  enqueue, claim, lease and completion
bookmarks/enrichment.py            validated input/output and apply rules
bookmarks/assets.py                approved upload/reference boundary
host_bindings.py                   verified public host APIs and lifecycle
native_tools.py                    schema/handler adapters
dashboard/manifest.json            Dashboard registration
dashboard/plugin_api.py            authenticated HTTP adapter
ui/library.js                      shared minimal library component factory
ui/library.css                     scoped semantic-token styles
scripts/build-ui.cjs                deterministic separate host outputs
scripts/host_smoke.py               opt-in actual-host checks
desktop/plugin.js                  generated Desktop ESM
dashboard/dist/index.js            generated Dashboard delivery
tests/                             unit/integration/emitted-bundle tests
docs/verification/                 compatibility and smoke evidence
```

Paths are relative to repository root. Do not create empty modules just to match this map; introduce a file with the task that owns working behavior. Host-specific function names below are adapter contracts owned by this plugin, not claims that Hermes exports matching names.

### Task 1: Pin public host contracts and establish the package lane

**Files:** Create `docs/verification/compatibility.md`, `host_bindings.py`, `tests/test_host_bindings.py`, `plugin.yaml`, `__init__.py`, `dashboard/manifest.json`, `dashboard/plugin_api.py`, `.github/workflows/tests.yml`.

**Consumes:** Official documentation index and relevant plugin/SDK documentation, exact backend/Desktop versions, and a recorded SHA of `irfansofyana/hermes-blogwatcher`.

**Produces:** Plugin-owned `describe_capabilities() -> dict[str, bool]`; package registration delegates to focused adapters. Compatibility table records public symbol/route, source locator, version, evidence level, and fallback for native navigation/context, inference/vision, storage root selection, lifecycle, attachments, and authorization on each host.

- [ ] Read the relevant official docs/source sections, inspect working reference manifests/build/registration/bridge, and record exact revisions. Inspect only nonsecret system metadata. Do not clone private runtime configuration into the public repo. Check available isolated host runners before installing dependencies.
- [ ] Write a capability-test failure first:

```python
import unittest
from host_bindings import describe_capabilities

class CapabilityTests(unittest.TestCase):
    def test_unknown_host_fails_closed(self):
        caps = describe_capabilities()
        self.assertIs(caps.get('custom_chat'), False)
        self.assertIn('native_chat_handoff', caps)
        self.assertTrue(all(type(v) is bool for v in caps.values()))
```

- [ ] Run `rtk proxy python -m unittest discover -s tests -p test_host_bindings.py -v`; record the import failure. Implement capability detection from verified public surfaces, not hardcoded successful detection. An unmounted/unknown host reports unsupported. Add tests using public-shape host doubles, including a missing export.
- [ ] Create the minimal package using verified manifest and registration syntax. Keep all routes read-only until the service task adds writes. Register a health response identifying this as a foundation preview. Do not copy a dependency list or minimum version without validation.
- [ ] Run the same test to PASS; run the official validator using the command documented for the installed version. Record errors rather than removing required features to get a green result. Establish CI with equivalent Python/Node checks as each suite is added; use no credentials for unit tests.
- [ ] Commit `chore: establish documented Hermes plugin boundaries`; update STATUS with exact evidence and unsupported capabilities. Missing direct embedding is acceptable if supported native handoff exists. No supported handoff on a target is a blocker to that target's acceptance.

### Task 2: Durable shared save/get/search service

**Files:** Create `bookmarks/{__init__,errors,storage,service}.py`, `tests/test_service.py`, `tests/test_storage.py`.

**Consumes:** Explicit `data_root: pathlib.Path` selected by verified host binding. Root is installation-owned, independent of selected profile; an unresolved root produces a configuration error.

**Produces:** `BookmarkService(data_root)`, `save_link(url: str, title: str = '') -> dict`, `get(item_id: str) -> dict`, `search(query: str, limit: int = 50, offset: int = 0) -> dict`. Item contains `id`, `url`, `title`, `revision`, `enrichment_status`. Search returns `items`, `total`, `limit`, `offset`. Duplicate saves return the same ID without overwriting title. Empty query lists items. Limit is 1–100, offset nonnegative. Typed errors carry `code` and safe `message`.

- [ ] Add failing tests, including:

```python
import tempfile, unittest
from pathlib import Path
from bookmarks.service import BookmarkService

class ServiceTests(unittest.TestCase):
    def test_two_instances_share_saved_item(self):
        with tempfile.TemporaryDirectory() as d:
            a = BookmarkService(Path(d))
            b = BookmarkService(Path(d))
            first = a.save_link('https://example.org/a?version=1', 'First')
            second = b.save_link('https://example.org/a?version=1', 'Replacement')
            self.assertEqual(first['id'], second['id'])
            self.assertEqual(b.get(first['id'])['title'], 'First')
            self.assertEqual(b.search('First')['total'], 1)
```

- [ ] Run `rtk proxy python -m unittest discover -s tests -p 'test_service.py' -v` and record RED.
- [ ] Implement migrations, parameterized SQL, stable IDs, transactions and conservative exact URL identity. Preserve query strings/fragments; accept only valid HTTP(S) URLs without credentials or control characters. URL syntax acceptance is not permission to fetch it. Use full-text indexing with a safe literal-query policy and deterministic pagination. Do not create a database on import or silently resolve a profile-local default.
- [ ] Add tests for reopen/restart, malformed/control-character URL, `file:`/`javascript:`, meaningful query differences, empty results, invalid pagination, SQL/FTS punctuation, Unicode title, and two concurrent process saves returning one record. Each test uses synthetic data and the configured scratch directory through `TMPDIR`.
- [ ] Run `rtk proxy python -m unittest discover -s tests -v`; record PASS, run `rtk git diff --check`, commit `feat: add durable shared bookmark service`.

### Task 3: Native tools and minimal dual-host library

**Files:** Create `native_tools.py`, `ui/library.js`, `ui/library.css`, `scripts/build-ui.cjs`, `tests/test_tools.py`, `tests/test_api.py`, `tests/test_ui.cjs`; modify registration/HTTP adapter; generate `desktop/plugin.js`, `dashboard/dist/index.js`.

**Consumes:** Task 2 service contracts. Verified host registration/HTTP authentication and SDK interfaces from Task 1.

**Produces:** Native `bookmark_save`, `bookmark_get`, `bookmark_search`; HTTP save/get/search routes in the plugin namespace; a minimal themed list with Add URL, search, item title, source, and status. Both adapter responses share the service data/error contract. Tools return structured serializable results; errors do not leak tracebacks/secrets.

- [ ] Write tool/API parity tests before implementing adapters. Instantiate the same temporary service for both, save through tool handler, then retrieve through authenticated test HTTP client and assert the identical ID/title. An unauthenticated remote request is rejected by the real host integration; do not make a plugin-local fake auth flag.
- [ ] Run `rtk proxy python -m unittest discover -s tests -p 'test_tools.py' -v` and record RED.
- [ ] Implement strict tool schemas with bounded search and explicit service injection. Wire HTTP requests to the same service. In the shared UI, retain input on failure and disable duplicate Save while pending. Use scoped CSS variables mapped by each adapter to documented tokens. Native source imports resolve only through the relevant public SDK.
- [ ] Write a failing emitted-bundle test. Example build invariant:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
test('both host deliveries contain the library and differ in loader contract', () => {
  const desktop = fs.readFileSync('desktop/plugin.js', 'utf8');
  const dashboard = fs.readFileSync('dashboard/dist/index.js', 'utf8');
  assert.match(desktop, /@hermes\/plugin-sdk/);
  assert.doesNotMatch(dashboard, /from ['"]@hermes\/plugin-sdk/);
  assert.match(desktop, /Bookmarks/);
  assert.match(dashboard, /Bookmarks/);
});
```

- [ ] Implement deterministic build and `--check`. Add actual render/interaction tests for save/search/error with public-shape host doubles. Run `rtk proxy node scripts/build-ui.cjs`, `rtk proxy node scripts/build-ui.cjs --check`, `rtk proxy node --test tests/test_ui.cjs`, and Python suite. A string check alone does not prove a UI works.
- [ ] Commit `feat: expose capture through native tools and both host UIs`; document real-host checks separately from mocks.

### Task 4: Ask Hermes through the actual native surface

**Files:** Modify `host_bindings.py`, shared UI, build adapters; create `tests/test_chat_handoff.cjs`, `docs/verification/native-chat.md`.

**Consumes:** Task 1 verified public composer/navigation/layout capabilities. Selected item ID and intended host session identity.

**Produces:** Plugin-owned async `prepareNativeChat({itemIds, sessionId, prompt}) -> {ok, reason?}` invoked from an explicit user gesture. It prepares a user-editable draft using bounded references without submitting; unsupported hosts return a visible reason. The concrete public API is recorded in compatibility.md, not invented in advance.

- [ ] Write failing adapter tests. A nonempty existing draft remains unchanged unless the user explicitly chooses append. A missing/unmounted target returns `ok: false`. A focus change between action start and completion never reroutes to the newly focused session. Selected IDs are bounded; note text/image bytes are not automatically attached.
- [ ] Run `rtk proxy node --test tests/test_chat_handoff.cjs`; record RED.
- [ ] Implement the supported native composition or handoff, with Ask Hermes in item actions. Show the chosen context/session and let the user send using native chat. Preserve library filters, scroll, and pending input. Do not use `ctx.llm` as a chat replacement or install a Markdown transcript library.
- [ ] Run tests to PASS and rebuild/check both outputs. In an approved isolated real host, demonstrate native Markdown, one bookmark tool call, stop/approval/history as available. Record missing features and actual host version. No paid turn is required without approval; a prepared draft test is not labeled proof of model execution.
- [ ] Commit `feat: hand bookmark context to native Hermes chat`; if no public handoff exists, commit the documented blocker and disable the unsupported action rather than implementing private integration.

### Task 5: Persistent first enrichment job and stable configuration route

**Files:** Create `bookmarks/jobs.py`, `bookmarks/enrichment.py`, `tests/test_jobs.py`, `tests/test_enrichment.py`; modify service and public host binding.

**Consumes:** Saved item ID/revision, explicit library model route, and verified host-owned inference and lifecycle capability. Plugin inference is distinct from native chat. Do not snapshot credentials into job payloads.

**Produces:** `JobQueue(data_root: pathlib.Path)` exposing `enqueue(item_id: str, revision: int, settings: dict) -> str`, `claim(worker_id: str, now: float, lease_seconds: int) -> dict | None`, `complete(job_id: str, worker_id: str, result: dict) -> bool`, `recover_expired(now: float) -> int`. Generation result is validated `summary: str`, `tags: list[str]`, `provider: str`, `model: str`, `coverage: str`. Apply only against the relevant revision/provenance. Jobs have stable IDs and pending/running/succeeded/failed/cancelled states.

- [ ] Add failing lease tests with deterministic clocks:

```python
# In a test fixture with an item and queue created in setUp:
def test_live_claim_is_exclusive(self):
    job_id = self.queue.enqueue(self.item_id, 1, self.settings)
    a = self.queue.claim('worker-a', now=100, lease_seconds=30)
    self.assertEqual(a['id'], job_id)
    self.assertIsNone(self.queue.claim('worker-b', now=110, lease_seconds=30))
```

- [ ] Run `rtk proxy python -m unittest discover -s tests -p 'test_jobs.py' -v` and record RED.
- [ ] Implement transactional claims/lease fencing, recovery and bounded retry. Test separate processes, expired claim recovery, rejection of stale-worker completion, cancellation before apply, revision changed after enqueue, and restart with pending work. Use explicit clocks rather than sleeps in unit tests. Define repeated-provider-call behavior honestly: exactly-once inference is not guaranteed after a crash.
- [ ] Implement one real lifecycle-bound worker through verified public APIs and a text-enrichment path. Use a registered library-owned auxiliary route if supported; do not tie settings silently to whichever profile last used chat. Extract only through a public host retrieval capability with adequate documented protections or a tested safe-fetch boundary; otherwise keep the real-fetch probe blocked. Never run an unvalidated arbitrary-URL fetch to demonstrate success.
- [ ] Test the generator through a dependency-injected fake returning labeled synthetic output, invalid JSON, timeout, empty input, and hostile instructions. Test manual-edit preservation and route stability across profile changes. Run full Python suite. Record these as fake-model tests; execute real text/vision calls only with approval. A host-model trust denial is actionable, not grounds to read auth files.
- [ ] Commit `feat: persist enrichment jobs with fenced worker ownership`; record cold-start/lifecycle evidence or exact blockers. M1 is not accepted with an unowned daemon or merely an enqueue stub.

### Task 6: One image round trip and milestone evidence

**Files:** Create `bookmarks/assets.py`, `tests/test_assets.py`, `scripts/host_smoke.py`, `docs/verification/m1.md`; modify verified HTTP/tool asset adapter and minimal UI; update README/STATUS.

**Consumes:** Explicit library root, verified authenticated upload/download transport, validated synthetic image bytes. Select a maintained decoder after checking host dependencies; pin it and document why. Do not handwrite an image parser for this milestone.

**Produces:** `store_image(content: bytes, declared_type: str) -> dict` returning stable `id`, verified `mime_type`, `size`, `width`, `height`; `get_asset(asset_id: str) -> dict` resolves only owned assets. Proposed safety defaults for this milestone: 10 MiB encoded input, 20 million decoded pixels, PNG/JPEG/WebP only. These are implementation proposals, not preexisting host defaults.

- [ ] Write failing tests for valid tiny synthetic PNG storage/reopen, declared-type mismatch, traversal asset IDs, unsupported SVG/HTML, truncated image, byte limit, decoded-pixel limit and an unauthorized read through the actual host boundary. Returned refs never expose arbitrary filesystem paths.
- [ ] Run `rtk proxy python -m unittest discover -s tests -p 'test_assets.py' -v` and record RED.
- [ ] Implement validation with the chosen decoder, bounded upload body handling, temporary-file cleanup, atomic write and ownership-checked delivery. No public unauthenticated static file mount. Test browser upload/preview via both emitted adapters; include remote-host delivery when an isolated remote topology is available.
- [ ] Run all Python/Node suites, deterministic build check, diff check, and official validator. Record exact commands, exit codes, host versions, screenshots and source commit. `scripts/host_smoke.py` must fail clearly for unavailable hosts and must not fabricate server responses. Separate skipped host and paid model checks from passing isolated tests.
- [ ] Update STATUS with completed tasks and next milestone. Commit `feat: verify image transport and foundation slice`, push the approved development branch, read back exact remote SHA, and inspect its checks. Do not claim green CI for absent jobs or a previous SHA. Open review only within approved publication scope; do not merge or release.

## Self-review and coverage

M1 owns working foundations, not final feature parity. The roadmap maps every spec section to a milestone; remaining native tools, imports/exports, rich notes, full settings, secure cleanup, and final visual quality remain explicitly assigned to M2–M5. M1 tasks define the cross-task service/queue contracts; public host symbols are deliberately discovered and recorded in Task 1, not guessed. Proposed APIs and test snippets above are implementation instructions, not output claimed to have run.

## Execution handoff

Plan review is required before product code. Recommended method: **subagent-driven**, because host integration, persistence, worker lifecycle, and asset security deserve independent task-level review. Execute dependency order 1 → 2 → 3 → 4 → 5 → 6. Do not parallelize unestablished shared contracts. A future session reads AGENTS and STATUS first, verifies current branch/worktree and task evidence, and resumes the earliest incomplete step. Create an isolated worktree at execution time through the relevant skill.
