# Settings and text/owned-image vision — verification

Date: 2026-10-24 WIB. **Implemented development preview, not a v1 release or live deployment.** Design and plan were explicitly approved; no further plan/workflow approval is pending. Scope is the [settings/vision plan](../superpowers/plans/2026-10-24-settings-and-vision.md), not the full rich-text/inline-image milestone.

## Result and evidence levels

- Library settings/schema11, atomic per-item requests and receipts, frozen settings/field/image/summary ownership, partial completion, public inference, seven native operations, HTTP parity, both emitted UIs and v2 backup/v1 reading are implemented.
- **321 Python tests each on CPython3.11.14 and3.14.7; 316 Node tests on24.18.0 passed.** Counts, durations, slow-callback diagnostics and delivered hashes: [gates](settings-vision-gates.json). Build equality, syntax and whitespace gates passed. Python printed nonfatal asyncio slow-callback diagnostics; not a warning-free claim.
- Actual authenticated disposable Hermes HTTP, real native registry, real Dashboard SDK/browser, exact content/settings/identity/asset-byte restart readback and official isolated capability validation passed, as detailed below. These are not direct-router doubles.
- **Real text/vision success remains UNVERIFIED.** Both synthetic-input attempts against the existing public main route returned `PluginLlmTrustError`; [provider evidence](settings-vision-provider.json). No active trust/config/installation was changed, no credentials copied/read/exported by the harness, no external SDK fallback and no fabricated response. A constructor-only public-context probe is not registered active-plugin acceptance. Actual registration is proved separately in the isolated native harness. A future approved trusted context is needed to establish model/image support and a checkable visual result. One facade call can involve host retries/fallback and costs; no plugin no-retry promise.
- Connected Electron, cross-machine remote/OAuth/payload ceilings, rich-text/inline images and full-product acceptance remain open. Dashboard and emitted Desktop tests are not substitutes.

The actual host source target was Hermes `v0.22.2`, source revision `d923a5eb487a17c0a68801bba9ef0f56c81040a8`; borrowed preprovisioned CPython3.14.7 environment, real built Dashboard and Chrome. This does not extrapolate a Hermes support floor or certify an unexercised Desktop build.

## Delivered contracts

Settings are installation-library SQLite state with CAS revisions, not chat preferences. Provider/model/options are editable; execution owner is fixed. Bootstrap preserves edits. Independent automatic fields, opt-in standalone-image bytes, language/length preferences, preferred tags, bounded nonsecret guidance, retention and pause are exposed. An incomplete route admits a terminal `configuration_required` job with zero provider attempts while preserving the save. Pausing prevents claims; accepted remote work may finish. Attachments are not automatically vision inputs.

Admission freezes settings revision, field mask, primary asset, summary revision and request tuple atomically. Reusing the exact request returns its original receipt; changed tuples conflict. Read-only status/receipt/settings calls and cancellation do not activate processing. Explicit Start/mutations can resume owned workers; lookup is not retry authorization. Per-item explicit fields are independent of automatic-field toggles. Manual/legacy summaries are excluded from automatic replacement; explicit summary edits/clears acquire protection against late completion. Applied/conflicted fields and actual attribution are reported honestly.

New tools: `bookmark_settings_get`, `bookmark_settings_update`, `bookmark_enrich`, `bookmark_enrichment_request_get`, `bookmark_enrichment_get`, `bookmark_enrichment_cancel`, `bookmark_source_clear`. `bookmark_job_*` stays import-only. Imported source, personal notes, generated summaries and retained extraction are distinct.

V2 writes preserve summary ownership/revision, <=30,000-character retained text and allowlisted canonical provenance/settings. Strict v1 validation remains unchanged and version dispatch is explicit. A real pinned old writer at `85161559263424c4bb4e0ecc66309a78043733ca` produced the committed synthetic ZIP and schema10 database; this is not hand-authored lookalike old data. Old-reader execution accepts its v1 ZIP and rejects v2. Restored settings/route stay inert, destination execution owner/identity remain unchanged and no work is restored. A full editable-field Save (excluding owner) is explicit adoption/replacement and retires both inert keys transactionally, including same-value adoption. Partial edits/bootstrap do not imply that consent.

## Actual host/native/restart checks

[Authenticated HTTP report](settings-vision-host.json):22 assertions, fresh source and target, unauthorized reads/writes rejected, strict CAS/foreign-owner rejection, independent automatic controls, manual summary ownership, durable request lookup, opt-in image admission, bounded public job projection, paused attempts0 and cancellation, v2 export/hash/chunk upload/preview/restore and inactive restored options. Two original items/one owned image were restored. Source then gained a separate synthetic imported item for the retained-body browser case.

