# Final independent library-first revision review

**Reviewed range:** `e3cbfc90f0db21b1238023962a6e9a308972b8f4` → **`d26a7bbe8e09545336ab938f34ed0c3ce2e2e1c3`**.  
**Disposition:** **Not ready to merge / not complete against the approved revision spec. Six Important issues reproduced; no Critical issue identified in this review's surface.**

## Scope and evidence

Read the Senior Code Reviewer template, AGENTS/STATUS, approved workspace specification and plan, every supplied ledger Ruling, and the committed backend/workspace evidence. Reviewed the shared UI and build adapters, relevant service/HTTP/native contracts, persistence projections, and changed queue/tag interfaces. The separate backend boundary review is not replaced or independently approved here.

The worktree advanced to `9850b4eecbb4c0351a4ee3abb259ef2277c71cd7` during review. **That later commit is not the reviewed head.** I archived the requested exact commit into disposable scratch and reran the probes and Node/build gates there. Archive SHA-256: `c281e9c08eedfe649fd58f0b0fa56c82ff5913d6673fa2f0ab4323ad2fd69df6`. Final byte comparison against the archive found **zero changed files among 130 archived files**. Later backend fixes neither change nor regrade this report.

Independent execution on that frozen revision:

- `rtk proxy npm test`: **86 passed, zero failed/skipped**.
- `rtk proxy node scripts/build-ui.cjs --check` and `rtk proxy node --check desktop/plugin.js`: passed.
- Disposable emitted-client probes produced **11 UI observations** reproducing the findings below. These use real React and both generated loaders, synthetic transport responses, controlled promises, and a public-shaped ResizeObserver fixture—not connected Desktop acceptance.
- A disposable real SQLite/JobQueue probe confirmed the unwanted tag mutation, and real in-process FastAPI/ASGI requests confirmed the 400/404/409 error envelopes. No worker/provider was activated. The supplied generated summary was explicitly synthetic fixture data.
- Four additional chat observations verified hidden permission replacement rejection, exact-session Stop, visible uncertain delivery, and no prompt replay through collapse/reopen on both emitted clients.
- `rtk proxy git diff --check e3cbfc90f0db21b1238023962a6e9a308972b8f4..d26a7bbe8e09545336ab938f34ed0c3ce2e2e1c3`: **failed**, with the Minor whitespace finding below. A clean-worktree `git diff --check` does not check this committed range.

Scratch evidence/reproduction directory: `/home/irfansofyana/.hermes/cache/scratch/bookmarks-final-review-o1mk9bvk/`. Run `rtk proxy node ../ui-probes.cjs`, `rtk proxy python -B ../service-probes.py`, and `rtk proxy node ../chat-probes.cjs` with working directory `snapshot/` inside that directory. Results are `ui-probe-results.json`, `service-probe-results.json`, and `chat-probe-results.json`. These disposable files are not repository changes.

For SDK error semantics, inspected official Hermes source pinned to the documented target `d923a5eb487a17c0a68801bba9ef0f56c81040a8`: `web/src/lib/api.ts:161–254`, `web/src/lib/api-error.ts:70–95`, Dashboard registry exports, and Desktop public REST/Dialog implementations. The error probe executes the actual pinned `apiErrorFromResponse` implementation, rather than inventing an error shape.

### Strengths

- The library is genuinely primary, and chat/controller lifetime is separated from visibility. The combined adversarial probe left a hidden request hidden, rejected its displayed predecessor after reopening, denied only `permission-B`, and interrupted only `runtime-chat`. Uncertain delivery remained visible and collapse/reopen produced one prompt submission, not a replay.
- Navigation, item presentation, forms, detail, draft state and modal adaptation are separated into shared modules, with deterministic Desktop/Dashboard output. The inspected production code stays on public host interfaces and does not introduce another agent loop or credential store.
- Item/receipt contracts preserve duplicate-create semantics and expected revisions. The backend rejects stale writes rather than silently overwriting; the remaining conflict problem is the UI's inability to finish a safe resolution.
- Notes use the existing React allowlist; HTML remains literal, remote Markdown images are not loaded, and owned previews use authenticated backend references. No new Critical injection/authentication defect was identified in the inspected surface.
- Acceptance disclosures are unusually clear: real Dashboard evidence is distinguished from protocol tests, connected Electron/provider/OAuth/independent-machine gates remain open, and image storage is not mislabeled as visual inference. The staged-asset and reload/exit draft limits are explicit.

