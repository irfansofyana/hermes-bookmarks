# Library-first backend review fix

The original [independent boundary review](library-first-backend-review.md) is preserved byte-for-byte. It reviewed `e3cbfc90f0db21b1238023962a6e9a308972b8f4..4fc4bab6766135bbdbef4561e28caf3328a9a56b` and returned **quality/security FAIL and backend-spec FAIL**, with one Important finding B1 and no Critical findings. These verdicts describe that snapshot; the author fix below is not independent re-approval.

## B1: normalized legacy aliases blocked migration

Confirmed. The old public queue writer accepted `["AI","ai"]`, `["Café","Cafe\u0301"]` and `["reading"," reading "]`. The new migration rejected the entire library. Rollback preserved data, but could not make the new backend open it.

Added `test_baseline_accepted_aliases_preserve_original_labels_and_normalize_membership`, changed populated concurrent-migrator coverage to contain all three alias families, and replaced the erroneous alias-as-corruption assertion with a genuinely invalid Unicode rollback case. Before the fix, migration tests ran seven cases with three alias subtest errors and one concurrent-migrator failure. After the fix, all seven passed.

The migration now admits valid aliases, retains the complete original `items.tags` JSON and its ordering, and inserts one normalized association using the first original spelling. Counts/filtering use that single identity. Metadata-only note edits and reopen preserve the original labels; explicit normalized tag removal suppresses the whole identity. No new schema column, snapshot retention store or private migration escape hatch was added. Invalid JSON/Unicode and failed-DDL rollback coverage remains.

**Ruling:** preserve historical tag spellings in the existing serialized tag cache, and use the first spelling as the normalized membership's display label. An explicit later tag edit or generated tag replacement rebuilds that cache under the current identity rules. This satisfies opening/read preservation while avoiding a second alias-history system. Cost if wrong: callers expecting duplicate spellings to remain separate editable identities must adapt; the new product identity is intentionally NFC/trim/casefold.

An additional disposable probe ran the actual pinned baseline `BookmarkService` and `JobQueue.complete` in one interpreter, then reopened each resulting SQLite library using the fixed current public service in a separate interpreter. All three cases opened, retained their original label arrays, and counted one normalized membership. The regression fixtures are therefore grounded in actual old-writer output rather than invented invalid rows.

## Actual verification

- Focused migration suite: **7 passed** after observed RED.
- Stable fingerprinted full gate after the fix: **147 Python tests passed on CPython 3.14.7 and 3.11.14; 86 Node tests passed**. Deterministic bundles, Desktop ESM syntax and whitespace passed.
- Before/after fingerprint: `b6d05ab0688d4099f656c7748fa1e74fb23a8cb1240bdcb1bf7e132a2a77d401`. This records the working-tree fix over parent head `d26a7bb`, not a claim that the reviewed old commit changed.
- Original review SHA-256: `a23852081fa00806d6274f372e3692e3747da0b713808b3fcad2a20b0b341803`.

No source-user data, active installation, production restart, inference or merge/release occurred. Final integrated revision review is still pending separately. No second boundary review is requested.
