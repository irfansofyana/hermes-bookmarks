# Development instructions

## Read before working

1. `docs/STATUS.md` for current progress, permissions, and the next action.
2. `docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md` for product requirements.
3. `docs/ROADMAP.md` for delivery boundaries.
4. The active milestone plan linked in STATUS.

Do not infer completed implementation from a plan checkbox, an example response, or this conversation. Check the working tree, remote refs, and actual tests. Preserve uncommitted work.

## Non-negotiable integration rules

- Use public, documented Hermes SDKs and exported components. Official docs are authoritative; inspect the exact target version during development.
- No Hermes core edits, private imports, monkey patches, DOM/React interception, copied internal chat components, custom chat renderer/composer/agent loop/model picker, or separate credential store.
- Reuse native chat. If composition is unsupported, use a supported explicit handoff. Missing supported APIs are limitations to report, not permission to bypass constraints.
- Shared library per installation; explicit data root. Never silently fall back to per-profile storage or assume profile names are unique across backends.
- Chat belongs to an explicit profile/session. Library enrichment settings and native chat model selection are independent.
- Follow each client's active Hermes theme with scoped CSS and public components.
- Inspect `irfansofyana/hermes-blogwatcher` as a working reference, not an unchanged backend template.

## Workflow

Use the relevant Hermes skills and Superpowers workflow. Execute tests first, show the failure, implement, then show the passing result. Keep focused commits. Prefix shell commands with `rtk`; use `rtk proxy` when raw output must be parsed.

Develop in an isolated checkout/worktree and test environment. Installing into active plugin discovery roots can hot-reload; do not treat copying files there as harmless development. No live service restart, deployment, catalog submission, paid model calls, real-vault migration, or merge without explicit approval for that action. Public code pushes on a development branch do not authorize merging it.

## Durable handoff

Update `docs/STATUS.md` after each completed task with commit, exact commands/results, skipped host checks, blockers, and the next runnable action. Maintain `docs/verification/` for evidence. Update milestone checkboxes only after verification. Record host/backend/Desktop versions separately. Never put user vault content, personal bookmarks, credentials, environment dumps, or private machine endpoints in this public repository.

A release is not complete until the roadmap's required v1 capabilities are exercised. A partial foundation must be labeled as such. Mocks do not establish real host compatibility.
