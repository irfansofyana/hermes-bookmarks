# Library-first workspace verification

Date: 2026-10-21. Approved scope: the eight-task [workspace plan](../superpowers/plans/2026-10-21-library-first-workspace.md), not all remaining v1 milestones. This revision stays a development preview. No merge, release, live plugin installation or production restart is authorized or claimed.

## Implemented behavior

The library opens first with chat closed. Its toolbar opens/collapses a dedicated Hermes-backed panel without disposing an existing session, stream, context or draft. Stop remains explicit. Collections, tags, smart views, counts, grid/list cards, paging and metadata/Markdown/image dialogs use the same shared service as native tools. Opening detail, previewing notes and preparing Ask context do not submit a prompt.

Add/Edit distinguishes personal notes, description and generated summary. Expected revisions reject stale edits without partial writes. Duplicate capture keeps staged user fields rather than overwriting the existing item; operation receipts reconcile uncertain capture. Standalone image items require an owned primary asset and report visual AI as unavailable. Drafts live in module memory scoped to connection/library/item, not durable browser storage; full reload/exit does not preserve an unsaved draft.

## Evidence matrix

| Requirement | Evidence | Status |
| --- | --- | --- |
| Schema upgrade, data preservation, concurrent/failed migration, FK checks | Python migration/storage tests; backend checkpoint | Verified locally; B1 author fix verified, original review FAIL preserved |
| Collections/tags/descendant AND queries/counts | Service and strict native/ASGI tests; authenticated real-host smoke | Verified |
| Notes, revisions, receipts and image associations | Service/API tests; actual browser capture/upload/edit and exact SDK readback | Verified |
| Real SDK 400/404/409 and original-key retry | Fresh actual Dashboard/public SDK validation, receipt absence and explicit retry, concurrent edit compare/rebase | Author-verified; no fake success response |
| Unchanged tags and same-library pending drafts | Comma/quote/Unicode/alias/newline and profile-ABA/upload regressions, actual comma-tag notes edit | Author-verified; source provenance retained |
| Responsive collection drafts and refreshed loaded navigation pages | Both-loader open/pending resize and 51-row tag/collection invalidation regressions; actual Dashboard collection resize/save | Author-verified; invalidation resets page zero |
| Real native registration and shared read parity | Actual Hermes plugin manager/model tool registry read of the smoke item, counts, library identity and receipt | Verified; no inference |
| Missing/invalid auth rejected on GET and POST | Real Dashboard smoke, including after restart | Verified on loopback |
| Persistence through host restart | Owned disposable process stopped, old socket closed, new process started against same data root; original receipt/item/edited note/asset read back | Verified |
| Chat initially closed; collapse preserves work; hidden decisions and exact-session Stop | Both emitted-client/controller regressions with explicitly synthetic protocol events | Verified protocol evidence; no provider success implied |
| Ask prepares context without sending | Real Dashboard sent only capability/model-options RPCs; no session.create/prompt.submit | Verified |
| Actual Dashboard loader and shared API | Real packaged Dashboard SPA, public SDK, real native plugin/backend; no fake API/provider responses | Verified |
| Dialog dirty Escape/keep/discard, focus containment and return | Actual browser keyboard traversal and native/public modal; confirmed by assertions | Verified on Dashboard |
| Narrow navigation modal/Escape and width-resized library/chat | Real browser at 390 px and a 480 px plugin container inside a 1440 px viewport | Verified on Dashboard |
| Live host theme, wide/narrow library and form layout | Dark Hermes Teal / light Nous Blue; 1440/390 px; eight screenshots; document/workspace/dialog overflow false; no page errors | Verified on Dashboard |
| Connected packaged Electron and public Desktop Dialog at runtime | Historical isolated app did not clear backend connection overlay; current ESM behaviors tested through React/protocol harness only | External target gate remains open |
| Successful real-provider text/vision | No provider credentials were loaded into the disposable host and no inference was sent | Not performed; approved separately, still open |
| OAuth/independent machine transport | Current real host is loopback only | Open |

