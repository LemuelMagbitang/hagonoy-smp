# HSMP Project Journal

This is the chronological working record of substantive HSMP project conversations and state changes. It complements (and does not replace) `PROJECT_MEMORY.md`, which is the concise current-state handoff, and the focused subsystem workflow documents.

## Journal rules

- Add an entry for each substantive HSMP project chat/session, including corrections, decisions, failures, applied patches, test results, and changed priorities.
- Record only what the user actually supplied, what was inspected, or what was successfully changed. Separate confirmed facts from hypotheses and pending verification.
- Record exact relevant paths, commands, component versions/builds, test names/results, and whether an operation was plan-only or affected the live server.
- When a phase is completed, update its status in `PROJECT_MEMORY.md` and mark the journal entry complete; preserve history rather than silently deleting useful evidence.
- When an instruction or design changes, update the current workflow document and mark the old instruction superseded. Remove genuinely obsolete operational guidance only when no longer needed; do not erase the audit trail.
- Never store passwords, API tokens, SSH private keys, recovery codes, or other secrets.
- Never make a GitHub source-code commit/push unless explicitly authorized. User-requested memory/documentation maintenance is tracked separately from source-code changes.

---

## 2026-11-13 — Core updater continuation, Geyser download failure, central cache, and active-host routing

### User direction and corrections

- The active workstream returns to finishing the core Paper/Geyser/Floodgate updater. VPN/firewall work is deferred.
- Preserve the user's corrected version history: the server was on Minecraft 26.1 before its successful migration to Minecraft/Paper 26.3. Earlier references to 1.21.x as the previous live version were mistakes.
- Keep the workflow focused and finish one workstream at a time.
- The user requires the GitHub project memory to be maintained throughout substantive HSMP conversations, with current instructions, outcomes, pending work, and retired/superseded guidance kept accurate.
- The user clarified that `D:\Hagonoy-SMP\server-update-downloads` is the designated central update-artifact cache, visible in WSL at `/mnt/d/Hagonoy-SMP/server-update-downloads`. Do not use or assume `C:\Users\lemue\Downloads` for HSMP patch/artifact instructions.
- The user added a required behavior: before update or artifact transfer/replacement, the tool must determine whether the canonical server is active on Ubuntu or Windows and route every operation to that host. Do not hard-code Ubuntu. If host state is ambiguous or conflicting, abort safely.
- Host synchronization semantics: pull means Ubuntu -> Windows; push means Windows -> Ubuntu. The server tree is copied to make the destination match the authoritative source. The update-artifact cache is outside the server tree and must remain separate.
- Native Minecraft commands/datapack functions/dialogs/command blocks are future in-game feature candidates. VPN/firewall and account-authentication implementation are deferred; preserve TLauncher/offline-mode compatibility as a future requirement.
- The user mentioned intending to delete the duplicate `VanillaTweaks-26.3.zip` in favor of the original website bundle `VanillaTweaks_d831085_UNZIP_ME.zip`; no deletion was confirmed.

### Verified command results

1. The live core update was attempted with `./hagonoy update --execute`.
2. The run checked Windows canonical listeners (0 Java TCP listeners and 0 Bedrock UDP endpoints), then targeted Ubuntu:
   - Minecraft 26.3
   - Paper current build 244, target build 249
   - Geyser target 2.12.1 build 1302, artifact `Geyser-Spigot.jar`
   - Floodgate already current at 2.2.5 snapshot/build 141, official SHA-256 matched
3. Paper 249 downloaded (55,281,059 bytes) and passed the expected SHA-256:
   `4c734aeb4da98845934af1e5481f0df7c80ad3ca50d272319ffe2b0e8a187c8a`.
4. Geyser build 1302 download failed with HTTP 404. The lifecycle wrapper reported remote exit 1 and explicitly did not force-kill or attempt state rollback. Failure occurred during download/staging, before graceful shutdown, live JAR replacement, or restart. The update is NOT complete.
5. Read-only `./hagonoy update --plan` subsequently succeeded and again planned Paper 244 -> 249, Geyser build 1302, Floodgate current. It performed no download, shutdown, JAR replacement, restart, or manifest change.
6. User applied the focused Geyser URL correction to the WSL checkout. Output:
   - `[UPDATED] bin/hagonoy-generation (uses API download key 'spigot')`
   - `[ADDED] tests/dual-geyser-download-key-check.py`
   - `[DONE] GeyserMC download-key correction applied.`
   - Safety output confirmed manager source/tests only; no server process, JAR, plugin, world, datapack, or backup was touched.
