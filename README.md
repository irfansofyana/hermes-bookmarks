# Hermes Bookmarks

A planned standalone bookmark and image library for Hermes Desktop, Dashboard, and native chat tools.

**Status: M1 execution approved; Task 1 foundation preview implemented with concerns.** The minimal package passes isolated Hermes validation, but capture, Desktop UI, enrichment and contextual native-chat integration are not implemented or accepted. See [host evidence and limits](docs/verification/compatibility.md) and [development status](docs/STATUS.md). This is not a v1 release or an approved live deployment.

## Product direction

- One shared library per Hermes backend installation, across agent profiles.
- Raindrop-inspired visual organization: grid/list views, nested collections, tags, favorites, and read later.
- Automatic AI tags and summaries for individual saves, with configurable controls and explicit opt-in for bulk imports.
- Link bookmarks, standalone image items, and rich-text personal notes with inline images.
- Desktop and Dashboard interfaces that follow the user's active Hermes theme.
- Native Hermes tools for capture, search, organization, notes, enrichment, and settings.
- Import-first delivery; export remains required.

## Design

Read the [specification](docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md), [delivery roadmap](docs/ROADMAP.md), and [M1 implementation plan](docs/superpowers/plans/2026-10-20-m1-native-foundation.md).

Future sessions should start with [AGENTS.md](AGENTS.md) and [development status](docs/STATUS.md). These record progress, permissions, unverified integrations, and the next action.

## Implementation references

- Official Hermes documentation: https://hermes-agent.nousresearch.com/docs/
- Working reference requested by the owner: https://github.com/irfansofyana/hermes-blogwatcher

The official documentation is the integration contract. Blogwatcher is a reference for packaging and host adapters, not a promise that its storage, inference, or lifecycle choices fit this product unchanged.

## Delivery gates

1. M1 execution is approved using subagents; Task 1 is locally implemented with documented acceptance limits.
2. Build a thin working slice, verifying public Hermes APIs during development.
3. Implement remaining milestones test-first, updating evidence and handoff after each task.
4. Verify Desktop, Dashboard, native chat tools, and release portability separately.

No live install command is provided for this incomplete foundation preview. No service deployment, catalog submission, or release is implied by this repository.
