# Library-first execution decisions

These rulings follow ledger order, including the decisions carried forward from the backend workstream. Each records the user consequence or cost if wrong. They do not change the preserved independent review verdicts.

## Rulings I made

1. implement backend Tasks 2–5 as one disjoint delegated vertical slice while parent owns chat/UI/integration — avoids per-task fresh-agent/reviewer loops while accelerating independent file-owned work — cost if wrong: integration/API mismatch, covered by real-host Task 8 and parent review.

2. combine UI form/navigation scaffolding against the plan's explicit protocol while backend runs — no UI-only persistence or actual-host claims; final service tests remain mandatory — cost if wrong: payload/schema drift requiring integration fixes.

3. prior inline-capture tests now exercise modal capture and the same failed-input, duplicate-guard and delayed-current-query invariants; chat Ask preserves a library search draft rather than a removed inline URL field — approved UX removes inline capture — cost if wrong: old-shape assumptions could hide a lost behavior, addressed by new modal/draft/asset tests.

4. consolidate planned form/detail/nav/item test filenames into test_library_ui.cjs, test_library_async.cjs and test_collection_ui.cjs while preserving old chat/UI regression files — one shared emitted-client helper with explicit route fixtures; all scenarios remain owed, no feature dropped — cost if wrong: coverage omissions, checked against Task 6–8 and final review.

5. use new scoped library-workspace.css and stop emitting obsolete inline-capture library.css — the legacy stylesheet made new selection checkboxes full width, reproduced in both emitted clients — cost if wrong: missing legacy-only style, checked by actual-browser acceptance.

6. use a ResizeObserver-selected public/native modal for narrow collection navigation instead of a CSS-only overlay — real browser Escape failed and the overlay lacked modal focus ownership — cost if wrong: navigation remount loses transient tree expansion on width changes, not library/query/chat/draft data.

7. preserve host tokens but scope away the dashboard SDK action-button tracking/bevel from card headlines and ensure primary hover keeps contrast — real browser reproduced unreadable typography/contrast — cost if wrong: local controls visually diverge from host action styling; both host themes were exercised.

8. retain original legacy tag JSON unchanged at migration/read/metadata-only edits, use first original spelling for the unique normalized association, and rebuild the cache only on later explicit tag mutation/generated replacement — avoids new alias-history schema while preserving accepted legacy data — cost if wrong: old duplicate spellings are not separate editable identities under NFC/trim/casefold semantics.

9. use lossless quoted CSV with untouched original tag arrays rather than expanding this fix into a chip/suggestion redesign — the independent remedy explicitly allows a lossless representation and this prevents unintended provenance changes — cost if wrong: users must quote commas/double embedded quotes; full chip/suggestion UX remains unfinished.

10. resolve conflicts at explicitly reviewed field granularity, preserving local dirty fields and adopting unedited remote fields, rather than adding an automatic text merger — keeps revision checks and explicit human Save without guessing intent — cost if wrong: a deliberately confirmed edited field can replace concurrent content within that same field.

11. reset navigation paging to page zero on revision/query invalidation, merge identity only for page extension — bounded requests refresh counts/names without duplicates — cost if wrong: users must load More again after a save/refresh.

12. image items report not_configured with no extraction job or invented URL — image storage must work before verified vision — cost if wrong: saved images do not receive AI analysis yet.

13. return current Item beside immutable capture Receipt, not a historical Item snapshot — no unapproved notes/history retention model — cost if wrong: receipt lookup shows later item fields, not capture-time fields.

14. preserve per-item association display labels alongside normalized matching identity — avoids replacing original spellings with one global label — cost if wrong: display spelling can differ between items for the same tag identity.

15. name read-only native operations bookmark_library_identity and bookmark_counts — descriptive identities match the implemented service/HTTP contract — cost if wrong: callers must use these names rather than assumed aliases.

16. exhaustive migration/enrichment races remain under the consumed separate boundary review plus author B1/full-suite evidence, not an inferred second certification — the final reviewer intentionally did not duplicate that seat — cost if wrong: untested transaction/race cases may remain before release.

17. connected packaged Electron and actual Desktop Dialog/remote IPC remain an external target gate — no permitted working connection was established, and protocol fixtures cannot prove Radix/native focus behavior — cost if wrong: real Desktop-only failures remain possible; keep draft.

18. fresh actual Dashboard/auth/restart judgment is now backed by the author’s real host/browser/native checks, not ASGI or screenshots alone — no credentials/provider copied, same disposable shared root — cost if wrong: this loopback topology does not prove remote transport.

19. successful provider text/vision, routing/trust/cancellation/charges remain unperformed acceptance gates despite separately approved synthetic calls — credential-free fixtures and protocol events are not inference success — cost if wrong: usable real AI enrichment remains unproven.

20. OAuth/independent-machine/maximum-proxy-payload acceptance remains open — no verified topology has been supplied or exercised here — cost if wrong: authenticated remote or large transfers may fail.

21. add actual reverse Tab containment but do not claim full screen-reader/short-height accessibility certification — browser assertions cover the exercised form, not every assistive technology/content case — cost if wrong: accessibility gaps may remain.

22. rich-text/inline images, configurable vision/settings, import/export and trash/restore stay roadmap requirements outside this revision — approved staged scope has not been widened by UI fixes — cost if wrong: this preview is not the complete v1 product.

23. full reload/exit draft recovery and abandoned-asset GC/quotas remain disclosed non-goals; same-library in-memory remount recovery is required and fixed — avoids silently inventing durable browser-private storage/retention policy — cost if wrong: reload can lose unsaved work and unused staged assets consume disk.

24. later author fixes require exact-head publication/CI evidence, not a rewritten independent PASS; preserve draft/no merge/release/live install — the immutable report cannot certify later commits — cost if wrong: residual author blind spots remain, and deployment still needs separate approval.

25. invoke the Python interpreter directly in portable test fixtures, keeping RTK only around this agent’s shell commands — GitHub does not install local output wrappers and the JSON fixture needs only Python — cost if wrong: test runners must provide python3 or BOOKMARKS_TEST_PYTHON, as documented.

## Deferred minors

- M1 saved-outside-filter notice lacks View item; item persists and filter remains unchanged, but users must find it manually.
- M2 chat.css trailing blank line; original-baseline committed-range diff check fails while working-tree diff check passes; no attributed runtime effect.
- Author formatting note: the preserved original final report has an intentional Markdown hard-break pair of trailing spaces at line3; staged/range whitespace checks flag it. Original bytes/checksum take precedence over cosmetic reformatting; no runtime effect is attributed.