7. The regression suite and existing focused updater/Paper suites have NOT yet been rerun after applying that patch. The prior attempt to run `tests/dual-geyser-download-key-check.py` occurred before the patch had been applied and failed because the file did not exist at that time. Re-run now.

### Code/design findings to carry forward

- The Geyser 404 was caused by building the official API download URL using the artifact filename (`Geyser-Spigot.jar`) instead of the API download key (`spigot`). The patch changes the URL to use the API key.
- The update-artifact cache is a user-specified system requirement, not just an optional downloads folder. The updater must query latest official releases automatically, download and verify artifacts into that central D: folder, atomically replace old cached artifacts only after verification, then transfer/re-verify/deploy to the active host.
- An inspection of the GitHub default branch's current dual-lifecycle implementation showed that it checks Windows is stopped and then routes lifecycle/update to Ubuntu unconditionally. The current update plan also says `Target: Ubuntu canonical server` and `Windows staging is excluded`. That is not host-agnostic detection. The user's new active-host routing requirement is therefore a known implementation gap.
- GitHub default branch content is not necessarily identical to the user's current WSL checkout. Keep the memory update separate from source-code patches and do not claim a source patch was pushed or merged unless verified.

### Next required work

1. Re-run compilation, the new Geyser download-key regression test, and all targeted core/Paper API, plan, and execution suites.
2. Run `./hagonoy update --plan` and examine the selected host, current versions, artifact cache destination, and transfer plan.
3. Implement/test dual-host active-server detection using manifest identity/state, tmux, Java TCP, Bedrock UDP, process/canonical directory, and reachability. Exactly one valid active host must be confirmed; both, neither, unknown, unreachable, or conflicting evidence must fail closed.
4. Integrate `/mnt/d/Hagonoy-SMP/server-update-downloads` into the artifact download/cache/transfer/deployment flow.
5. Only after these gates pass, request/receive explicit live-update authorization, execute the update on the detected active host, and verify a healthy runtime.


### GitHub memory library maintenance — 2026-11-13

The following memory-only documentation changes were written to the repository's `main` branch in response to the user's standing instruction to maintain project memory across substantive HSMP chats:

- Created `memory/README.md` as the memory-library index and authority/maintenance guide (commit `1b6b264d75b15e447433732dae48541b2d5baaa3`).
- Created `memory/CORE_UPDATER_WORKFLOW.md` with managed scope, D: artifact cache, host-detection requirements, push/pull semantics, failure state, and next verification gates (commit `b7a2fb6b56290f5d742a338992bc748c1dd161d3`).
- Created `memory/PROJECT_JOURNAL.md` as this chronological record (initial commit `db79e9176b2357e26b3a1ca1618b49c06b10c82c`).
- Updated `memory/PROJECT_MEMORY.md` to correct the pre-migration version from 1.21.x to 26.1; supersede stale active-focus notes; record the active updater status, failed Geyser download, applied local patch, central cache, host-routing requirement, and current next steps (commits `a9ae10639002d763b68828b6d68141a301069387` and `54ebd789b012f7cb9551eb10ea242afb87d64803`).
- Updated `memory/DATAPACK_WORKFLOW.md` to mark datapack work as a separate, currently deferred workstream while preserving its confirmed deployment history (commit `50f5efea6272e7e3036b136f1b108cc27268a73e`).

These commits changed memory/documentation only. They did not push the user's local WSL source patch, alter either live server, deploy any artifact, change a datapack, or create a backup.


## 2026-11-13 — Geyser download-key regression test fixture diagnosis

- User supplied a traceback where dual-geyser-download-key-check.py expected build 1302 but received URL for build 1802.
- Inspection of the exact patch bundle showed the regression test replaced fetch_geysermc_default_builds() with a fake that returned both default build 1302 and experimental build 1802. The real helper contract returns default-channel builds only; the production selection routine's max() therefore selected the highest supplied entry as designed.
- Diagnosis: invalid test fixture/mocking boundary, not proof of a production channel-filter defect. Existing dual-core-update-api-check.sh is responsible for testing experimental-channel filtering in the real helper.
- Prepared hsmp-geyser-test-fixture-fix.zip, a test-only correction removing the experimental entry from that mock. The apply script was tested on a temporary copy and Python compilation succeeded. Not yet applied to the user's WSL checkout, and the actual test has not yet passed.
- No production code, live server, JAR, plugin, world, datapack, or backup was changed by this diagnostic patch preparation.
- Immediate next step: user downloads the test-only patch to D:\Hagonoy-SMP\server-update-downloads, applies from WSL, and reruns the new test plus existing focused updater/Paper suites.