### Issues

#### Critical (Must Fix)

None identified within the independently inspected and exercised surface. This is not a blanket security or backend-concurrency certification.

#### Important (Should Fix)

**I1. Real Dashboard HTTP errors bypass the form's domain-error state machine.**

- **Files:** `scripts/build-ui.cjs:31–32`; `ui/library-state.js:5–8`; `ui/library-form.js:27–43,68–72`; HTTP mapping at `dashboard/plugin_api.py:20–28`.
- **Effect:** `bookmarkRequest` recognizes errors only in a resolved `{ok:false,error:...}` payload. The actual Dashboard `fetchJSON` throws `ApiError` for non-2xx responses, carrying `status`/`body`, not the plugin's `code`/`current_revision`. Thus known validation failures become uncertain, a real 409 misses the direct conflict controls, and a genuine missing receipt cannot unlock an explicit retry. A user can be trapped with locked text even though the server definitively rejected the capture.
- **Reproduction:** The actual ASGI routes returned `400 invalid_argument`, `404 not_found`, and `409 conflict`. Feeding their public SDK exception contract through the emitted Dashboard left validation at “Verify save”; after receipt 404, `retryOffered=false`, `verifyOffered=true`, and notes remained locked. Current tests return resolved error envelopes and miss this boundary.
- **Remedy:** Normalize each public host's non-2xx contract in its adapter, retaining bounded structured domain details, or use the Dashboard's public authenticated raw-response helper. Distinguish known rejections from unknown network outcomes. Add actual SDK-shaped 400/404/409 form regressions, especially the not-found receipt → explicit same-key retry path.

**I2. Saving an untouched valid tag containing a comma removes it and creates different manual tags.**

- **Files:** `ui/library-form.js:4,8,50–55,101`; permitted backend labels at `bookmarks/tags.py:8–12`.
- **Effect:** Arrays of arbitrary valid Unicode labels are round-tripped through comma-joined text. A generated or manual label such as `Research, AI` is split even if the user never edits tags. A notes-only edit—or just Save—then suppresses the original label and creates `Research` and `AI` as manual labels. This changes discovery/filter results and provenance without consent.
- **Reproduction:** Both emitted clients sent `add_tags:["Research","AI"]` and `remove_tags:["Research, AI"]` after opening Edit and immediately saving. Applying that emitted delta to a real generated-tag item changed its `tag_details` to two manual tags; searching the original tag returned zero items.
- **Remedy:** Keep tag arrays/identities and provenance in draft state. Use explicit chip add/remove actions with the planned existing-tag suggestions, or a lossless representation; never derive removals from a lossy display string. Cover commas and normalized aliases in unchanged-form and notes-only round trips.

**I3. Scoped draft retention does not retain ownership/notification of in-flight completions.**

- **Files:** `ui/library-form.js:6–17,21–25,68–72,80–91`; `ui/library-state.js:2,5–7`; Desktop remount at `scripts/build-ui.cjs:16–20`.
- **Effect:** The Map preserves a draft object across profile remounts, but its promise continuations still belong to the old component's `live`/`paint` callbacks. Reopening the same draft before a late success can leave the new form stuck at “Saving…” after the write has completed. A successful same-library upload response can also be discarded solely because the profile changed, losing its returned owned asset ID. Treating post-dispatch `scope_changed` as a known unsaved rejection compounds the lost-acknowledgement problem.
- **Reproduction:** In the emitted Desktop client, hold capture, switch work → personal → work on the same connection/library, reopen Add, then resolve success. The new form remained open with disabled “Saving…”, no saved notice, and one accepted POST. Separately, hold an upload, switch to another participating profile in that same library, reopen Add and resolve success: notes survived, but `uploadedIds=[]` and the error was “The connection or profile changed.”
- **Remedy:** Own pending operations and completion notifications at the immutable connection/library/draft identity, independently of a particular mounted form. Let a resumed owner subscribe/reconcile; apply returned owned IDs only to the originating, undiscarded draft. Keep visible-publication guards and transport scope checks—do not solve this by allowing publication into a different backend. A scope change after dispatch is not proof that no write occurred.

