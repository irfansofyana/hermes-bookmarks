# Development status and continuation handoff

## Current stage

Implementation planning complete; plan review and execution-method selection pending. Product implementation has not started. There is no installable plugin, no completed host probe, and no runtime test result to report.

Product direction was approved for implementation planning. The owner explicitly wants compatibility discovery during development, native Hermes reuse without core changes, and durable documentation for future sessions. Do not restart product brainstorming or require a mockup.

## Read next

1. `AGENTS.md`
2. `docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md`
3. `docs/ROADMAP.md`
4. `docs/superpowers/plans/2026-10-20-m1-native-foundation.md`

## Execution handoff

Next action: present the committed M1 plan for review and confirm execution method. Recommend subagent-driven execution with fresh task reviews. The user delegated the breakdown, but did not explicitly choose native versus subagent-driven execution. Once reviewed and selected, use the corresponding execution skill, create an isolated development worktree, and start M1 Task 1. Do not skip directly to UI construction or add a custom chat implementation.

If a later user message has already approved execution, follow that message instead of asking again. Record the approval and method here before commencing work.

## Verified repository facts

- Public repository: `irfansofyana/hermes-bookmarks`.
- Initial specification commit: `c1b37f4d278ce76c9ac6632422ecc7e402875f19`.
- Native chat, UX, batch tool and migration revision: `b4259228b11bf57f7227e71207b26f833b15ce79`.
- Planning files are included in the commit containing this handoff; obtain its full SHA with `rtk git log -1` rather than maintaining a self-referential commit field.
- No CI workflow exists yet. Documentation checks are not product tests or host compatibility validation.

## Milestone status

| Milestone | State | Next deliverable |
| --- | --- | --- |
| M1 native foundation | Detailed plan awaiting review | Public host capability evidence and minimal package |
| M2 organization/import | Roadmapped; not implemented | Detailed plan against established M1 contracts |
| M3 notes/images/enrichment | Roadmapped; not implemented | Detailed plan against working jobs/assets |
| M4 polished UI/native workflow | Roadmapped; not implemented | Complete emitted UI and real-host visual evidence |
| M5 portability/release | Roadmapped; not implemented | Export/restore and release evidence |

## Decisions not to reopen without new evidence

Shared library across profiles; native chat identity remains session/profile owned. Automatic tagging and summarization for individual saves; bulk enrichment opt-in. Nested collections. Rich notes, standalone images, and inline note images. Standalone images may receive configured vision analysis; note images are not automatically analyzed. Follow each host's theme. Import-first does not remove export from required v1. Existing file tools plus normalized import records handle vault migrations; no dedicated Obsidian connector is required. No custom chat or Hermes patches.

## Unverified engineering boundaries

Desktop/Dashboard native-chat composition or supported handoff, installation-owned storage root and service ownership, public worker lifecycle, stable enrichment route/vision trust settings, remote attachment transport, and authentication/approval behavior. Verify within M1. Record exact host versions and sources; public source links alone are not proof of exercise.

## Permissions

Public docs updates are requested. Development is requested in principle but detailed plan review/execution-method selection remains the next workflow gate. No authorization to deploy into running Hermes, restart services, submit upstream/catalog PRs, merge, publish releases, use paid inference, or migrate real vault content. Use synthetic fixtures and isolated hosts unless separately approved.

## Handoff maintenance

After each task, update its checkboxes and add: commit, exact tests and exit status, real-host evidence versus mocked coverage, skipped checks, blockers, next action. Never mark M1 complete just because the package loads or a mock test passes. Keep private data out of this public file.