## 2026-11-13 — Geyser fixture fix passed; core API suite now fails

- User applied the test-only fixture correction from `D:\Hagonoy-SMP\server-update-downloads\hsmp-geyser-test-fixture-fix.zip`.
- Apply output: only `tests/dual-geyser-download-key-check.py` updated.
- `python3 -m py_compile bin/hagonoy-generation` passed.
- `python3 tests/dual-geyser-download-key-check.py` passed both URL assertions: Geyser build 1302 and Floodgate build 141 use API download key `spigot` in `/downloads/spigot`.
- The subsequent `&&` chain stopped in its first suite, `bash tests/dual-core-update-api-check.sh`, with `File "<stdin>", line 48, AssertionError`. All later suites in the chain were skipped. Exact assertion is unknown; no diagnosis should be guessed. Next action: inspect the test around its embedded Python line and run with `bash -x`.
- No live update was attempted; no server process, live JAR, plugin, world, datapack, or backup was changed by these tests.
- User added a deferred cleanup requirement: after the server update is complete and verified, clean unnecessary files outside the structured Windows/Ubuntu server directories, including obsolete patch artifacts in `D:\Hagonoy-SMP\server-update-downloads`. Inventory and classify first; preserve required originals, current artifacts, rollback/recovery material until safe, and manager/server files. No deletion now.

## 2026-11-13 — Core API test failure precisely identified

- User supplied `nl -ba tests/dual-core-update-api-check.sh | sed -n '1,150p'` and `bash -x tests/dual-core-update-api-check.sh`.
- The embedded Python heredoc starts at shell line 4; therefore traceback `File "<stdin>", line 48` points to physical shell file line 52.
- Physical line 52 asserts that the Geyser metadata URL ends in `/1300/downloads/Geyser-Spigot.jar`. This is an obsolete pre-fix expectation. The production updater now constructs the correct official API route ending in `/1300/downloads/spigot`.
- The preceding build-selection assertion (physical shell line 48) is not the failing assertion. No production code or release-channel filtering needs changing for this failure.
- Next: perform a guarded test-only replacement of the expected URL suffix, then run compilation, Geyser regression, core API/plan/execution and Paper API/plan/execution suites in a fail-continue batch to collect all results in one pass.
- User has set a two-day target for this maintenance/update work and asked for quicker, focused execution. Avoid additional discovery loops and sequential tests where a single batch can provide the same evidence.
- No live server operation or server-file modification occurred during this test diagnosis.


## 2026-11-13 — Core updater regression batch fully passed

- User corrected the single stale URL expectation in `tests/dual-core-update-api-check.sh` from `/1300/downloads/Geyser-Spigot.jar` to `/1300/downloads/spigot`, guarded to require exactly one replacement.
- User ran a fail-continue test batch and supplied the complete result. All nine checks passed:
  - `python3 -m py_compile bin/hagonoy-generation`
  - `python3 tests/dual-runtime-version-probe-check.py`
  - `python3 tests/dual-geyser-download-key-check.py`
  - `bash tests/dual-core-update-api-check.sh`
  - `bash tests/dual-core-update-plan-check.sh`
  - `bash tests/dual-core-update-execution-check.sh`
  - `bash tests/dual-paper-update-api-check.sh`
  - `bash tests/dual-paper-update-plan-check.sh`
  - `bash tests/dual-paper-update-execution-check.sh`
- The tests validated default-channel selection, Geyser/Floodgate API download-key URLs, artifact checksum verification, managed installed-plugin identity, plan-only invariants, no missing-component installation, combined transaction behavior, and rollback/recovery.
- The mock readiness/version failure messages were deliberate negative-path tests; both execution suites passed their recovery assertions.
- This was a local source/test operation only. No live server, JAR, plugin, world, datapack, or backup changed.
- The live update remains incomplete. Previous real execution downloaded and verified Paper 249 but failed on Geyser HTTP 404 before shutdown/replacement/restart. No new live readback has been supplied.
- Next work is a focused implementation pass for the user's required central cache (`D:\\Hagonoy-SMP\\server-update-downloads`) and automatic Ubuntu/Windows active-host routing. Then batch tests, fresh plan, explicitly approved live update, and live health verification.
- User reaffirmed the two-day completion target and requested fewer loops and faster execution. Do not repeat broad discovery or serial test cycles; do not bypass the central cache, verified host detection, artifact validation, or rollback safety.


