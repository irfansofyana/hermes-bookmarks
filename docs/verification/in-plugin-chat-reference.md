# In-plugin chat reference: Hermes Learning

## Corrected product boundary

Bookmarks needs a conversation UI while the plugin stays open. Reusing Hermes execution underneath does not mean navigating to the usual Hermes session-chat screen. The owner identified `irfansofyana/hermes-learning` as the implementation reference; source inspection confirms that it implements this UI/backend split. This replaces the earlier handoff-first interpretation, not the restrictions on core edits, private imports or a new agent runtime.

## Inspected source

Learning checkout: `main`, commit `2a9f2e2fd9c5007996dc7a6b7f16f50a306a6c10`, clean during inspection. The older `spike/cross-client-learning` checkout is not the relevant implementation. Inspected UI, hook, controller and both transport/entrypoint files matched the installed Learning package byte-for-byte. No Learning files, user records or configuration were changed.

| Layer | Source evidence | What it does |
| --- | --- | --- |
| Plugin chat UI | `ui/src/TutorPanel.jsx:16-30` | Own transcript, Markdown rendering, composer, Stop, reconnect, tool activity, plans and permission/clarification controls. |
| React binding | `ui/src/useTutor.jsx:3-8` | Binds the panel to a reusable conversation controller and disposes it on unmount. |
| Hermes conversation | `ui/src/tutor-session.mjs:64-85,109-132,209-236,269-297` | Creates/resumes durable Hermes sessions, submits prompts, reads history, forwards actual permission decisions and interrupts the owned session. |
| Desktop adapter | `ui/src/desktop.jsx:6-26` and `ui/src/tutor-transport.mjs:25-63` | Uses public `host.request` / `host.onEvent`; checks profile/connection and owns only its subscriptions. |
| Dashboard adapter | `ui/src/dashboard.jsx:4-9` and `ui/src/tutor-transport.mjs:66-189` | Uses SDK `buildWsUrl('/api/ws')` for its authenticated gateway connection and JSON-RPC/event transport. It does not require the usual chat composer API. |
| Domain integration | `ui/src/LearningApp.jsx:38-43,55-86` and `ui/src/tutor-session.mjs:7-35,125-132` | Supplies selected learning context, stores the durable session binding through Learning's service, and refreshes domain data after actual tool effects. |

Concrete gateway operations include `session.create`, `session.resume`, `prompt.submit`, `session.history`, `session.activate`, `session.interrupt`, `request.answer` and `clarify.lock`. The web adapter advertises `client.capabilities` with `server_requests: true`, correlates responses, and rejects interactive requests for sessions it does not own. It obtains authentication through the SDK rather than storing provider credentials.

## What Bookmarks should reuse

Use the same separation: **Bookmarks conversation panel → scoped session controller → host-specific gateway transport → real Hermes agent/tools**. Do not implement another model/tool loop and do not make native draft handoff the primary workflow.

Adapt the context and persistence to Bookmarks: selected item/collection references, explicit profile/backend/session ownership, and normal bookmark tools. Do not import Learning as a mandatory runtime dependency, copy its teaching prompt, or carry over learning-assessment consent/job semantics. Shared installation library data does not imply shared conversations across unrelated profiles.

Preserve the reference's important behavior: explicit Send, durable session IDs separate from runtime IDs, stream/session/profile guards, history restore, actual tool/plan events, scoped approval/clarification, Stop, stale-await generation checks and uncertain-submit reconciliation. A lost response must not trigger automatic prompt replay. Keep chat provider/session settings separate from library enrichment settings.

The library and chat remain inside Bookmarks. Wide side-by-side presentation and narrow in-plugin switching are proposed layout defaults; detailed thread/context persistence and component choices belong in the corrected design. Native tools remain usable independently in ordinary Hermes chat too.

## Verification and limits

Executed against the inspected Learning source:

```sh
rtk proxy node --test ui/test/tutor-transport.test.mjs ui/test/tutor-session.test.mjs
```

Result: **58 tests passed, zero failures**. Coverage includes create/bind/submit, restore, streaming, tools/plans, scoped approvals, Stop, profile mismatch, stale async work, uncertain delivery, authenticated transport, disconnect, heartbeat and explicit reconnect. These are Learning's focused controller/transport tests using boundary doubles, not a new live-provider or Bookmarks UI acceptance run.

This is a verified reference architecture, not implemented Bookmarks chat. Target-version gateway authentication/event behavior, actual emitted Bookmarks UI, real-provider execution and Desktop connectivity still need their own evidence. In particular, these source/unit results do not prove every OAuth/remote topology. No active installation, service restart, model request or publication was performed for this inspection.
