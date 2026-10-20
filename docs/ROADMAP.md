# Delivery roadmap

Status: proposed execution breakdown, based on the approved product direction. Detailed M1 plan awaits review. No product code has shipped.

## Delivery approach

Build vertical slices. Verify uncertain host capabilities during the first development tasks, not as a separate prerequisite research project. Keep each completed slice testable and usable in isolation. M1 is a foundation preview, not a v1 release. Prioritizing imports does not remove required export from v1.

The full product spans several subsystems; do not prewrite hundreds of speculative code steps against unverified host interfaces. M1 has a detailed executable plan. Write subsequent milestone plans against the interfaces and evidence actually produced by their dependencies, preserving every requirement mapped below.

## M1 — Native integration and durable capture

Deliver a valid plugin package, minimal shared library, native save/get/search tools, two UI entrypoints, native Ask Hermes composition/handoff, one durable enrichment path, and one image upload/read path. Start with public-API compatibility evidence. Development stays outside active installation roots.

Exit: both emitted interfaces and native tools exercise the same service. Real-host checks either pass against recorded versions in an approved isolated environment or remain explicit blockers; fixtures alone do not establish compatibility. The native-chat constraint cannot be waived to finish the milestone.

Detailed plan: `superpowers/plans/2026-10-20-m1-native-foundation.md`.

## M2 — Organization and import-first migration

Depends on M1 persistence and contracts.

Deliver nested collections with cycle checks, tags, filters, pagination, favorites/read later, revision-aware edits, trash/restore, and durable normalized-record and bookmark-HTML imports. Chat-driven file migration uses existing authorized Hermes file tools; no source-specific Obsidian/X/GitHub connector is required. Include preview tokens tied to inputs/options, explicit duplicate policy, bounded staging, source provenance, partial cancellation reports, retry idempotency, and job inspection tools.

Suggested ownership: `bookmarks/collections.py`, `bookmarks/imports/{records,html,preview,runner}.py`, `bookmarks/trash.py`, matching native-tool and HTTP adapters, `tests/imports/` with synthetic source fixtures.

Before implementation: write a detailed test-first plan with exact contracts derived from M1. Tests must cover nested HTML, malformed imports, repeated jobs, stale previews, duplicate URLs, unknown metadata, notes already edited by users, and reconciled item counts. Imports do not fetch publishers or invoke AI by default. Source files remain unchanged.

Exit: a chat-originated import and a UI-originated import produce identical validated data, preserve supported notes/tags/provenance, survive restart/cancel/retry, and return accurate reports.

## M3 — Notes, images, and reliable enrichment

Depends on M1 jobs/assets and M2 edits/imports.

Deliver rich-text notes with Markdown shortcuts and inline images, readable saved summaries, safe autosave/conflict handling, image items/covers, thumbnail delivery, durable settings and UI controls, text and vision enrichment, manual/generated provenance, bounded retries, pause/resume, concurrency safety, retention and asset-reference cleanup.

Suggested ownership: `bookmarks/notes.py`, `bookmarks/assets.py`, `bookmarks/settings.py`, `bookmarks/enrichment/{extract,generate,apply}.py`, focused shared UI components and tests.

Detailed plan must specify validated upload byte/dimension limits and quotas, safe asset references, sanitized editor format, conflict responses, SSRF and redirect/DNS handling, settings snapshots, execution ownership, and inference overrides based on public contracts. Tests cover late AI responses versus manual edits, note draft failure/recovery, hostile HTML, unsupported vision, attachment authorization, decompression bombs, upload truncation, and cross-client image rendering. Note images are not automatically analyzed.

Exit: links and standalone images receive configurable AI tags/summaries; manual content survives updates; notes/images work across both clients. No result is labeled successful from a mocked model test alone.

## M4 — Polished library and native conversational workflow

Depends on functioning prior slices; refine shared UI continuously rather than waiting for M4 to begin styling.

Deliver image-led grid/list views, comfortable detail reading, full nested navigation, visible selection/bulk actions, native Ask Hermes context actions, state-preserving native-chat navigation, responsive narrow-screen flows, host theme inheritance, keyboard/touch accessibility, reduced motion, and complete error/empty/pending states.

Use the host's exported primitives and native chat. No duplicate transcript, composer, model picker, or credential form. Include side-by-side composition only where public SDK support was proven; otherwise provide the approved explicit handoff. Record differences between Desktop and Dashboard. Chat uses session-scoped identity/model; enrichment uses its library route.

Detailed plan includes actual emitted-bundle browser tests in both themes and widths, long titles, missing covers, large collections, unsaved notes during navigation, stale responses, focused session changes, existing composer drafts, and double clicks. Capture screenshots and inspect console/layout errors. Expected native chat capabilities are verified on the host, not recreated.

Exit: source/tool changes refresh the UI without losing drafts/selection, and representative tasks are comfortable through keyboard, touch, and native chat. UI review is required; mockups are not.

## M5 — Portable data and release verification

Depends on M2 records/imports and M3 assets/notes.

Deliver bookmark HTML export and versioned lossless bundle export/restore, authenticated downloadable artifacts, explicit format limitations, installation/upgrade/uninstall docs, remote-client instructions, migrations/backups, risk/data-transfer disclosures, and exact-version compatibility evidence.

Suggested ownership: `bookmarks/exports/{html,bundle}.py`, `tests/roundtrip/`, `docs/verification/release.md`, README installation sections only once exercised.

Tests must cover Unicode, empty library, rich notes, nested collections, duplicate filenames, assets shared by items, unsupported bundle versions, traversal/zip bombs, secret exclusion, restore conflicts, partial failure and exact supported-field round trips. Run full suites, official plugin validation, actual host smoke tests, and approved model tests. Verify exact-head CI and published files. No live deployment or release/catalog publication without approval.

Exit: all v1 requirements are covered by recorded evidence. Export is part of release safety, even though imports were built first.

## Spec coverage map

| Spec section | Delivery owner |
| --- | --- |
| 1: shared library, public SDKs, no core changes | M1; regression checks through M5 |
| 2: library UX and native chat | M1 integration; M4 full UX |
| 3: themes | M1 base tokens; M4 complete visual verification |
| 4: items/collections/search/trash | M1 basic items/search; M2 organization |
| 5: notes/images | M1 asset transport; M3 full editor/assets |
| 6: enrichment/settings/jobs | M1 first job; M3 full behavior |
| 7: native tools | M1 basic tools; M2 bulk/organization; M3 notes/assets/settings; M5 export |
| 8: imports/exports | M2 import; M5 export/restore |
| 9: architecture | M1 boundaries; all milestones preserve them |
| 10: security | Every owning task, final M5 regression |
| 11: acceptance | M1–M5 evidence, M5 release gate |
| 12: limitations/compatibility | M1 initial matrix; maintained through M5 |

## Explicitly deferred

Profile-private libraries, semantic search, cross-installation sync, multi-user sharing, browser extension, highlights, full-page archival, PDF/video support, custom appearance overrides, and source-specific vault/social connectors. Deferral never permits dropping supported normalized-file migration or lossless export.
