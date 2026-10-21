# Development instructions

## Read before working

1. `docs/STATUS.md` for current progress, permissions, and the next action.
2. `docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md` for product requirements.
3. `docs/ROADMAP.md` for delivery boundaries.
4. The active milestone plan linked in STATUS.

The owner approved the written library-first design in `docs/superpowers/specs/2026-10-21-library-first-workspace-design.md` with “lets implement all”. The detailed plan is `docs/superpowers/plans/2026-10-21-library-first-workspace.md`; plan review precedes product changes. Preserve the existing hybrid method and the library/chat ownership, draft and manual-edit requirements. See STATUS for the current approval stage rather than asking to approve an already approved artifact again.

Do not infer completed implementation from a plan checkbox, an example response, or this conversation. Check the working tree, remote refs, and actual tests. Preserve uncommitted work.

## Non-negotiable integration rules

- Use public, documented Hermes SDKs and exported components. Official docs are authoritative; inspect the exact target version during development.
- No Hermes core edits, private imports, monkey patches, host DOM/React interception, copied internal chat components, new agent loop or separate credential store.
- Owner clarification: Bookmarks must have its own chat UI while the plugin is open, not redirect primarily to the usual Hermes session screen. Plugin-owned conversation presentation is allowed; reuse public Hermes agent/session/provider facilities underneath and public UI components where they fit. Do not substitute draft handoff for the requested in-plugin experience. Verify the supported backend contract before implementing it; do not assume either an exported full-chat component or a custom agent runtime is required.
- Shared library per installation; explicit data root. Never silently fall back to per-profile storage or assume profile names are unique across backends.
- Chat belongs to an explicit profile/session. Library enrichment settings and native chat model selection are independent.
- Follow each client's active Hermes theme with scoped CSS and public components.
- Inspect `irfansofyana/hermes-blogwatcher` for packaging/host-adapter patterns and `irfansofyana/hermes-learning` for the requested in-plugin chat UI/session/transport pattern. Pin and inspect relevant source; adapt domain semantics without depending on either plugin at runtime.

## Workflow

Use the relevant Hermes skills and Superpowers workflow. Execute tests first, show the failure, implement, then show the passing result. Keep focused commits. Prefix shell commands with `rtk`; use `rtk proxy` when raw output must be parsed.

Develop in an isolated checkout/worktree and test environment. Installing into active plugin discovery roots can hot-reload; do not treat copying files there as harmless development. No live service restart, deployment, catalog submission, paid model calls, real-vault migration, or merge without explicit approval for that action. Public code pushes on a development branch do not authorize merging it.

## Durable handoff

Update `docs/STATUS.md` after each completed task with commit, exact commands/results, skipped host checks, blockers, and the next runnable action. Maintain `docs/verification/` for evidence. Update milestone checkboxes only after verification. Record host/backend/Desktop versions separately. Never put user vault content, personal bookmarks, credentials, environment dumps, or private machine endpoints in this public repository.

A release is not complete until the roadmap's required v1 capabilities are exercised. A partial foundation must be labeled as such. Mocks do not establish real host compatibility.
