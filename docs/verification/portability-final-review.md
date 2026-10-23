# Final portability adapter/UI review

**Verdict: REQUEST CHANGES at the immutable candidate. Two Important findings; no Critical finding reproduced.**

- Candidate: `4f7b6fb1b04018e4844fb54e37f220058356031f`; relative base: `b5e03fc`.
- Reviewed tree: `674aaca418bf5db4bc646c583f578e973682b40b`.
- Scope: common/native/HTTP portability boundaries, cancellation/authority, Data dialog sources and **both actually committed emitted bundles**, asynchronous ownership, transfer/confirmation/reconciliation and public metadata.
- The separate archive/content/store-integrity review is not repeated. Store code was used only to check the public facade, metadata and a failed-receipt/retry seam.
- No production source, tests, index or HEAD was modified. This ignored report is the only repository file written by this review. Synthetic test artifacts were confined to disposable scratch directories and cleaned up.

## I1 — Important: committed bundles omit source ownership fixes; a late export can replace a newer request's artifact

**Locations:** `desktop/plugin.js:943,955,960,984,1032-1033`; `dashboard/dist/index.js:945,957,962,986,1034-1035`. Source fixes that are absent from those outputs: `ui/library-data.js:6,18-19,45-49,97-102,121`. Test blind spot: `tests/test_library_data.cjs:6-14`.

The emitted dialogs are stale, not equivalent to the committed UI sources. Their `discard()` clears `state.task` and `state.busy` even if the outstanding task is an unrelated, admitted export. An old `generate()` continuation still unconditionally assigns `state.artifact`. The source already preserves that independent admission's ownership, retains discarded upload request IDs and strengthens its epoch check, but the actual shipped bundles do not contain those changes.

**Deterministic repro on each committed emitted client:**
1. Select an unrelated backup file. Start export A and hold its POST acknowledgement.
2. Close Data, choose **Discard file and close**, and reopen.
3. The stale bundle incorrectly enables **Check export request** while A's POST is unsettled. Resolve that read-only lookup to ready A.
4. Generate B and resolve B to ready. Now resolve the original POST for A.
5. Click **Download export**. The UI retains B's request ID but downloads A's artifact/bytes.

Observed on both targets: `correctlyHeld:false`, read `/exports/export-fixture?offset=0`, bytes `Synthetic portable bytes — 中文`; expected the newer `/exports/export-new?offset=0` and `Synthetic snapshot B`. The identical adversarial test passed on both targets when the same immutable `ui/` sources were built in memory (`correctlyHeld:true`). No source patch was necessary for that comparison.

**Independent packaging/gate evidence:**
- Frozen build `--check`: exit 1, **Stale: desktop/plugin.js**, **Stale: dashboard/dist/index.js**.
- Frozen `test_library_data.cjs` with its normal in-memory rebuild: **44 passed**.
- The same 44 tests pointed at the **actual committed emitted bytes**, disabling only the fixture's rebuild interception: **40 passed, 4 failed**. Failures on each client: `discarding an unrelated file does not release a pending export admission` and `discarding a file never erases an uncertain upload request identity`.
- The latter failure also proves that discarding/replacing a file erases its uncertain upload identity in the bundles despite the close prompt promising to retain request IDs. The source's `previousUploads` retention is missing from both outputs.

**Required disposition:** regenerate both outputs from the final sources, run deterministic `--check`, and test the exact committed emitted bytes, not only freshly rebuilt replacements. A later controller rebuild may subsume this, but this review has not inspected any later commit and does not assume that it did.

## I2 — Important: authoritative failed restore receipts leave the dialog permanently non-retryable

**Locations:** `ui/library-data.js:78-83,85-93,116-122`; emitted Desktop `1013-1026,1047-1052`; Dashboard `1015-1028,1049-1054`. Relevant backend public contract: `bookmarks/portability/store.py:228-256`; existing recovery regression: `tests/test_portability_store.py:59-69`. Design: `docs/superpowers/specs/2026-10-23-export-and-restore-design.md:32`; general recoverable-error requirement: original product spec `:40`.

Freezing an uncertain or admitted restore is correct. The problem is that the UI never distinguishes that case from an exact request whose **read-only status has subsequently returned `failed`**. `restoreRequest` is never cleared or made explicitly retryable. `restore()` returns whenever it exists, and every file/upload/confirmation/restore control remains disabled even after `state.restore.state === 'failed'`. Closing/reopening preserves the lock. There is no explicit retry action. Reloading drops the selected file and the original request identity, which is the identity the backend expects for owned recovery.

