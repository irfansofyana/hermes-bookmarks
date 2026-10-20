# Hermes Bookmarks

A planned standalone bookmark and image library for Hermes Desktop, Dashboard, and native chat tools.

**Status: design stage. This repository contains a draft specification, not an installable plugin.** No runtime implementation or host compatibility is claimed yet.

## Product direction

- One shared library per Hermes backend installation, across agent profiles.
- Raindrop-inspired visual organization: grid/list views, nested collections, tags, favorites, and read later.
- Automatic AI tags and summaries for individual saves, with configurable controls and explicit opt-in for bulk imports.
- Link bookmarks, standalone image items, and rich-text personal notes with inline images.
- Desktop and Dashboard interfaces that follow the user's active Hermes theme.
- Native Hermes tools for capture, search, organization, notes, enrichment, and settings.
- Import-first delivery; export remains required.

## Design

Read the [draft specification](docs/superpowers/specs/2026-10-20-hermes-bookmarks-design.md). Product choices have been discussed; this consolidated document still requires review before an implementation plan is approved.

## Implementation references

- Official Hermes documentation: https://hermes-agent.nousresearch.com/docs/
- Working reference requested by the owner: https://github.com/irfansofyana/hermes-blogwatcher

The official documentation is the integration contract. Blogwatcher is a reference for packaging and host adapters, not a promise that its storage, inference, or lifecycle choices fit this product unchanged.

## Delivery gates

1. Review the written specification.
2. Verify the required Hermes APIs and document capability boundaries.
3. Write and approve an implementation plan and choose its execution method.
4. Build test-first and verify Desktop, Dashboard, and native chat tools separately.

No install command is provided until a working package exists. No service deployment, catalog submission, or release is implied by this repository.
