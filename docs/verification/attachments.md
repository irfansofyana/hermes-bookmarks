# Image attachment slice (Task 6 partial)

A stable backend-owned asset ID resolves an image from the explicitly configured shared library. No local filesystem path is returned, and no public static-files mount is added. Attachments are not yet standalone image library items or inline note embeds; those remain M3.

The decoder is Pillow 12.3.0, already present in the inspected host environment, pinned in runtime metadata and test requirements. Python-multipart 0.0.32 is pinned for the multipart endpoint. Validation allows PNG/JPEG/WebP, rejects MIME mismatch, truncated/unsupported files and animation, and limits encoded input to 10 MiB and decoded area to 20 million pixels before loading pixels. Images are reencoded with metadata cleared. File staging occurs in the library assets directory with flush/fsync and rename; a failed DB insertion removes the file. A process crash between file promotion and DB commit can leave an orphan; reconciliation/cleanup is not yet implemented.

Native tools:
- `bookmark_attachment_add(content_base64, mime_type)` stores supplied image bytes without reading arbitrary server files or requesting AI analysis.
- `bookmark_attachment_get(asset_id)` returns metadata and a host-authenticated API reference, never a filesystem path.

HTTP routes under `/api/plugins/hermes-bookmarks`:
- `POST /assets` accepts bounded raw image bytes or a single multipart `file`.
- `POST /assets/base64` accepts the bounded native-tool input shape.
- `GET /assets/{id}` delivers a validated owned file with `nosniff` and private/no-store caching.
- `GET /assets/{id}/preview` returns a small JPEG preview as JSON/base64.

Both shared UIs use public JSON transport (`ctx.rest` or Dashboard `fetchJSON`) for upload and preview. This avoids assuming binary IPC uploads work in every authentication mode: inspected Desktop source documents its ArrayBuffer multipart upload as token-mode-only. Browser-local data URLs are display-only; the persisted library asset ID is the durable reference. Full-size JSON upload behavior through actual host proxy limits remains unverified.

Observed RED: missing asset module; direct API upload returned 404; both emitted UI tests failed because no image capture existed. GREEN: 65 Python tests and 10 Node tests, `node scripts/build-ui.cjs --check`, `node --check desktop/plugin.js`, and `git diff --check` exit 0. Real React/jsdom tests exercise both emitted entrypoints; responses in those tests are explicit synthetic fixtures. Direct FastAPI tests exercise real image decoding, raw/multipart/base64 upload, native metadata lookup, original bytes and preview roundtrip. Additional tests cover MIME mismatch/SVG/HTML/truncation/byte/pixel limits, invalid IDs/symlink refusal, reopening storage, and safe storage errors.

Official `hermes plugins validate <worktree> --json` also passed in synthetic HOME/HERMES_HOME with `ok: true`, no warnings, matching tool registrations and no core overrides. The validator prepared dependencies only in that isolated data root.

These are isolated code tests, not installed-host verification. Unauthorized rejection by actual Hermes authentication, cold backend plugin-bridge initialization, local-client/remote-backend image delivery, screenshot/theme verification, independent upload security review and final whole-branch review remain acceptance gates. No live plugin installation, service restart, real user images or model calls were performed. Task 6 and M1 remain incomplete.
