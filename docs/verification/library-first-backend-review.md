# Independent library-first backend boundary review

## Scope and verdicts

- Reviewed commit: `4fc4bab6766135bbdbef4561e28caf3328a9a56b`.
- Comparison baseline: `e3cbfc90f0db21b1238023962a6e9a308972b8f4`.
- Scope: Python library backend, native tools, HTTP adapters, manifest and their Python tests; Tasks 2–5 of the approved library-first plan. Unchanged worker helpers were read only to trace ownership through the changed queue boundary. This is not another historical M1/chat review or the final integrated/UI review.
- **Quality/security verdict: FAIL — one Important migration compatibility defect.** No Critical defect or additional actionable injection, arbitrary-asset-path or credential-handling defect was found in this boundary. Local ASGI checks do not establish host authentication.
- **Backend-spec verdict: FAIL — valid schema-5 tag data can prevent opening the upgraded library**, contrary to the data-preserving forward-migration requirement. The other reviewed boundaries had no additional Important/Critical findings; passing tests are not a waiver of the reproduced migration failure.

No production/test files or git index were changed. Only this new review report was written in the worktree; disposable snapshots, probes and logs are under scratch. Historical consumed reviews were left untouched. No network fetch, provider call, credential access, active installation, restart, personal-library migration or external-system write was performed.

## Important finding

### B1 — Normalized aliases accepted by the previous backend make the entire library unopenable

**Location:** `bookmarks/library_schema.py:19–24`, specifically the normalized-identity cardinality check at lines 20–21. Related acceptance error: `tests/test_library_migration.py:48–57` treats `["AI","ai"]` as corrupt legacy data and asserts that the migration must fail.

**Effect:** A valid v5 item can contain differently spelled tags that normalize to the same new identity. The migration raises `StorageError` before upgrading any rows. Rollback works and leaves the database intact at version 5, but every new `Storage`/`BookmarkService` construction attempts the same failing migration. Because the root is shared, one affected item prevents library reads and writes through the new backend, not merely tag editing for that item. Ordinary generated output can produce this condition; no malformed JSON, direct SQL corruption or hostile filesystem access is necessary.

**Why this is a regression:** The exact baseline's `bookmarks/jobs.py:22–29` validates each nonempty bounded label and deduplicates only exact strings (`dict.fromkeys`). Its public queue completion therefore accepts case variants, canonically equivalent Unicode forms and leading/trailing-space variants. The new migration silently changes the definition of valid historical data to require uniqueness under NFC/trim/casefold. The approved spec requires existing tags/spelling and library availability to survive the forward migration; normalized membership needs an explicit compatibility treatment, not rejection as corruption.

**Independent reproduction:** Export both exact commits into disposable scratch directories. With the baseline production `BookmarkService` and `JobQueue`, save a synthetic link, enqueue/claim a job, then call `complete()` with one of these tag lists and valid synthetic summary/provenance. Reopen the resulting database using the reviewed production `BookmarkService`. Each case was run against a separate synthetic root:

| Baseline-produced tags | Baseline completion | Reviewed upgrade | Readback after failure |
| --- | --- | --- | --- |
| `["AI", "ai"]` | accepted | `storage_error` | version 5, original tags retained |
| `["Café", "Cafe\u0301"]` | accepted | `storage_error` | version 5, original tags retained |
| `["reading", " reading "]` | accepted | `storage_error` | version 5, original tags retained |

The combined fixture also retained its original full item rows and `PRAGMA integrity_check='ok'` after the rejected migration. This is an availability/upgrade failure, not a claim that rollback destroyed data.

Repro outline, using the baseline modules first and reviewed modules in a fresh interpreter second:

```python
# Baseline e3cbfc90..., synthetic root only:
service = BookmarkService(root)
queue = JobQueue(root)
item = service.save_link('https://example.org/alias')
job = queue.enqueue(item['id'], 1, {})
lease = queue.claim('fixture', 100, 30)
assert queue.complete(job, 'fixture', {
    'summary': 'Synthetic summary', 'tags': ['AI', 'ai'],
    'provider': 'fixture', 'model': 'fixture', 'coverage': 'extracted_text',
}, token=lease['token'], now=110)
# Reviewed 4fc4bab..., same synthetic root:
BookmarkService(root)  # raises StorageError, although the old writer accepted it
```

**Expected remedy:** Add explicit legacy-alias handling during backfill. Normalize membership without throwing away original label information or requiring users to edit/reset their database manually; choose and document how original spellings/aliases are retained when one new identity represents multiple old labels. Do not classify previously accepted normalized aliases as corrupt JSON. Replace the erroneous rejection assertion with preservation/readability coverage built from actual baseline-writer output. Retain rollback tests for genuinely invalid JSON/Unicode, failed DDL and unknown future versions, and exercise the supported alias case with concurrent migrators.

**Missing acceptance coverage:** Existing migration fixtures exercise shared identity *across* different items, but not aliases *within* one valid baseline item. The current `["AI","ai"]` rejection assertion codifies the defect instead of catching it.

## Verification and positive boundary evidence

### Stable source

To avoid concurrent parent UI work contaminating results, tests and probes used an export of the exact reviewed commit:

`/home/irfansofyana/.hermes/cache/scratch/backend-boundary-vg549fzh`

All 116 exported tracked files were hashed. The canonical path-to-SHA256 manifest fingerprint was identical before and after the full suites and remained identical on final comparison with the original export manifest:

`36d55a37ad0df62fa57a4e2b032bd0c2258a02c2f347fd818478dee6d474c996`

Baseline export:

`/home/irfansofyana/.hermes/cache/scratch/backend-baseline-gio48asd`