**I4. “Keep editing” cannot lead to a revision-safe save of the preserved local draft.**

- **Files:** `ui/library-form.js:51–58,69–72,76–78,107`.
- **Effect:** After conflict, the local text survives, but `draft.original.revision` never advances and the current server revision is not fetched/displayed for comparison. “Keep editing” only resets the phase. Every subsequent Save uses the original stale revision. The only offered refresh path discards the draft, so a user must copy work out of the application to resolve an ordinary multi-client edit.
- **Reproduction:** Both emitted clients submitted expected revisions `[1,1]` after conflict → Keep editing → change text → Save; only the original detail read occurred. The real service likewise rejected both stale attempts after an unrelated remote description edit. This remains broken even if I1's exception normalization is fixed.
- **Remedy:** Provide explicit compare/rebase resolution: fetch the saved version without replacing local fields, show the divergence, and allow an explicitly confirmed new save against that reviewed revision. Do not automatically adopt the revision or introduce last-write-wins. Test preservation and eventual successful save, not just preservation and destructive reload.

**I5. Responsive navigation remount silently drops an open collection draft.**

- **Files:** `ui/library.js:9,51,60`; collection editor state/lifetime at `ui/library-navigation.js:17–19,23–31,43–50`.
- **Effect:** Crossing 680 px replaces the whole Navigation instance. Its collection editor/draft exists only in local state, so resizing closes the modal and loses the typed name/parent without Keep editing / Discard. Pending mutation ownership and refresh callbacks are also attached to the discarded instance. This exceeds the ledger ruling's accepted loss of transient tree expansion: it loses actual form work.
- **Reproduction:** On both emitted clients, open New collection and type `Keep my collection draft`, then deliver a 480 px ResizeObserver measurement. Both the input and modal disappeared; reopening New collection yielded an empty value, with no discard confirmation. Window resizing while a modal is open is a valid user interaction; this is not an artificial click through inert background content.
- **Remedy:** Keep one navigation/editor owner across responsive presentation changes, or lift collection drafts and pending mutation state above the branch. Mount only its presentation in the appropriate public/native modal. Preserve drafts and reconcile saves across width and relevant scope remounts; add both open-form and pending-save cases.

**I6. Refreshing loaded tag/collection pages appends the last page again instead of refreshing navigation.**

- **Files:** `ui/library-navigation.js:6–8,13,20–21,41`; invalidation at `ui/library.js:32,37,41`.
- **Effect:** The same effect handles “load more” and revision invalidation. At a nonzero offset, any successful save or native-chat refresh appends that offset's page to the existing accumulated rows. Earlier counts/names remain stale, duplicate keys appear, and the rendered row count no longer agrees with the server total. CollectionLevel has the same append-on-revision branch.
- **Reproduction:** Load all 51 tags, then save an item that changes counts. Both emitted clients rendered 52 rows with only 51 unique labels; Tag50 appeared twice with different counts, Tag0 retained its old count, and React warned about duplicate keys. Requests used offsets `0,50,50`, never refreshing the first page.
- **Remedy:** Distinguish page extension from invalidation. Refetch/replace the loaded range, or reset and replace from page zero with explicit paging semantics; merge by stable identity and guard the refresh generation. Add save/rename/delete/native-refresh cases after loading additional tag and collection pages.

#### Minor (Nice to Have)

**M1. A save outside the active filter has no promised “View item” action.**

- **Files:** `ui/library.js:41,50`.
- **Effect/repro:** Save a non-favorite while browsing Favorites, or an item outside the current tag/search filter. The form closes and the notice says only “Saved to your library”; it retains neither an actionable saved item nor a View control. The user must change filters and find it manually.
- **Remedy:** Retain the returned item identity in the notice and expose View item without reverting the current filter. This is an explicit requirement in spec §6, not a request to navigate automatically.