[Native report](settings-vision-native.json): all seven new operations executed through actual `model_tools.handle_function_call` and public plugin discovery. Actual frozen v1 ZIP restored three items/one owned asset/two collections; live target settings stayed unchanged. Status/receipt/cancel/source-clear used real registered handlers. Native harness lives under `tests/host/`, never runtime modules.

Actual HTTP import: [fixture report](settings-vision-import-fixture.json). For the retained-body UI case only, the **stopped** owned server's real queue was completed with explicitly synthetic tags/body/attribution using `settings_vision_seed.py`; that is neither publisher extraction nor a provider result. The synthetic values identify themselves as not inference. Pause was restored before restart. Browser/model evidence must not be conflated.

After the review fix, both owned servers were restarted and exact full projections/settings/identity/counts and actual base64 image bytes compared:

- Source: [before](settings-vision-source-before.json), [after](settings-vision-source-after.json), three items/one asset.
- Target: [before](settings-vision-target-before.json), [after](settings-vision-target-after.json), two items/one asset.
- Original admitted settings/receipts/manual summary also survived the earlier controlled restart: [report](settings-vision-restart.json), [pre-restart capture](settings-vision-pre-restart.json).

[Official validator](settings-vision-validator.json):15 checks passed, registration and manifest tool inventory match; no core runtime rebinds and Desktop stays on public SDK. Run without `--install-deps` against preprovisioned dependencies, not a first-install/dependency-bootstrap proof. Stderr empty. Scanner returns **caution**, not clean security: `inline_shell_exec` in each bundled Markdown lexer. [Matched context](settings-vision-scanner-context.json) records the actual negative-lookahead/backtick regex fragments; those matches do not execute shell commands. Warnings remain disclosed.

Fixture setup initially omitted the public `plugins.enabled` allowlist: the real server returned404, which the harness correctly rejected. Fixed using the official config handler inside disposable homes and restarted only those owned hosts. No fake backend substituted. The earlier scratch3.11 environment had expired; a new isolated environment was created from `requirements-test.txt`. Inherited3.14 PYTHONPATH initially broke a raw3.11 probe; final3.11 execution explicitly unsets PYTHONPATH/PYTHONHOME. These failures are not counted as successful gates.

All owned servers were stopped; [cleanup](settings-vision-cleanup.json) verifies seven recorded loopback ports closed. No active installation/rescan/restart, personal library/vault migration, merge or release occurred.

## Actual Dashboard/browser matrix

[Browser manifest](screenshots/settings-vision-browser.json):13 completed rows, real Dashboard loader/SDK/controls/authenticated API, six screenshots, dark/light at1440/390, dialog and document bounds, focus containment/opener return, GET-only settings opening, real CAS conflict with retained draft and explicit reviewed revision, actual successful settings commit with only its acknowledgement aborted followed by GET-only reconciliation (one POST), dirty Escape/keep/discard, image opt-in blocking, manual-summary save, tags-only explicit request/status/cancel, cold reload/exact receipt inspection with zero POSTs, and retained-body clearing while imported source/summary/notes remain. Page errors0. Console records the deliberately caused409 and aborted acknowledgement; not a pristine-console claim.

Representative screenshots:

- [Dark settings1440](screenshots/bookmarks-ai-settings-dark-1440.png), [dark390](screenshots/bookmarks-ai-settings-dark-390.png).
- [Light settings1440](screenshots/bookmarks-ai-settings-light-1440.png), [light390](screenshots/bookmarks-ai-settings-light-390.png).
- [Detail/partial-field controls](screenshots/bookmarks-ai-detail-light-1440.png), [source removal390](screenshots/bookmarks-ai-source-cleared-light-390.png).

[Measured contrast](settings-vision-contrast.json): body and primary-button hover pass4.5 in both themes/widths; the SDK-provided small DialogDescription is2.56 in the light theme and is an explicit deferred visual minor. Main data-transfer/cost/ownership disclosures are separate normal body text. Settings beyond the first viewport scroll behind the reachable sticky footer; screenshots of the top are not full-form captures. The SDK top-right close glyph appears blank in captured pixels; Escape and labeled footer close controls were exercised successfully (deferred minor).

## Independent review and one author fix pass

Independent Codex0.163.0, explicitly `gpt-6.1-sol`, read-only detached clone reviewed `4def7bed..37e5e5ae378d9050ef0796293a696b748645c844`. [Original verdict](settings-vision-review.md): **REQUEST CHANGES, two Important, no Critical**. Source links are mechanically normalized from the original local clone to the exact reviewed public commit; verdict/finding text is unchanged. The raw CLI report remains in the local review scratch. No independent reapproval is claimed.

