# Portability adapter/UI review — author disposition

Original independent review: [portability-final-review.md](portability-final-review.md), immutable `4f7b6fb1b04018e4844fb54e37f220058356031f`, **REQUEST CHANGES: two Important findings, no Critical defect reproduced**. Preserve that verdict; this document is author verification, not independent re-approval.

## I1 — committed generated bundles were stale

Accepted. Although controller follow-up `16129df` rebuilt the bundles and deterministic `--check` subsequently passed, the old Data test fixture built replacements in memory and could mask stale shipped bytes. Changed `tests/test_library_data.cjs` to execute the actual on-disk Desktop/Dashboard bundles; it no longer intercepts the builder's output or synthesizes replacement bundles. Existing delayed-export/discard and uncertain-upload-identity regressions now exercise shipped bytes directly. Both targets passed those four specific assertions before the I2 code fix; all Data cases subsequently passed in the full Node gate. Both outputs were regenerated from final sources and `node scripts/build-ui.cjs --check` passed.

This is a permanent test-boundary fix, not merely a claim that rebuilding once solves the fixture blind spot. CI already checks deterministic output before running the Node suite.

## I2 — authoritative failed restore was permanently locked

Accepted and reproduced RED on both actual emitted hosts: `Exact failed receipt must enable deliberate recovery`, expected enabled retry control, observed none. Implemented explicit **Retry failed restore** only after the exact retained request's read-only GET returns `state:failed`.

- Retains the original immutable preview ID, input digest and request ID; does not create a replacement restore or reset the file draft.
- Consumes retry permission before dispatch. A transport failure during a retry therefore requires another authoritative GET before any further retry.
- `not_found`, pending/admitted status, uncertain transport errors and a failed POST alone do not authorize automatic replay.
- Busy/current scope guards remain in force; closing/reopening retains the admitted tuple and selected file. Existing A→B→A same-owner refresh behavior remains covered by the shipped-bundle suite.

Tests prove no retry appears after initial uncertainty or `not_found`, an exact failed GET enables deliberate retry without a POST, close/reopen retains the draft, the retry payload equals the original, in-flight controls prevent duplicate dispatch, and success settles without a third POST. New real-storage HTTP regression injects `StorageError`, observes HTTP503, reads the failed receipt, then succeeds with the same restore operation ID and request tuple.

## Minor observations

- **M2 fixed:** a manually inspected ready export now displays filename, size and SHA-256 and offers **Download inspected export**. It downloads that exact artifact through the existing bounded/integrity-checked read lane, without selecting a different generated snapshot or making any mutation. Both emitted-client RED→GREEN tests and actual Dashboard page-reload/download verification passed.
- **M1 deferred:** restore preview still displays raw supported table counts, not a labelled image-item/Trash breakdown or explicit integrity-status wording. Successful preview does validate the archive and digest; no validation/empty-target boundary is relaxed. This is a disclosed presentation minor, not a complete descriptive-preview contract claim.
- The review's C1 export-integrity metadata gap was already controller-addressed at `16129df`; no additional independent approval is claimed.

## Actual browser recovery evidence

[portability-recovery-browser.json](portability-recovery-browser.json) comes from the real Dashboard SPA, plugin loader/public SDK, authenticated backend and emitted bundle. A new disposable HOME/HERMES_HOME/library was configured through the official command handler and read back. The test copied only a **plugin-owned content module** into that scratch installation and injected one `StorageError` before content restore. No Hermes core patch, fake HTTP response, provider call, personal data or active service change was used.

Observed sequence: upload/preview/confirm → real HTTP503 → zero active/Trash content → read-only failed receipt → no automatic retry → close/reopen → explicit same-tuple retry → three active/one trashed item. Exactly **two** restore POSTs; request bodies equal. Then Generate export, page reload, read-only saved-ID inspection and actual download with **zero mutation requests**. No page errors. Two screenshots (`screenshots/bookmarks-data-failed-recovery.png`, `bookmarks-data-recovered.png`) retain the synthetic real-host state; the failed-recovery screenshot was directly inspected.

## Combined author gates

- CPython3.14: **237 tests passed**.
- CPython3.11: **237 tests passed**, unset inherited PYTHONPATH/PYTHONHOME.
- Node: **217 tests passed**, Data tests now read actual delivered bundles.
- Deterministic build, Desktop and recovery-script syntax, committed diff whitespace: passed.
- Official isolated validator returned ok:true/host-ready/matching capabilities/no core override; only the known bundled Marked-regex scanner cautions remain. Recovery server was stopped and its port33157 verified closed (portability-process-cleanup.json).

The original backend integrity review aborted on provider-credit exhaustion and produced **no final verdict**. The resumed Hermes delegate also failed on credits. Independent local Codex subsequently completed at immutable `e20e0f6fa6d41fbf8aa9c14ae93048962ded88b0`, finding one Important mid-write asset crash/recovery flaw. It is author-fixed atb3fef77; see [backend disposition](portability-backend-review-fixes.md). Final gates242Python each/217Node pass. Both review scopes are consumed and all Important findings have author fixes; no independent re-approval is claimed. No merge/release/live deployment.