**M2. The committed range fails the whitespace check.**

- **File:** `ui/chat.css:5`.
- **Effect/repro:** The exact-range `git diff --check` exits 2 with `new blank line at EOF`.
- **Remedy:** Remove the extra trailing blank line and run the range-aware check as well as any working-tree check. No runtime failure is attributed to this whitespace.

### Recommendations

Fix the proved Important findings in the authorized single author RED→GREEN pass. Strengthen the existing emitted-client harness at the real adapter exception boundary and around retained draft subscriptions, rather than adding another large mock-only feature suite. Keep the original independent reports intact; an author's successful fix run is not independent approval.

Update the evidence matrix after fixes so “revision-safe edits,” “scoped drafts,” and “pagination/navigation” do not imply these failing interactions were already accepted. Keep the existing explicit external gates; no new approval or historical re-review cycle is requested here.

### Declined to judge

These are not silently waived or counted as passing:

- **Exhaustive migration, reciprocal-move/deletion serialization and enrichment lease/cancellation races:** assigned a distinct concurrent backend boundary review. I inspected the interfaces and relevant transaction/tag paths and exercised the service where needed for UI findings; I did not duplicate that seat or accept its green tests as independent proof.
- **Connected packaged Electron rendering, actual Desktop modal focus/stacking and remote IPC acceptance:** the documented connection overlay gate remains open; no live install, connection alteration or credential access was permitted. The Node helper omits public Dialog components, so its Desktop label does not prove the real Radix branch.
- **Fresh authenticated actual-Dashboard browser/restart acceptance:** reviewed the committed machine evidence, browser/smoke scripts and representative dark-narrow/light-wide-form screenshots, but did not restart servers or read token files. The ASGI probes are not host-auth middleware evidence. The supplied Dashboard registry does export public Dialog components; the real adapter can take that branch rather than the helper's native fallback.
- **Successful provider text/vision, inference routing/trust, provider cancellation and charges:** no provider calls or credential reads allowed. Synthetic protocol events and a supplied queue result are not successful inference evidence.
- **OAuth, independent-machine transport and maximum proxy payload acceptance:** no authorized topology or credentials were supplied; loopback evidence does not establish these behaviors.
- **Full accessibility/visual certification, including screen-reader announcements, reverse keyboard traversal and every short-height/long-content case:** static screenshots and jsdom cannot establish these. The committed browser script's focus loop exercises forward Tab, not reverse Tab; this remains an evidence limitation, not a claimed focus escape.
- **Rich-text/inline images, configurable vision, settings, import/export and trash/restore:** explicitly staged outside this revision, still required by the roadmap; not judged as missing implementations in this slice.
- **Durable recovery after process exit/reload and abandoned staged-asset garbage collection/quotas:** explicitly disclosed non-goals of this revision. I did judge the required same-library in-memory remount recovery in I3/I5.
- **Later commits/fixes, exact-head remote CI, merge/release/live installation:** outside the requested immutable range and this read-only scope. I neither certify later changes nor authorize deployment.

### Assessment

**Quality/security verdict: FAIL / fixes required.** No new Critical security flaw was identified in this surface, but reproduced data-integrity, draft-lifetime and error-contract failures make this exact revision unsuitable for approval as finished work.

**Spec verdict: NOT SATISFIED.** The architecture and much of the visible workspace match the approved design, but required unchanged-tag preservation, usable conflict resolution, same-library late-operation recovery, safe form lifetime and refreshed paginated navigation fail under reproduced conditions. External target/provider gates also remain explicitly open.

**Ready to merge? No.** Continued development and an honestly unfinished draft PR remain consistent with the owner's permission; this report is not merge, release or live-install approval.

**Repository changes by this review:** only this requested report. No source, tests, committed documentation, index or HEAD were modified; no reviewers or listening services were spawned. Disposable probes/results and downloaded public SDK source stayed under TMPDIR. A redundant public SDK export-index fetch returned HTTP 429; the source needed for the error-contract and modal inspection had already been retrieved, so it did not block the findings.
