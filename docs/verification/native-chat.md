# Native chat handoff

Implementation uses public Desktop SDK only: `host.profileRoutes`, connection-qualified `focusedSessionOwner`, `focusedStoredSessionId`, `openSession`, `composer.getDraft` and acknowledged `composer.insertText`.

Ask Hermes stages bounded bookmark IDs and an explicit user gesture appends references to the selected native draft. It never submits, replaces a draft, sends notes/images, or implements a transcript/model picker. Matching requires connection + backend profile + stored session. Changes during lookup abort, missing registry routes fail closed, and a false insertion acknowledgement is surfaced. getDraft can return persisted text for an unmounted composer; it is not proof of a mounted surface.

The current Dashboard SDK has no supported context/draft API. Its Ask Hermes action remains disabled with an explanation. This is an acceptance blocker, not parity. No terminal injection or custom chat workaround is included. Actual Desktop installed-build and native Markdown/tool/approval/history behavior also remain unverified.

Test-first: `node --test tests/test_chat_handoff.cjs` initially failed six tests because the adapter did not exist; after implementation all six pass. They cover exact targeting, append consent, focus change, source identity, missing capability/route, mutation acknowledgement and invalid selections. Whole suite: 10 Node tests and 40 Python tests pass; emitted build and Desktop syntax checks pass. These are host-shaped doubles plus real React tests, not a real-host chat turn.

Library view state retains draft URL, search and scroll across native navigation within the mounted plugin generation; cross-connection restoration and full navigation UX receive additional coverage in M4. No paid inference or live installation was performed.
