# Backend portability review — author fix and verification

Date: October24,2026 (WIB). Original independent Codex review at `e20e0f6fa6d41fbf8aa9c14ae93048962ded88b0`: **REQUEST CHANGES, one Important defect, no Critical defect established**. [Original report](portability-backend-review.md) is preserved unchanged. Neither aborted Hermes delegate produced a verdict; the completed Codex review used its separate existing ChatGPT authentication. This is the controller's author disposition, **not independent re-approval**.

## I1: process death during asset write

Accepted. Added synthetic subprocess tests against production restore. Before the fix, a child died after flushing8 of77imagebytes to the final asset name; same-request retry raised `StorageError`, and expiry cleanup retained the claim. The RED run reproduced the error in `_restore` and observed `claims:1` instead of0. The prior test only killed the process after complete asset publication, so did not cover this boundary.

Fix commit `b3fef77`:

- Derive a distinct `.asset-part` filename from the generated restore operation ID and validated asset ID. Its durable claim is committed before writing. The stage name is refused if it predates the claim; no archive/user path is accepted.
- Write/truncate only this claim-owned temporary leaf through existing regular-file/no-symlink/single-link checks. Flush and fsync complete bytes before publication.
- Atomically hard-link complete bytes into the final asset name with **no overwrite**, then unlink the temporary name and sync the directory before content/receipt commit. A partial write can never publish partial final bytes.
- Handle death between link and unlink: accept exactly the two known names of the same regular inode, unlink the stage, validate final bytes, then continue. Unexpected extra links and symlinks fail closed.
- Lazy expiry cleanup removes only recorded operation-owned temporaries, including partial bytes, and known digest-matching unregistered final assets. Remove the durable claim only after directory synchronization. Unrelated files are not scanned or deleted; corrupt/unrecognized final files remain fail-closed rather than overwritten.

No schema migration or runtime supervisor change was needed. Original atomic content/receipt transaction, final emptiness recheck, claim ownership and cancellation drain remain intact. Publication requires a filesystem supporting hard links and directory fsync; failure is reported without a content commit. Windows/non-POSIX acceptance is not claimed.

## Verification

Six subprocess/security crash regressions passed:

1. Mid-write death: final asset absent, exactly8temporarybytes, another restore identity conflicts without changing bytes, same-request retry succeeds with exact source image bytes and notes.
2. Mid-write expiry: removes owned partial and claim, keeps an unrelated `.asset-part` file untouched; a fresh upload/request then restores the same backup.
3. Death between atomic link and stage unlink: same-request recovery succeeds, no staging leaf remains.
4. Expiry after link/before unlink: both known names and the unregistered claim are cleaned.
5. Replaced stage symlink: retry/cleanup refuse without truncating or deleting unrelated target bytes.
6. Original post-publication/pre-content-commit death: successful same-request recovery and durable exact receipt.

Full gates after the fix: **242Python tests passed on each3.11/3.14;217Node passed**, actual emitted UI bytes tested. Deterministic bundles, syntax/whitespace and official isolated validator passed (`ok:true`, matching capabilities, host-ready; known bundled Marked regex scanner cautions only). Machine-readable [final gates](portability-final-gates.json).

### Reviewer cancellation timeout

The review recorded a standalone15-second timeout without proving a cancellation defect. Controller reran the exact pinned review clone with `PYTHONPATH=.:tests` and `python -m unittest tests.test_portability_cancellation -v`: passed in0.054s. The working-tree standalone discover invocation also passed in0.054s, before and after the asset fix; both full-version suites passed. No cancellation implementation/test was changed to make this pass. The historical timeout remains in the original report; its cause was not established and is not called a confirmed product bug or silently erased.

### Real-host regression

After this fix the actual authenticated source/empty-target HTTP roundtrip was rerun: [portability-final-host.json](portability-final-host.json) compares all four items and exact owned image bytes/MIME, idempotent export/restore, immutable preview and target identity. The real Dashboard/public SDK [browser matrix](portability-browser.json) was also rerun against another empty backend: explicit generate/download/preview/confirm/restore, reload read-only request inspection, dark/light wide/narrow, no page errors. These use synthetic data, no model calls or core patches. Final target restart [readback](portability-final-restart.json) passed whole item projections, exact asset bytes/MIME, artifact digest, receipt and identity. All owned source/target/browser servers were stopped and ports36897/32963/42387/39815 verified closed in portability-process-cleanup.json. This does not establish connected packaged Electron, OAuth/remote, maximum-size payload or power-loss behavior.

## Final disposition

Backend I1 and both adapter/UI Important findings now have concrete author fixes and passing regressions. [UI disposition](portability-review-fixes.md) preserves its original changes-requested verdict and its deferred descriptive-preview minor. No new review loop or independent approval is claimed. Published code/evidence at17095208ffc300ecc027159501636e1b51d2cf89 with verified exact-head push/PR CI (portability-publication.json). PR remains open/draft/unmerged; merge/release/live deployment remain unauthorized.
