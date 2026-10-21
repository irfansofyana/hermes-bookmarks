# Library-first backend checkpoint

Date: 2026-10-21. Scope: Tasks 2–5 of the approved library-first workspace plan. This is implementation/unit/in-process ASGI evidence, not deployed-host, successful-provider, or release acceptance.

## Delivered interfaces

- Forward schema 5 to 6 migration with populated/concurrent/rollback coverage and connection-local foreign-key enforcement.
- Nested collections, normalized tag identities and provenance, descendant/AND filtering, pagination, and whole-library counts.
- Revision-checked metadata and Markdown notes, owned image items and attachment associations, operation-key capture receipts, generation/active-job fencing and manual-field protection during enrichment.
- Fifteen strict native tools and matching plugin HTTP operations, retaining the legacy Item result shape. Unknown fields, duplicate JSON keys, scalar query ambiguity, streamed metadata bounds and safe conflict details have direct tests.

## Actual execution

The backend implementer supplied a RED/GREEN execution record and a 95-test focused pass. Its full 144-test run had one remaining failure, `test_package.PackageTests.test_manifests_match_the_preview_package`, because the parent-owned manifest still listed five tools. The controller independently reproduced that exact failure, expanded the ordered manifest to match `native_tools.SPECS`, then executed:

```sh
rtk proxy python -W error -m unittest discover -s tests -q
rtk proxy npm test
rtk proxy git diff --check
rtk proxy python -c "import native_tools; print('Native tool count:', len(native_tools.SPECS))"
```

Observed: **144 Python tests passed on CPython 3.14.7; 78 Node tests passed; whitespace passed; native tool count was 15**. The existing nonfatal asyncio slow-callback diagnostics remain visible. CPython 3.11, official isolated validation, stable final fingerprints, authenticated actual-host/browser probes and independent review belong to the integrated final gate and are not claimed here.

## Decisions carried forward

- Standalone image processing reports `not_configured`; capture creates no extraction job and never invents a URL. Vision remains roadmapped.
- Retry/status returns the current Item alongside its immutable accepted-revision/outcome Receipt. An immutable copy of notes/item fields is not stored as receipt history; this avoids introducing a new retention policy.
- Association-local `item_tags.label` preserves original per-item spelling while the shared normalized identity provides matching/counts. The extra schema column does not alter the public contract.
- The two read-only native operations are named `bookmark_library_identity` and `bookmark_counts`; HTTP remains `GET /library/identity` and `GET /counts`.

Independent boundary review is still required. The implementer's self-review and the controller's green rerun are not independent approval. No active installation, production restart, provider inference, migration of personal content, merge or release occurred.
