# Independent backend integrity review

Snapshot: e20e0f6fa6d41fbf8aa9c14ae93048962ded88b0; range b5e03fc..e20e0f6.
Verdict: REQUEST CHANGES. One Important/Major finding; no Critical finding established.

## I1: Interrupted asset writes permanently block recovery

bookmarks/portability/store.py:298-304 writes directly into the final asset leaf. Process death during handle.write leaves a partial file, with an already committed portability_asset_claims row. Same-request retry recognizes the claim but rejects the partial file at line 302 instead of recovering it. Expiry cleanup at lines 108-118 skips hash-mismatching claimed files (line 116), retaining both the file and claim. Other restore request IDs then conflict with this claim. The otherwise empty target cannot restore the same backup through supported retries, including after expiration, without manual storage repair.

Fresh synthetic subprocess probe: intercepted only the exclusive asset write, wrote/flushed 8 of the expected 77 bytes, then os._exit(23). Child exit 23; target items 0. Two ordinary same-request retries each raised StorageError and reported failed. Advanced cleanup clock beyond upload expiry and invoked upload_create: partial file still present, claims count 1, items 0. No source code was changed. Repro script and literal output: probe.py and probe.log in this directory.

Suggested correction: use operation-owned temporary asset leaves with durable atomic publication, with recoverable ownership metadata for interrupted temporaries. Recover only files proven to belong to this operation; preserve refusal to overwrite unrelated files. Test mid-write termination, retry, expiry cleanup and conflicting restore operations. Directory fsync alone does not address this boundary.

## Verification

Command (shell prefixed with rtk proxy):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests TMPDIR=/tmp timeout 60s python -m unittest tests.test_portable_archive tests.test_portable_content tests.test_portability_store tests.test_portability_crash
Result: 49 tests passed in 18.956 seconds, Python 3.14.7, exit 0. Full output: focused-corrected.log.
Includes hostile archive inventories/flags/forged lengths/JSON/image limits, alias and source-provenance migration/order/search, exact logical round trips, target concurrent writer refusal, rollback and receipts, directory sync failures and post-publication child-process death recovery.

Initial invocation omitted PYTHONPATH=.:tests: 30 tests passed and content module import failed (library_fixtures unavailable). Corrected run above resolved that harness error. Initial combined run also stalled in cancellation and was interrupted. Standalone cancellation test was bounded with timeout 15s: exit 124 without a result (cancellation.log). This is unresolved verification, not a proven defect in the five scoped backend modules.

Scope read: archive.py, content.py, store.py, operations_schema.py, schema.py, migration registration, import provenance writer, item projection and search integration, focused tests and required design/status/roadmap context. No additional Important/Critical archive/domain/provenance defect established.

Limits: synthetic local filesystem/SQLite only; no power-loss simulation, full maximum-size stress, real host/UI/provider checks, Python 3.11 run or full product approval. Did not read personal data or call providers/network, install, start servers, publish or modify tracked files/index/HEAD. HEAD and clean git status verified before and after review. All review artifacts and synthetic data are under /tmp.