**Repro:** preview a valid backup; confirm and submit; inject a transient storage failure during content commit; use **Check restore request** to read the exact durable `failed` receipt. Both emitted clients then show `Restore failed` while Backup file, Resume upload and preview, confirmation and Restore remain disabled; the only relevant enabled action keeps rereading the failed receipt. A focused assertion requiring any enabled explicit retry control failed on each actual emitted client. The same lock is present in the UI source, independently of I1.

**Real-service seam, not merely a made-up server state:** using immutable Python modules and synthetic scratch storage, injected `StorageError` in `restore_content`; HTTP restore returned 503; exact request GET returned `state:failed`; an explicit native retry with the **same preview ID, digest and request ID** returned `state:succeeded` with the **same restore operation ID**. The UI cannot invoke that supported recovery. No archive/transaction-integrity claim is inferred from this seam test.

**Required disposition:** after an authoritative failed receipt, offer a deliberate same-request retry/recovery path while retaining its immutable tuple and file draft. Do not automatically replay a restore, replace its identity, or unlock it merely on `not_found`, a transport error or an admitted/pending status.

## Public-contract gaps / non-blocking observations

### M1 — Minor: preview still lacks requested descriptive breakdown/integrity wording

`bookmarks/portability/store.py:216-223` returns raw table counts and version; `ui/library-data.js:118` prints those counts as JSON. A real source fixture with one active link plus one trashed image produced `items:2, assets:1`, with no image-item or Trash count and no explicit source-format/integrity-status field. Successful preview implicitly validates integrity, but the user-facing preview does not explicitly say so. The approved design `:30` asks for source format/version, image/Trash breakdown and integrity status; readable labelled metadata would complete that contract. Classified Minor here because this does not itself bypass validation or cause partial restore, and empty-target protection remains effective.

### M2 — Minor: manually inspected ready exports cannot be downloaded from that inspection

`ui/library-data.js:85-91,113,123-126`: a saved export request ID entered after reload can resolve to `ready`, but its result is stored only in `inspection`, not in a download-capable selected artifact. The dialog shows ready/counts and leaves **Download export** disabled; it does not even surface that result's artifact ID/integrity metadata. Both actual emitted clients reproduced this. Regenerating an export is a workaround, but it produces a different snapshot. This is a recovery/usability limitation, not an authorization failure, and the narrow read-only-inspection promise itself is honored.

### C1 — Export metadata gap: already controller-fixed per direct steering, not a new fix request

At this immutable candidate, `ui/library-data.js:114` omits visible filename, byte size, format version and digest, and export metadata in `bookmarks/portability/store.py:133-134` lacks `format_version`. The controller explicitly reported an after-candidate commit adding an Export integrity block, API version metadata and two-host RED→GREEN/API tests. Record this as **already controller-addressed**, not as another outstanding author task. That later commit is outside this immutable review and was not independently re-approved. Do not infer that it also fixes I1/I2/M1/M2.

## Verification and limits

### Verified locally against immutable objects

- CPython **3.14.7**: existing portability native/HTTP and cancellation tests **3 passed**.
- CPython **3.11.14** in the controller's existing disposable interpreter environment: same **3 passed**. An initial bare 3.11 attempt inherited incompatible 3.14 dependencies; rerunning with `PYTHONPATH` unset and the existing 3.11 venv passed. No dependency install was performed.
- Additional 3.14 boundary checks: real failed-receipt/same-identity recovery; repeated HTTP cancellation drains admitted executor work; already-cancelled native owner starts no dispatch; **15** strict/streamed-size/path-identity/query rejection cases; five source-library lookups refused after switching to a different configured target root. These are direct adapter/service checks, not real-host authentication acceptance.
- Actual emitted Desktop ABA probes held upload-create, chunk acknowledgement and preview across A→B→A. All three stopped stale continuations, preserved the correct owner and resumed only explicitly with the same upload identity. No restore POST was sent by these probes.
- Transfer/confirmation/lost-ack/Blob URL cleanup tests ran, with the crucial rebuilt-source versus actual-emitted distinction recorded under I1.
- Targeted added-line adapter/UI security scan found no hardcoded credential, shell/eval/deserialization, raw HTML injection or arbitrary output-path match. Scoped committed diff whitespace check passed.
- Isolated Chromium **fixture**, with actual immutable emitted bundles but synthetic API/public SDK doubles and the native HTML-dialog fallback: both targets measured within viewport at 390×844 and 1440×900, light/dark; no measured horizontal overflow or recorded JS errors; initial focus was inside Data; Escape closed and returned focus to Data. Reverse keyboard traversal returned to the last dialog control. Forward Tab at the native-dialog end temporarily reported BODY, so this is **not** a claim that public-host component focus trapping passed. No host DOM was intercepted.