1. I1: inactive migrated pending jobs blocked explicit reprocessing although claims skipped them. Genuine old-writer fixture regression reproduced `ConflictError` RED. `has_active_job` now uses the same pointer/generation ownership as claims for explicit and automatic admission; inactive history is preserved, a new generation claims successfully, and a genuinely active generation still conflicts. Migration4/request26 focused tests GREEN.
2. I2: both UIs rejected migrated `settings_revision:null`. Ten emitted legacy-state cases RED; fixed nullable historical status and explicit `legacy / unknown` label. New admission receipts still require a positive safe revision; two negative cases stayed protective. All12 emitted cases GREEN.

Author fix: `c599e1e0ae7ee55c36dbe1197ee7697654c962db`. Final whole suites:321Python each3.11/3.14,316Node, zero failed/cancelled/skipped; exact delivered build check and actual-host browser/restart rerun use the fixed code. Independent reviewer couldn't run filesystem setup or React in its read-only sandbox; those are controller evidence, not independent verification.

## Rulings and costs

1. Parallelize disjoint UI/codecs after frozen contracts while controller owns backend/integration; no child commits. Cost if wrong: integration rework, covered by full gates.
2. Retain unmanaged low-level service fixture compatibility until settings become managed; runtime always uses persisted admission snapshots. Cost: constructor-contract confusion, covered by stale-cache/runtime tests.
3. Duplicate saves do not implicitly reprocess; inactive claims remain skipped. Explicit enrichment now ignores inactive history but preserves it. Cost: legacy duplicates need deliberate Enrich, and historical orphan rows can still show their stored old state when separately inspected.
4. Consolidate service/API scenarios rather than creating duplicate test files. Cost: navigation differs from plan filenames, not omitted behaviors.
5. Full editable-field Save defines explicit restored-intent adoption/replacement; partial edits/bootstrap preserve intent. Cost: API adopters must send every editable field; no source-owner transfer.
6. Incompatible historical route spellings remain v1-readable but make v2 export fail closed until valid explicit replacement. Cost: legacy intent cannot silently disappear or normalize; an explicit adoption/replacement may be needed before export.
7. Detached read-only clone plus the complete immutable scope/spec/Review Focus/rulings prompt replaced helper-package output. Cost: the reviewer sandbox could not run filesystem/React suites; controller checks are separate and no independent reapproval is claimed.
8. Task7 completes execution of the allowed acceptance **attempts and blocker recording**, not real-provider or full-target acceptance. No active trust grant was authorized as a workaround. Cost: production text/vision support remains unverified until an approved trusted context is exercised.

Deferred visual minors: light SDK description contrast2.56; SDK close glyph appears blank. Existing bulk-tag Unicode/restore-preview-description minors remain in the earlier roadmap/evidence, not silently fixed here.

## Reproduction and publication boundary

Use only prepared disposable homes and credential-free explicit loopback origins. Actual scripts refuse remote/credential-bearing origins; mutation helpers require explicit allow flags. Tokens remain private local fixture files, not arguments containing token values or public evidence.

```sh
rtk proxy python -m unittest discover -s tests -q
rtk proxy env -u PYTHONPATH -u PYTHONHOME /path/to/isolated311/bin/python -m unittest discover -s tests -q
rtk npm test
rtk proxy node scripts/build-ui.cjs --check
rtk proxy python scripts/settings_vision_smoke.py "$SOURCE_ORIGIN" "$SOURCE_TOKEN_FILE" result.json --allow-write --target-origin "$TARGET_ORIGIN" --target-token-file "$TARGET_TOKEN_FILE"
rtk proxy node scripts/settings_vision_browser.cjs "$SOURCE_ORIGIN" screenshots --allow-write
rtk proxy node scripts/settings_vision_metrics.cjs "$SOURCE_ORIGIN" contrast.json
rtk proxy python tests/host/settings_vision_readback.py "$SOURCE_ORIGIN" "$SOURCE_TOKEN_FILE" after.json --compare before.json
```

The native harness requires the real Hermes source/runtime in an isolated home. Provider probe uses the existing public configuration/facade and never grants trust. Exact pushed HEAD, Actions push/PR run IDs and individual job conclusions are recorded in the PR#1 handoff after publication; code evidence SHA above is not extrapolated to a later commit. PR remains draft/open/unmerged; merge/release/live deployment belong to the owner.
