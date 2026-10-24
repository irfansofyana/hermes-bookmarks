**REQUEST CHANGES** for `4def7bed..37e5e5ae`. Two Important findings; no Critical findings. Review remained read-only; working tree is clean.

1. **Important — Inactive migrated jobs indefinitely block explicit enrichment.**
   [bookmarks/enrichment_requests.py:74](https://github.com/irfansofyana/hermes-bookmarks/blob/37e5e5ae378d9050ef0796293a696b748645c844/bookmarks/enrichment_requests.py#L74)

   Admission rejects any pending/running job for the item, while the updated worker claims only jobs owning the current pointer and generation. Consequently, an inactive pending job is never consumed and continues rejecting every new request.

   **Reproduced entirely in memory:** create a schema-5 item at revision 8 pointing to a pending revision-1 job, then run the actual migrations. `claim()` returns `None`; explicit enrichment at revision 8 raises `ConflictError`. This matches the inactive-migration scenario already covered by the changed tests, but follows it through admission.

   **User effect:** legacy items cannot be deliberately reprocessed through the new API. Refreshing or restarting does not resolve the conflict.

   **Minimal fix:** reconcile inactive jobs and stale item pointers without provider execution, or consistently restrict admission and UI activity decisions to the current owned generation. Preserve the approved claim-skipping behavior.

2. **Important — Both UIs reject valid migrated-job status responses.**
   [ui/library-enrichment.js:22](https://github.com/irfansofyana/hermes-bookmarks/blob/37e5e5ae378d9050ef0796293a696b748645c844/ui/library-enrichment.js#L22)

   `validateJob()` requires a positive integer `settings_revision`. Legacy snapshots intentionally produce `settings_revision: null`, which the public projection returns unchanged.

   **Reproduced:** migrated the committed `enrichment-v10.sqlite3` fixture into an in-memory database. Its running, pending, cancelled and succeeded jobs all return null settings revisions. Passing that shape through the actual UI validator throws “Processing status identity or fields are invalid.”

   **User effect:** opening an existing enriched item sets `statusUnknown`; processing status cannot be displayed, active jobs cannot be cancelled from the panel, and regeneration controls remain unavailable. Checking again repeats the rejection.

   **Minimal fix:** accept null revisions for legacy job status and display an explicit legacy/unknown revision label. Retain strict positive revisions for new admission receipts. Add emitted-bundle regression coverage for migrated active and terminal jobs.

**Strengths:** transactional settings/admission boundaries and receipt-first lookup are well structured. In-memory checks confirmed original receipt recovery after item/settings changes, manual-summary conflict reporting, and tag suppression. The actual v1 fixture’s content restored into schema 11 with live settings/owner unchanged and legacy summary ownership preserved.

**Rulings:** I accepted the supplied controller rulings, full-field imported-intent replacement semantics, explicit-Start lifecycle behavior, and adjusted assertions implementing approved behavior. I did not reopen consumed portability findings. Rich text, inline images and connected Electron/full remote acceptance remain deferred product gates.

**Coverage limits:** the three options tests passed; both shipped bundles passed syntax checks and contain the exact reviewed settings/enrichment sources. Diff whitespace checks passed. `test_settings.py` encountered eight setup errors because the sandbox permits no temporary database files. Both UI test files failed to load because React is absent; nothing was installed. Full suites, real providers, browsers, authenticated host behavior and filesystem crash guarantees were not independently verified here. The reported controller suite counts remain controller evidence.