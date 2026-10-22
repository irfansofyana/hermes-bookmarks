# Recoverable trash and durable imports — verification

Date: 2026-10-22. Development snapshot `775cfa855c474a6a07adf3ff2f07e960e477ead9`, with a subsequent browser-harness-only wait for responsive portal reflow. This is synthetic development verification, not installation, release, all-target acceptance, or successful provider inference.

## Implemented contract

- Revision-checked soft delete/restore. Trash retains notes, metadata and owned assets, excludes items from active views/counts and fences late enrichment. Capturing a trashed duplicate reports `trashed_duplicate`; it never restores implicitly.
- Supplied normalized JSON or Netscape bookmark HTML, bounded to 2 MiB and 500 records; nested collections/tags/notes and supported source provenance. Preview performs no item/collection/tag writes or publisher/inference calls. Unknown fields and unsupported HTML metadata produce warnings; this is not a lossless arbitrary-source importer.
- Immutable staged preview ID/digest, explicit Start with stable request ID; lookup by request ID is read-only. Existing active/trashed duplicates are skipped, never overwritten or restored.
- SQLite fenced durable per-row execution: item, provenance, result, cursor and counters commit together. Cancellation keeps committed effects and stops remaining rows. Default enrichment is off; opt-in snapshots an admissible route.
- Native tools and authenticated HTTP routes share the service. Import supervision uses the original public host task context independently of enrichment configuration.
- Both emitted UIs provide Import source/file selection, Preview, explicit Start, warnings/results, progress/cancel, paged results and inspection by saved job ID after reload. Source bytes remain in scoped in-memory drafts, not separate browser persistence. Losing a Start acknowledgement freezes its identity and offers read-only reconciliation rather than blind replay.

## Automated gates

At the code snapshot above:

- **173 tests pass on CPython 3.14.7 and CPython 3.11.14.** Includes real disk-backed child process `os._exit(17)` after the first committed row; another process/service resumes after lease expiry without duplicate result/items.
- **110 Node tests pass**, exercising both emitted Desktop and Dashboard loaders with real React/transport doubles. Import additions cover explicit Preview/Start and payload shape, default no-AI, dirty close, uncertain admission lookup, post-reload job inspection/result pagination, and discarded asynchronous file reads.
- Deterministic emitted build check, Desktop syntax, browser-harness syntax and whitespace pass.
- Official isolated `hermes plugins validate PATH`: **Validation passed**; declared tools/hooks/middleware match registration, no tool collisions/core override and supported Desktop SDK surface. Two scanner cautions remain on bundled JavaScript code-span regex syntax (`inline_shell_exec`); the same known bundled Marked construct is not shell execution. Execution isolation is the plugin host, not a security sandbox.

Local harness remediation is not a product defect: the old Python 3.11 scratch venv had expired. After recreating it, the first run inherited Hermes's Python 3.14 `PYTHONPATH` and failed binary imports. Re-running the entire 3.11 suite with `env -u PYTHONPATH -u PYTHONHOME` used its installed dependencies and passed all 173 tests. No live Python environment was modified.

## Actual host, native registry and restart

Disposable Hermes home/library, copied development plugin, loopback TCP; production home/services unchanged. No source vault, real bookmarks or model requests used.

Evidence (raw credential/log files intentionally excluded):

- [`import-smoke.json`](import-smoke.json): real authenticated TCP routes; unauthorized GET/POST rejected, preview writes zero items, idempotent Start/read-only request lookup, terminal report exactly **4 rows = 2 imported + 1 skipped + 1 failed**, supported notes/source provenance, trash exclusion and revision-checked restore, actual HTML import, cancellation. The 100-row cancel stopped at **0 processed/100 remaining**; partial-after-commit cancellation is separately covered in SQLite tests, not misrepresented as this TCP result.
- [`import-restart.json`](import-restart.json): owned disposable server terminated, original port verified closed, actual host restarted on a new port, then authenticated job/item readback retained the report, notes and provenance. This proves persistence across real host restart; crash mid-row recovery is the separate disk-backed subprocess test.
- [`import-native.json`](import-native.json): real plugin-manager discovery plus `model_tools.handle_function_call` registry dispatch exercised `bookmark_import_preview`, `bookmark_import_start`, `bookmark_import_request_get`, `bookmark_job_get`, `bookmark_job_cancel`, `bookmark_delete`, `bookmark_restore` and `bookmark_get`. No direct service substitution for dispatch. Synthetic imported notes/restore/cancel passed. A separate unrelated basic-auth plugin emitted an incomplete-settings warning in that credential-free probe; Bookmarks tools still passed. Dashboard TCP authentication was independently tested.

Repro scripts: `scripts/import_smoke.py` takes explicit loopback origin/token-file and requires `--allow-write`; `--reopen` reads a prior synthetic report against an operator-restarted disposable host. Scripts do not restart or configure a service themselves. Native dispatch was a scratch-only driver using the actual public registry, not a committed credential fixture.

## Actual Dashboard/public SDK browser

[`import-browser.json`](import-browser.json), generated by `scripts/import_browser.cjs` against the actual host/SDK, records:

- Real source entry, dirty Escape/Keep editing, preview, explicit Start and terminal progress. Imported notes, tags and provenance read from backend; trash/Undo through the visible UI; page reload followed by inspection using saved job ID.
- Dark/light and 1440/390 px viewport matrix, forward/reverse keyboard focus kept inside the dialog, no page errors or document/dialog overflow.
- Final narrow measurements: dialog bounds **left 6/right 384** in the 390 px viewport; wide bounds **510/930** in 1440 px. Initial immediate-after-resize measurements ran before portal reflow; the harness now waits for bounded layout completion, then checks both bounding rectangle and scroll overflow. Product layout was not changed to satisfy the harness.
- Screenshots in `screenshots/bookmarks-import-{dark,light}-{1440,390}.png`. Narrow/dark and wide/light screenshots were visually inspected: content/actions visible, no clipping/overlap. These are real SDK controls, not raw-button doubles.

All disposable servers used here were stopped; both previously owned listener ports were verified closed. No active installation, production restart, merge or release.

## Review and remaining gates

The targeted immutable backend review `c1abe3c..ebbf973` returned no concrete Important/Critical defect. Preserve its limited scope in [backend disposition](trash-import-backend-review.md); it excluded later HTML/API/UI. A separate final milestone review was dispatched at `775cfa855c474a6a07adf3ff2f07e960e477ead9` and is pending consumption. No final independent approval or exact-head publication is claimed here yet.

Connected packaged Electron, physical/remote-machine and OAuth proxy acceptance remain open. The emitted Desktop React tests are not a substitute. Real text/vision tests are approved but not performed in this slice. Export/lossless restore, full settings and image analysis, rich-text/inline-note images, bulk polish and final release gates remain required future work; imports do not remove export.