Its full-suite before/after fingerprint also matched:

`cc67f58d0bddc975a76b64a07fa5aacdcac0f483d8fd584510bb354db552d705`

Parent-owned source/bundle/smoke-script edits appeared in the original worktree during review; none were used as reviewed source or modified by this reviewer. Findings and line numbers above refer only to `4fc4bab...`.

### Executed checks

| Check | Actual result |
| --- | --- |
| Reviewed snapshot, CPython 3.14.7: `python -W error -m unittest discover -s tests -q` | 144 tests passed, exit 0 |
| Reviewed snapshot, existing isolated CPython 3.11.14: same suite with `-B -W error` | 144 tests passed, exit 0 |
| Baseline snapshot, CPython 3.14.7: same suite with `-B -W error` | 86 tests passed, exit 0 |
| Scoped `git diff --check e3cbfc90... 4fc4bab...` | exit 0 |
| Added-line security scan | no secret-literal, shell-execution, eval/exec or pickle matches; dynamic SQL reviewed as static/allowlisted structure with bound caller values |
| Disposable baseline-writer alias migration probes | all listed valid alias cases rejected as described in B1 |
| Disposable service/concurrency/ASGI probes | passed; details below |

All shell entrypoints were `rtk`-prefixed. Source bytecode writes were disabled in the exported trees. Existing nonfatal asyncio slow-callback diagnostics remained visible. The first 3.11 attempt inherited the runtime's 3.14 `PYTHONPATH` and failed dependency imports; removing `PYTHONPATH`/`PYTHONHOME` from the child environment corrected that harness issue, and the complete 144-test rerun passed. No dependency installation was needed.

### Boundaries exercised without additional Important/Critical findings

- **Migration/FKs:** committed tests passed for transactional DDL rollback, invalid data rollback, future version rejection, preserved IDs/rowids/URLs/summary/assets/jobs/settings/chat identity, populated concurrent migrators and foreign keys on fresh connections. Item-child cascade and asset restriction tests passed. B1 limits the overall preservation verdict.
- **Tag provenance:** tests cover normalized manual/generated identity, manual priority at the 20-tag bound, durable explicit suppression, unchanged-form provenance, FTS/cache/count agreement and original per-item spelling across shared identities. An independent real-SQLite completion-first/edit-second race returned a stale-revision conflict; explicit retry removed the normalized AI tag while preserving notes/manual tags, and discovery/filter counts agreed.
- **Queue ownership:** retained tests passed for exact active job ID plus generation, stale complete/fail/cancel/recovery, token replacement, lease expiry, post-lock clocks on complete/fail, bounded retries, repeated cancellation while draining admitted claim/completion work, and a provider double that swallows cancellation. Additional real competing-write-lock probes verified claim expiry was based on the post-lock clock and recovery saw expiry occurring during lock wait. These are local lifecycle proofs, not successful-provider acceptance.
- **Atomic edits/assets:** revision races, byte/type/Unicode bounds, unknown/source-field rejection, rollback of scalar/tag/association changes, 10-image limits including primary, restart persistence, unlink preservation and restrictive owned IDs passed. An independent HTTP update combining notes/tags with a missing asset returned 404 with no partial change.
- **Capture/receipts:** eight concurrent same-URL writers with different operation keys produced one item, one created receipt and seven duplicate receipts; winner metadata stayed unchanged. Two concurrent local-ASGI image captures had their response bodies deliberately dropped *after durable dispatch*. Read-only receipt lookup and same-key retry recovered one item and the same immutable receipt. After later note edits, retry/status returned the current Item with the original accepted revision, without creating another item.
- **Strict adapter boundary:** independent local-ASGI probes rejected boolean revisions, immutable source edits, malformed nested tags, route-identity overrides, duplicate nested keys, nonfinite JSON and repeated scalar queries with 400; over-byte-limit notes were rejected. Chunked metadata with false `Content-Length: 1` returned 413 before dispatch. Exactly 65,536 UTF-8 note bytes were accepted. The full suite also exercised strict native/API parity and the ordered fifteen-tool manifest inventory.

### Rulings assessed

The supplied rulings are consistent with the backend contracts: standalone images report `not_configured` without an extraction job; retry/status returns a current Item with an immutable Receipt rather than retaining note snapshots; association-local tag labels preserve each item's original spelling across shared identity; and the read-only native names are `bookmark_library_identity` / `bookmark_counts`. The shared explicit library root and separately profile-scoped chat boundary were not changed. None of these rulings explains or excuses B1's within-item alias rejection.

## Reproduction artifacts and remaining gate

Scratch probes:

- `/home/irfansofyana/.hermes/cache/scratch/backend-boundary-probes.py`
- `/home/irfansofyana/.hermes/cache/scratch/backend-boundary-adapter-probes.py`
- `/home/irfansofyana/.hermes/cache/scratch/backend-boundary-alias-cases.json`

Full outputs:

- `/home/irfansofyana/.hermes/cache/scratch/backend-boundary-vg549fzh-suite.log`
- `/home/irfansofyana/.hermes/cache/scratch/backend-boundary-vg549fzh-py311-clean-suite.log`
- `/home/irfansofyana/.hermes/cache/scratch/backend-baseline-gio48asd-suite.log`

Probe scripts are rerunnable with `rtk proxy python -B <absolute-probe-path>` while the pinned scratch exports remain present. They use synthetic local SQLite/ASGI data and no network/model execution.

This one new boundary review is complete. B1 needs an author-owned reproducing regression and verified fix; no code was rewritten and no independent re-approval of a future fix is implied. UI/browser, official host validation/authentication and remaining target/provider gates belong to the separate integrated acceptance/final revision review.