Machine-readable sanitized evidence is in `library-first-workspace.json`. Images contain only synthetic records. Credentials, runtime homes, raw server logs and authentication files stay outside the repository.

## Defects reproduced during integration

- Deferred React event access crashed collection name editing. Read input values before scheduling state updates.
- An uncertain capture retry allowed edits that would not be part of the original submitted payload. Fields remain locked until explicit resolution/retry.
- Edit acknowledgement verification incorrectly queried a create receipt. Verify the saved item against the immutable submitted edit and revision instead.
- Discarding an in-flight upload could close without a dirty warning. Pending uploads now count as dirty, and their discarded draft cannot mutate a replacement.
- Failed library identity had no effective retry. Retry now reissues identity discovery.
- Old inline-capture CSS stretched selection checkboxes. The obsolete stylesheet is no longer emitted.
- Reloading a conflicted item reused the prior form controller. The expected item revision now participates in its render identity; local input remains until confirmed reload.
- Actual host theme mapping yielded black text in dark mode, and SDK action-button spacing/bevel leaked into card headlines. Correct public theme tokens and scoped control styles were verified RED to GREEN in the actual browser.
- The narrow CSS-only navigation lacked Escape/focus ownership. It now uses a ResizeObserver-selected public/native modal; it does not dispose chat on resize.

## Verification checkpoints and review

Backend implementation checkpoint: **144 Python tests on CPython 3.14.7 / 78 Node tests**, all passed after the controller reproduced and fixed the manifest mismatch. Subsequent safety-probe additions passed **146 Python tests on CPython 3.11.14**; the Node suite at that checkpoint passed **86 tests**. The independent backend review reported one Important legacy-alias migration defect (quality/security FAIL, backend-spec FAIL for `4fc4bab`), now reproduced and fixed by the author: [original report](library-first-backend-review.md), [RED/GREEN fix](library-first-backend-review-fix.md). The fixed tree passed **147 Python tests on each runtime and 86 Node tests**, with a stable fingerprint and deterministic build/syntax/diff checks. The final independent review is now consumed: six Important findings were reproduced and fixed, with all 14 new cases failing on the frozen prior tree and passing after fixes. The complete stable gate now passes **147 Python tests on each runtime and 100 Node tests**. See the [unchanged original final report](library-first-revision-review.md) and [author fix evidence](library-first-revision-review-fixes.md). No independent re-approval is claimed. The working-tree diff check passes; the committed-range blank-line warning remains an explicitly deferred Minor.

Official CLI validation in a disposable environment returned `ok: true`, `host_ready: true`, matching fifteen declared tools and no core override. It retains two disclosed `inline_shell_exec` scanner cautions in bundled Marked code-span regex source (`index.js:54`, `plugin.js:52`); the scanner did not report executed shell commands. Existing async slow-callback diagnostics remain visible during lock tests.

The fresh backend boundary review and final whole-revision review are separate from previously consumed M1/chat reviews. Author RED/GREEN fixes are not independent approval. Original reports are preserved unchanged, with fixes, all rulings, the two final-review minors and the preserved-report formatting note recorded separately rather than silently regraded away. See [execution decisions](library-first-execution-decisions.md).

## Reproduce safely

Use `scripts/library_workspace_smoke.py` with an explicit loopback origin and token file. Synthetic writes require `--allow-write`; redirects and credential URLs are rejected. A receipt operation key permits read-only verification after a deliberately scoped disposable restart. Never point the write probe at a personal library.

`scripts/library_workspace_browser.cjs` loads the actual Dashboard page and public SDK. Supply the existing Playwright module through `BOOKMARKS_PLAYWRIGHT`, the verified Chrome path through `BOOKMARKS_CHROME` if needed, an output directory and explicit synthetic image file. It makes capture/edit writes only with a final `--allow-write`; opening an owner endpoint can still activate previously accepted enrichment jobs. Use a credential-free disposable home with unconfigured enrichment. The browser does not simulate a provider answer.

Rich-text/inline note images, visual AI, settings, trash/restore, import/export and complete v1 release acceptance remain roadmapped. This revision does not silently replace those requirements with Markdown storage.