## 2026-11-13 — Server-running acceptance criterion reaffirmed; source bundle pending attachment

- User emphasized that all Minecraft server changes/updates must preserve a healthy operational server. The server may be stopped only when required for safe maintenance and must be running again afterward so that functionality can be tested.
- Acceptance criterion recorded: preflight, release discovery, downloads, checksum/integrity/compatibility verification, and remote staging happen while the server remains online. Only then stop gracefully, apply the verified managed artifacts, restart the same positively identified host, verify Paper/Geyser/Floodgate runtime versions and readiness/connectivity, and rollback/restart the original set if verification fails.
- A successful maintenance run must leave exactly one canonical host running and the other stopped. Do not report completion after JAR replacement alone. Never force-kill Java as a routine step or accept a stopped server as success.
- User supplied SHA-256 `bc9f4df991079266ba1957f16ac6bae13ea82cbc304696f1a59a9d365da288ce` for `/mnt/d/Hagonoy-SMP/server-update-downloads/hsmp-updater-current-source.zip`.
- The actual ZIP bytes were not present in the current assistant runtime's `/mnt/data` and were not attached in the conversation. The supplied digest is noted but has not been independently verified; no source inspection or patching from that archive has occurred.
- Next: attach the ZIP itself (or upload it into the conversation) so its digest and exact WSL source can be inspected. Then implement the central-cache and active-host routing requirements against those exact files in a consolidated pass, batch tests, run a read-only plan, and only then proceed to explicitly approved live update and post-update health verification.

## 2026-11-13 — Verified source bundle inspected; central cache and host-routing gaps confirmed

- User ran a read-only archive inspection in WSL and confirmed the ZIP SHA-256 matches the supplied value: `bc9f4df991079266ba1957f16ac6bae13ea82cbc304696f1a59a9d365da288ce`.
- Archive file listing included `bin/hagonoy-dual-lifecycle`, `bin/hagonoy-generation`, `config/dual-host.conf`, tests, and only the root two-line `hagonoy` shim. It did not contain `bin/hagonoy`, which is the real command dispatcher. Therefore the complete update command route is not yet available for patching.
- The printed `bin/hagonoy-dual-lifecycle` confirms it requires Ubuntu SSH settings, checks that Windows is stopped, and then unconditionally invokes the Ubuntu remote helper. It prints Ubuntu as the target and says Windows staging is excluded.
- The printed `bin/hagonoy-generation` confirms `update_core_server()` requires the live generation host to be Ubuntu and hard-codes Ubuntu in runtime verification. Some lower-level start/stop/runtime functions have Windows support, but the combined update operation does not pass host through its full execution/rollback path.
- The core update downloads into temporary staging files adjacent to the live server JAR/plugin JAR destinations. It does not first update the central artifact cache at `D:\\Hagonoy-SMP\\server-update-downloads` / `/mnt/d/Hagonoy-SMP/server-update-downloads`.
- All nine focused updater/Paper/Geyser tests passed in the user's latest batch. They do not prove central cache or host-agnostic routing behavior.
- No live server or server files were changed by this inspection. Do not run live update until both gaps are corrected and tested.
- Next: inspect the exact current `bin/hagonoy` dispatcher and the AST-extracted relevant generation helper functions; then prepare a consolidated, scoped change.

## 2026-11-13 — Dispatcher and helper expose exact host-routing defects

- User supplied the WSL `bin/hagonoy` dispatcher and source for `verify_running_server`, `start_managed_server`, `stop_managed_server`, `verify_core_update_runtime`, `update_core_server`, and CLI/main in `bin/hagonoy-generation`.
- The dispatcher routes regular `./hagonoy update --plan|--execute` to `bin/hagonoy-dual-lifecycle update`. A separate duplicate `update)` case later in that shell case is unreachable.
- Existing generation code has Windows process verification, batch startup, and Windows listener checks in selected lifecycle functions; however, the combined core updater remains Ubuntu-only. It requires manifest host ubuntu, hard-codes Ubuntu in runtime verification, and omits host arguments in stop/start/rollback calls.
- The coordinator checks that Windows has no tmux session/listeners and then always sends update to Ubuntu; it is not host-agnostic.
- The core update downloads next to live JAR/plugin targets instead of using the central cache.
- The ZIP omitted `bin/hagonoy-dual-status` and `bin/hagonoy-dual-windows-lifecycle`, which must be inspected before completing the single-source-of-truth host detector.
- Nine core updater regression suites are passing. These tests do not cover central cache or active-host routing. No live server or server files were changed during this inspection.


