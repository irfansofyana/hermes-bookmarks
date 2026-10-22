# UX polish review disposition

Independent immutable review `deleg_24791731` at `63bea80cac78ec882737ffc70e27c9aca3a8203c`: **REQUEST CHANGES**, one Important, no Critical. [Original report](ux-polish-final-review.md) is preserved unchanged. This is author verification, not independent re-approval.

## I1 fixed: remounted scoped completion invalidation

Reproduced the exact A → B → A ordering with admitted first Favorite response held until returning to A. Added separate profile and connection regressions in `tests/test_library_bulk.cjs`. Both initially failed with `Returning owner must refresh after acknowledged change`.

The scoped report now increments a completion generation. Its currently mounted matching subscriber observes that generation and refreshes through its own latest callback. The unmounted initiator never invokes its old callback. Existing stop-on-unmount stays set; the remaining mutation is not resumed. B has a different report key and receives no invalidation.

After rebuilding both emitted clients: all **25 focused selection tests pass**, including the two new RED→GREEN remount cases, no extra mutation and no replacement-backend refresh. Full gates: **184 Python tests on each CPython 3.14.7/3.11.14 and 167 Node tests**, deterministic build, Desktop syntax and diff whitespace pass. Existing nonfatal slow-callback diagnostics remain visible. Prior actual Dashboard visual/real-conflict evidence remains scoped to `63bea80`; this lifecycle change was verified with emitted Desktop/React ownership tests, not falsely represented as a live Electron proof.

## Deferred minor

M1: selection tag length currently counts UTF-16 units; a tag containing 41 supplementary emoji is rejected by the UI although the server's Unicode-character limit permits it. Ordinary tags remain usable; no unsafe write or metadata corruption occurs. Defer consistent normalized Unicode counting to the next editing polish task rather than expanding this Important-fix pass. Preserve the reviewer's exact repro for that task.

## Shipping limits

No further speculative review cycle. Publish the existing draft PR, verify exact remote head and CI separately. No active installation, production restart, merge or release. Export/restore, AI settings/text+vision, rich-text/inline images and final cross-client acceptance remain future required work.
