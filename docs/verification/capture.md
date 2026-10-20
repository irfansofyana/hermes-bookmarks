# M1 capture slice evidence

Task 3: native tools, shared HTTP adapters and both emitted library interfaces. Development-only; not installed or fully host-verified.

## Implemented

`bookmark_save`, `bookmark_get`, `bookmark_search` register through the documented native plugin API. The HTTP routes `/items`, `/items/{id}` use the same strict dispatcher/service. The shared React source builds Desktop ESM and Dashboard IIFE independently. Users can save links, see title/domain/status, search, and retry failures. Failed saves retain their input; repeated clicks while pending cannot duplicate submissions.

Configuration is explicit: `plugins.entries.hermes-bookmarks.settings.library_root` is an absolute shared data directory. Configure the same path in participating backend profile configs. Never infer a root from the active profile. A plugin-owned named bridge joins native registration and path-loaded HTTP within the plugin host, following the Blogwatcher pattern; it owns no credentials. Conflicting roots in a process are rejected and cleanup is registration-owned. Separate processes require consistent operator configuration. No config or files on the running host were changed. Real cold-host bridge/auth behavior remains unverified.

## Test-first evidence

- `rtk proxy python -m unittest discover -s tests -p test_tools.py -v`: RED, missing `native_tools`; after implementation, 7 passed.
- Package tests changed to require actual native registrations: RED, empty tool declarations/registrations; after wiring, passed.
- `rtk proxy node --test tests/test_ui.cjs`: after isolated test dependency setup, RED due absent Desktop bundle and Dashboard preview not rendering library data; after implementation, 3 passed. Real React/DOM exercises both emitted entrypoints using synthetic transport responses, failed and successful save, duplicate-click guard, and search.
- Final whole Python suite: `rtk proxy python -W error -m unittest discover -s tests -v`: 40 passed, exit 0.
- Final whole Node suite: `rtk proxy npm test`: 4 passed, exit 0.
- `rtk proxy node scripts/build-ui.cjs --check`, `rtk proxy node --check desktop/plugin.js`, `rtk git diff --check`: exit 0.
- Official `hermes plugins validate <worktree> --json` in fresh synthetic HOME/HERMES_HOME, credential-free environment: exit 0, `ok:true`, no warnings, three declared tools match registrations, Desktop stays inside public SDK, no core overrides. The launcher prepared dependencies only in scratch. No active install/restart.

Runtime-only dependencies remain host supplied. Node dev dependencies are test-only and lockfile-pinned; they are never bundled as another runtime React. CI was updated but has not run remotely because no branch push was authorized.

## Limits

Direct-router tests do not include host auth middleware. JS DOM tests do not establish real browser styling or installed renderer support. The preview still says AI/native context/image capture unavailable. Shared-root registration is explicit but cross-profile/cold-start host integration must be exercised. No model call, external page fetch, real-vault access, deployment or remote CI success is claimed.