## 2026-11-13 — Existing dual-host status and lifecycle scripts inspected

User supplied the current WSL contents of bin/hagonoy-dual-status, bin/hagonoy-dual-windows-lifecycle, bin/hagonoy-dual, plus selected generation-helper functions.

### Confirmed findings

- bin/hagonoy-dual-status counts Windows canonical TCP/UDP and staging TCP/UDP listeners, and probes the Ubuntu tmux/TCP/UDP state over SSH. However, canonical RUNNING/STOPPED classification uses only tmux-session presence plus Java TCP count; Bedrock UDP is printed but not enforced. It does not inspect generation manifests, ancestry/IDs, Java process owner/identity, or canonical process working directory.
- bin/hagonoy-dual-windows-lifecycle checks Ubuntu's generation manifest is stopped, Ubuntu tmux is absent, and Ubuntu TCP/UDP listeners are absent before a Windows lifecycle operation. It explicitly starts/stops Windows with --host windows, verifies the Windows stopped manifest on stop, and then calls dual status. This is a host lifecycle guard, not a two-host active selector.
- bin/hagonoy-dual has a backup preflight selector. Its Windows and Ubuntu state helpers are too lightweight for updater authority (session can classify as RUNNING without a full process/runtime/manifest proof).
- bin/hagonoy-generation select() is for ignition/selection among STOPPED manifests. It fails if either manifest is not stopped; for two stopped manifests it uses generation numbers plus ancestry, and for equal IDs explicitly states byte-for-byte equality is not proven. It must not be reused to determine the currently active server.
- verify_running_server_windows() confirms a unique TCP listener owner with Java executable and server.jar command line, Bedrock UDP, tmux session, canonical tmux pane path, and runtime versions. It does not independently confirm the Java process's own current working directory. verify_stopped_server() checks manifest state, tmux absence, and listener absence, but its Ubuntu branch checks TCP only; the Windows branch checks TCP and UDP.
- Conclusion: updater active-host detection must be a new dedicated, read-only, fail-closed preflight. It must combine host reachability, manifest identity/state, generation evidence, tmux, Java process/listener identity, Bedrock UDP, and canonical process directory. It must require exactly one fully verified RUNNING host and one fully verified STOPPED host, and recheck before stop/replacement. Existing status and stopped-generation selection logic are insufficient.
- This inspection does not change the confirmed result of the prior nine passing local tests; those tests do not cover this detector or the D: central cache.
- No source patch, live server operation, JAR/plugin/world/datapack change, backup, or cleanup was performed in this inspection.

### Next action

Inspect the generation manifest loader and the full generic running-server verifier so the detector can reuse validated manifest schema and host-specific process checks rather than duplicating or weakening them. Then implement the detector and central-cache/host routing in one scoped patch and add dedicated tests.


## 2026-11-13 — Generation manifest loader and generic running verifier reviewed

User supplied the WSL implementations of load() (lines 28–76) and verify_running_server() (lines 288–428).

- load() verifies generation manifest schema_version == 1, allowed state (running/stopped), positive non-boolean generation integer, non-empty generation_id, valid unique ancestry, ancestry length exactly generation - 1, and correct parent_generation_id linkage. It does not validate host as part of the manifest schema loader.
- The Ubuntu generic running verifier supports host dispatch, canonical server directory resolution, optional manifest-absence adoption check, strict tmux session name, canonical tmux pane directory verification, unique Java TCP listener PID, Java executable check, /proc PID cwd equality with canonical server directory, and Paper/Minecraft runtime discovery from logs or fresh console query.
- For existing managed server updates, the default require_manifest_absent=True must not be mistakenly used as the normal running-state authorization check. The new active-host detector must validate the existing manifest separately and invoke appropriate running verification without weakening adoption protections.
- The Windows branch delegates to verify_running_server_windows(). The earlier supplied body verifies Java listener ownership/process executable and server.jar command line, Bedrock UDP presence, tmux session and canonical pane path, and runtime versions; it does not independently read the Java process working directory. The existing stopped verifier's Ubuntu branch checks TCP only, whereas its Windows branch checks both TCP and UDP.
- Design direction: preserve/reuse load() validation, then require explicit matching host/state/generation ID; strengthen UDP and Windows working-directory verification; fail closed unless exactly one host is fully RUNNING and the other fully STOPPED; recheck before stop/replacement.
- No code was patched, no live server operation occurred, and no server files changed during this inspection. Existing nine focused tests remain the last confirmed local test batch; they do not exercise these additional requirements.
