# Final whole-branch review

**Base:** `e7e0cc91cf71724c9d3caf7978308be462c78a77`  
**Snapshot:** `d602bed8120fc67cd873abad97edea021c9c70d2`

## Scope and evidence

Reviewed production source, adapters, migrations, security boundaries, tests, plan/spec, current STATUS/M1 evidence, and prior rulings. Read shared UI once and inspected thin emitted adapters; deterministic build check and range whitespace check passed. HEAD remained the requested snapshot with no tracked changes. Three focused synthetic probes below used temporary SQLite storage or real React/jsdom, without publisher/model calls. Existing 77-Python/two-version, 10-Node, validator and actual-host results are **recorded evidence, not reruns by this reviewer**.

## Strengths

- Shared explicit-root service, transactional duplicate identity, parameterized SQL/literal FTS, migration rollback and cross-process tests are sound foundations.
- Claim tokens, revision checks and post-lock completion clocks protect persistence. Previously reported executor cancellation and nonowner bootstrap defects are fixed, not repeated findings.
- Owned image IDs, decoder/reencoding limits, authenticated routes and pinned-IP extraction avoid arbitrary path/static-mount/provider-store shortcuts.
- New activation uses the original context/profile and public async lane; no private loop/core workaround. Unsupported Dashboard chat and missing actual Desktop/model evidence are disclosed honestly.

## Issues

### Critical (Must Fix)

None found.

### Important (Should Fix)

1. **One accepted URL can break rendering of the library.**  
   **Files:** `bookmarks/urls.py:48–50`; `ui/library.js:124`.  
   The DNS-label validator accepts `https://256.256.256.256/`, but the renderer unconditionally evaluates `new URL(item.url)`. A focused service probe persisted this URL and returned it in search; the real React component then threw `TypeError: Invalid URL`. An API/native capture or mistyped numeric host can therefore poison any result page containing the item on both clients. Reloading repeats the failure, and M1 has no deletion UI. Guard display-time URL parsing so one record cannot crash the page, and validate problematic numeric-host forms at capture. Add a persistence-to-render regression.

2. **A transient database lock permanently stops enrichment while health still says started.**  
   **Files:** `bookmarks/enrichment.py:51–54`; `worker_host.py:35–40`; `runtime.py:80–84`.  
   Recovery/claim run outside the worker's exception handling. Startup discards the task handle, and activation only retries `host_loop_unavailable`, not a terminated worker. Focused reproduction: activate through `ensure_enrichment`, hold a real SQLite write lock beyond its five-second busy timeout, then release. Observed `worker_done=True`, `StorageError`, job still `pending`; another activation left task count at one and startup status `started`. Ordinary storage contention can strand all later jobs until reload despite restored storage. Add bounded transient-storage recovery and lifecycle-owned task termination/status handling; preserve original-owner and single-activation guards.

3. **Completing an older save overwrites the user's newer search results.**  
   **File:** `ui/library.js:58–62` (interacts with `35–50`).  
   The completion calls `load(query)` from the save's old render closure. Search remains usable during saving, so this refresh receives a newer request generation and wins over the current query. A controlled React probe held POST, searched `Beta` successfully, then released POST: the search box still read `Beta`, heading remained `Search results`, but rows became `Alpha, Beta`; final request was `/items?query=`. Both emitted clients inherit this mismatch. Refresh/invalidate the current query rather than the captured one, and regress the pending-save/search ordering without disabling unrelated search controls.

### Minor (Nice to Have)

1. **Retry does not retry the failed action.** `ui/library.js:65,110`: every error's Retry invokes only `load(query)`, including failed saves/uploads. A successful GET clears the error without retrying capture. Bind recovery to the failed operation or explicitly label it “Reload library”; keep input and uncertain mutation outcomes clear.
2. **Narrow layouts hide all processing status.** `ui/library.css:1`, `@media(max-width:600px)`: `.hb-item-status{display:none}` also removes failed/queued states. Mobile users cannot inspect the M1 status shown on wider layouts. Wrap/reposition a compact status instead of suppressing it entirely.

## Recommendations

Fix the three Important findings with focused regressions and then perform the normal verification gate. These are defects in delivered M1 behavior, not requests to implement future milestones. Keep the partial-foundation label and existing host restrictions.

## Declined to judge

- M2–M5 organization, full UI pagination, imports, notes, settings UX, exports, automatic cross-view refresh and final polish: explicitly future milestones, not silently waived release requirements.
- Actual Desktop/composer acceptance: disposable host remained offline; SDK-shaped tests cannot establish a mounted composer or native chat behavior.
- Dashboard contextual handoff: inspected SDK limitation requires a supported contract or owner acceptance revision, not plugin-private integration.
- Real provider text/vision, trust and routing: approval absent; no inference performed. Activation proof is not provider proof.
- Independent-machine/OAuth and maximum proxy payload behavior: current evidence does not exercise these topologies/ceilings.

## Assessment

**Code quality/security verdict: Changes required.** Three reproducible Important defects remain. No new authentication or SSRF bypass was identified in inspected paths; untested transport gates remain unapproved.

**Spec-compliance verdict: Partial; M1 not accepted.** The foundation follows the shared-library/public-SDK/no-custom-chat architecture, but the defects above and documented Desktop, Dashboard-handoff and real-model gates prevent full target acceptance.

**Ready to merge? No.** Resolve the Important defects and separately obtain/verify the remaining acceptance decisions; passing existing suites alone is insufficient.