### Explicitly not verified / not claimed

- No actual authenticated Dashboard host, actual native isolated-host registry, connected packaged Electron, remote/OAuth or real proxy maximum-payload acceptance in this review. The controller said isolated hosts were still bootstrapping; that is not a passing gate.
- Direct ASGI tests deliberately omit host middleware and cannot prove host authorization. The source-library refusal checks establish configured-library ownership, not an independent authentication audit. No new authorization bypass or cancellation-draining defect was reproduced in the inspected portability adapters.
- Screenshot capture timed out and recovered the browser session; the subsequent fixture run yielded DOM/layout/focus measurements only, **not visual screenshot acceptance** or real-host compatibility.
- No model calls, real user data, active plugin installs, live restarts, tracked-file/index/HEAD mutations or external publication.
- No rerun of the full Python234/Node211 provisional gates or official host validator. Those controller counts do not override the reproduced immutable bundle failure.
- No independent approval of the controller's later commits. Final snapshot must be rebuilt and read back after any author fixes.

## Re-run the frozen actual-emitted 44-test check

Run the following Python through `rtk proxy python3 -c` (or an equivalent tool code argument). It uses immutable `git show` reads, disables only the test fixture's regeneration, and writes no production/test/bundle files. Dependencies are read from the existing `node_modules`.

```python
import subprocess
from pathlib import Path
root='/home/irfansofyana/.local/share/hermes-worktrees/hermes-bookmarks/m1'
js="\nconst fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),Module=require('node:module'),vm=require('node:vm');\nconst ROOT=process.cwd(),REV='4f7b6fb1b04018e4844fb54e37f220058356031f';\nconst tracked=new Set(cp.execFileSync('rtk',['proxy','git','-C',ROOT,'ls-tree','-r','--name-only',REV],{encoding:'utf8'}).trim().split('\\n'));\nconst cache=new Map(),realRead=fs.readFileSync,realJS=Module._extensions['.js'];\nfunction immutable(file){const rel=path.relative(ROOT,path.resolve(String(file)));if(!tracked.has(rel))return null;if(!cache.has(rel))cache.set(rel,cp.execFileSync('rtk',['proxy','git','-C',ROOT,'show',REV+':'+rel],{maxBuffer:32*1024*1024}));return cache.get(rel);}\nfs.readFileSync=function(file,options){const value=typeof file==='string'?immutable(file):null;if(value===null)return realRead.call(fs,file,options);const encoding=typeof options==='string'?options:options?.encoding;return encoding?value.toString(encoding):Buffer.from(value);};\nconst immutableModule=function(m,file){if(immutable(file)!==null)m._compile(fs.readFileSync(file,'utf8'),file);else realJS(m,file);};\nModule._extensions['.js']=immutableModule;Module._extensions['.cjs']=immutableModule;\nfunction loadTest(rel,transform=x=>x){const file=path.join(ROOT,rel),m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(path.dirname(file));m._compile(transform(fs.readFileSync(file,'utf8')),file);return m.exports;}\nloadTest('tests/test_library_data.cjs',source=>{const lines=source.split('\\n');lines[6]=' outputs.clear();';lines[7]='';return lines.join('\\n');});"
result=subprocess.run(['rtk','proxy','node','-e',js],cwd=root)
raise SystemExit(result.returncode)
```

Expected at this candidate: **40 pass / 4 fail**, exit 1. Running the normal fixture instead rebuilds its own replacement bundles and produces **44 pass**; do not mistake that for proof about committed outputs.

## Final object readback

The reviewed commit still resolved to tree `674aaca418bf5db4bc646c583f578e973682b40b` at the end. Relevant Git blob IDs:

- `native_tools.py`: `954aecc8bb68797f020191a57627b3e6da59b3f4`
- `runtime.py`: `57c68cce1cfd4fea53503d3391ea04807f12d285`
- `dashboard/plugin_api.py`: `43050af60ede70722c9b623c4ea142a9ef1e0866`
- `ui/library-data.js`: `48d9d026886d5fc21f028b2ac74a8fd23def3c05`
- `desktop/plugin.js`: `ba839b0655e2bbbe6085a8470ced699234a12d57`
- `dashboard/dist/index.js`: `7ecfb9777a3d97912f49069aa35b13229177acd3`
- `tests/test_library_data.cjs`: `2d6ef3ca653d591f86b5f7da6b51cb7e92500617`
