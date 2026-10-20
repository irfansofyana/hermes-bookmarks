# Task 2 — durable shared library service

Checked 2026-10-20. **Service-only local verification; awaiting independent Task 2 review.** This is not native-tool/UI integration, host shared-root resolution, enrichment, or M1 acceptance. The existing status command/API remain read-only and continue reporting the unintegrated foundation preview.

## Implemented contract

- `from bookmarks.service import BookmarkService`; construction requires a caller-selected, absolute `pathlib.Path`. `None`, strings, relative paths, inaccessible roots, and unusable path values produce a typed `ConfigurationError`. No HOME/profile/current-directory default and no import-time database creation.
- Construction creates/migrates `<data_root>/bookmarks.sqlite3`. No host storage helpers or active-library paths are imported or inferred. The host must still bind an installation-owned shared root and enforce access policy before deployment.
- `save_link(url, title='')` returns a durable item containing `id` (UUID), original `url`, `title`, `revision`, `enrichment_status`. New items have revision `1` and status `not_started`: no job has been scheduled or AI completed. Duplicate saves return the existing record, including its unchanged title/revision/status.
- Identity is **exact string equality**, backed by a binary-collated unique URL constraint. Query strings/order, fragments, scheme/host case, explicit ports and percent encodings are not stripped or normalized. Equivalent spellings may intentionally remain separate records.
- URL syntax supports HTTP(S), DNS/IDNA names, IPv6 literals, ports and Unicode paths. Reject credentials/userinfo, raw whitespace/control/format/surrogate characters, unsafe unescaped ASCII, malformed escapes, encoded ASCII controls, malformed authorities and unsupported schemes. This conservative policy also rejects percent-encoded hostnames and scoped IPv6 literals. Local/private destinations are accepted syntactically; **acceptance does not authorize fetching**. No network, DNS or inference operation exists in this service. Future fetch code must separately enforce SSRF/redirect limits.
- `get(item_id)` reads persisted data without mutation; missing IDs produce `NotFoundError`.
- `search(query, limit=50, offset=0)` returns `items`, `total`, `limit`, `offset`. Whitespace-only query lists all items. Limit must be an integer 1–100; offset a nonnegative integer; bools are rejected. Arbitrarily large valid offsets return an empty page without SQLite integer overflow.
- Search indexes title and URL through SQLite FTS5 `unicode61`. Nonempty input is one quoted literal **token phrase**, not raw FTS syntax or substring matching: punctuation is tokenized; boolean operators, column selectors and prefixes are not executed. Embedded quotes are escaped. Page order is ascending persisted insertion rowid, not relevance. Count and page share one read transaction/snapshot.
- `BookmarkError` subclasses expose static safe `code`/`message` strings: `configuration_error`, `invalid_argument`, `invalid_url`, `not_found`, `storage_error`. Raw URLs, SQL errors and database paths are not returned as messages.

## Storage and migrations

`storage.py` owns short-lived connections closed on every path. `BEGIN IMMEDIATE` serializes schema changes and saves; SQLite waits up to five seconds for ordinary lock contention. Saves use bound SQL values and `ON CONFLICT(url) DO NOTHING`, followed by the existing/new row selection in the same transaction. Commit completes before a response reaches the caller. Reads use an explicit snapshot transaction. There are no workers, global connections, hidden profiles or test-only production hooks.

Migration 1 creates items; migration 2 adds an external-content FTS5 index, insert/update/delete triggers and a rebuild for existing rows. All pending steps and `PRAGMA user_version` changes are one transaction; `executescript` is deliberately avoided because it implicitly commits. Existing IDs, revisions and content survive the frozen schema-1 upgrade fixture. Unsupported newer schema versions are rejected without downgrade. SQLite compiled with FTS5 is required; no unindexed fallback is claimed. Default local SQLite durability/journaling is retained; network-filesystem and power-loss fault injection were not exercised.

## RED → GREEN evidence

Before implementation:

```text
$ rtk proxy python -m unittest discover -s tests -p 'test_service.py' -v
ModuleNotFoundError: No module named 'bookmarks'
Ran 1 test
FAILED (errors=1)
exit 1 — expected missing-feature RED, not a dependency to install

$ rtk proxy python -m unittest discover -s tests -p 'test_storage.py' -v
ModuleNotFoundError: No module named 'bookmarks'
Ran 1 test
FAILED (errors=1)
exit 1 — expected missing-feature RED
```

The full synthetic contract tests were written and rerun RED before production modules. Self-review then added two narrower regressions **before their fixes**: unsafe ASCII URL characters were accepted (nine assertion failures including the resulting saved-item count); an embedded-NUL root leaked a raw `ValueError` instead of `ConfigurationError`. Both were reproduced, fixed and rerun GREEN.

Final exercised commands/results:

| Command | Actual result |
| --- | --- |
| `rtk proxy python -W error -m unittest discover -s tests -p 'test_s*.py' -v` | 27 service/storage tests passed, exit 0 |
| `rtk proxy python -m unittest discover -s tests -v` and the same suite with `-W error` | 33 tests passed on each run, exit 0; CPython 3.14.7, SQLite 3.53.1 |
| `rtk proxy <scratch-CPython-3.11-harness>/bin/python -B -W error -m unittest discover -s tests -v` | 33 tests passed, exit 0; CPython 3.11.14, SQLite 3.50.4 |
| `rtk proxy node --test tests/test_preview.cjs` | 1 test passed, exit 0; Node 24.18.0 |
| Ten separate repetitions of `rtk proxy python -W error -m unittest discover -s tests -p test_storage.py -k two_concurrent_processes -v` | 10/10 passed; each races two spawned processes through cold-root migration and duplicate save |
| `rtk git diff --check` and staged equivalent | Checked before commit; exit 0 |

All temporary libraries/fixtures honor the configured `TMPDIR` scratch root. Tests exercise actual SQLite: reopen, independent roots, two live service instances, schema upgrade/rollback/newer-version refusal, atomic failed saves, FTS updates/deletes, Unicode, exact URL identities, malformed inputs, literal FTS/SQL punctuation, paging and duplicate process races. Parent reads after both spawned writers exit establish persistence across process lifetimes; both writers must return the identical winning record and only one indexed item may remain.

The initial 25-test assertion pass was **not warning-clean**: test fixtures used SQLite connection context managers without closing the connections. A local probe confirmed those contexts only commit/rollback. Fixtures now use `contextlib.closing` plus the transaction context; final 3.14 `-W error` output is clean. One initial 3.11 whole-suite run printed an existing async-router test's nonfatal 0.104-second slow-callback diagnostic; it passed, and the full output is retained in the coordination report. No warning was suppressed.

Full command/stdout/stderr/exit-code transcripts, including intermediate diagnostics, are in the local gitignored `.superpowers/sdd/2026-10-20-m1-native-foundation/task-2-report.md`. This committed file is the durable concise evidence.

## Boundaries and remaining concerns

- Task 1 was independently approved with two nonblocking minors (composer-getter evidence wording; temporary test-package child cleanup). Those remain for their appropriate later task; this change does not silently fix or dismiss them.
- Task 2 has been self-reviewed only. No independent review or milestone completion is asserted.
- Host shared-root selection, native tools/HTTP/UI adapters, real host authorization, Desktop/Dashboard handoff, lifecycle/service ownership, library inference route, jobs, images and remote transport remain unresolved/unimplemented under their existing gates in `compatibility.md` and `STATUS.md`.
- This is a trusted backend-local service, not an authorization boundary. An explicit root is not proof of an installation-wide binding or cross-backend synchronization.
- Five-second lock timeout produces a safe storage error under prolonged contention; no custom retry/background loop is added. Local SQLite concurrency tests do not certify remote/network filesystem locking.
- No active installation, plugin enable, service restart, paid inference, personal bookmark/vault access, network inference, push, merge, release, or remote CI run was performed. Official host validator/doctor checks from Task 1 were not rerun: this task changes no host integration.
