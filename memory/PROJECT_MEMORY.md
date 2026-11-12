# HSMP Project Memory

Last updated: 2026-11-13 (Asia/Manila)

This is a continuity aid, not the project authority. The user's explicit decisions and clarifications are authoritative. Keep this file factual and current; never let older notes or legacy scripts override the user's direction.

## Mission

- The goal is a healthy, reliable HSMP server that returns to a working, verified state after maintenance. Brief downtime is acceptable when required; correct recovery and a verified running server are the objective.
- The server was on Minecraft 26.1 before its successful migration to Minecraft 26.3 / Paper 26.3. The user's earlier references to a 1.21.x live baseline were mistakes. Do not repeat that incorrect history or reopen the completed migration unless the user reports a problem.
- The recurring update/maintenance manager is still being completed. Do not confuse the completed upgrade to 26.3 with completion of the updater.
- Keep work simple, focused, and high quality. No repeated broad audits, unnecessary abstractions, redundant questions, or directory proliferation.
- The user's decisions are the source of truth. The repository is the implementation workspace and version-control record. Legacy scripts are references only, not the authority.
- Separate user-confirmed facts, historical command output, and unverified current state. Never claim local or server changes that were not made.

## Current controlling checkpoint — 2026-11-13

This section supersedes older dated work-focus and immediate-sequence sections below whenever they conflict.

- Active workstream: finish the combined core updater for Paper, already-installed Geyser, and already-installed Floodgate. VPN/firewall and account authentication are deferred. Native Minecraft commands/datapack functions/dialogs/command blocks are future feature considerations, not current work.
- Server history: previous live Minecraft version was 26.1; current migrated version is 26.3. Do not state that the previous live server was 1.21.x.
- Latest user-supplied live plan: Ubuntu was identified as active; Windows canonical had 0 Java TCP listeners and 0 Bedrock UDP endpoints. Minecraft 26.3; Paper 244 -> 249; Geyser 2.12.1 build 1302; Floodgate already current (2.2.5-SNAPSHOT/build 141). This is a historical plan snapshot; always re-probe before execution.
- Latest live execution attempt downloaded Paper 249 and verified its SHA-256, then failed at Geyser build 1302 download with HTTP 404 before graceful shutdown, live JAR replacement, or restart. The live update is NOT complete.
- User applied the Geyser download-key patch in the WSL checkout: `bin/hagonoy-generation` uses API download key `spigot`; `tests/dual-geyser-download-key-check.py` was added and its fixture corrected. Both Geyser build 1302 and Floodgate build 141 regression cases pass.
- The core API test's embedded Python traceback `<stdin>, line 48` was traced to physical shell-script line 52, a stale expected URL ending `/downloads/Geyser-Spigot.jar`. The user corrected it to `/downloads/spigot` (test-only change).
- Latest user-supplied batch result: all nine focused checks passed—Python compilation, Paper 26.3 runtime version-probe regression, Geyser/Floodgate download-key regression, core API/plan/execution suites, and Paper API/plan/execution suites. No failures remain in this targeted batch.
- No live update was performed by the tests. The live update is still NOT complete: Paper 249 previously downloaded and passed SHA-256 verification, but Geyser download returned HTTP 404 before shutdown/replacement/restart. Do not claim newer JARs are installed.
- The next work is implementation, not more repeated discovery: finish central D: artifact-cache integration and host-agnostic active-host detection/routing. The last observed plan was Ubuntu-specific and said Windows staging was excluded; that does not yet satisfy the user's host-routing requirement.
- Central artifact cache: Windows `D:\Hagonoy-SMP\server-update-downloads`; WSL `/mnt/d/Hagonoy-SMP/server-update-downloads`. Use this established location in all HSMP artifact/patch instructions. Never assume `C:\\Users\\lemue\\Downloads`.
- The updater must discover releases automatically, download/verify/atomically refresh this central artifact cache, then deploy only to the active host after confirming whether Ubuntu or Windows is live.
- New required active-host detection: validate both hosts using generation manifests/identity, tmux, Java TCP, Bedrock UDP, process/canonical directory, and host reachability. Require exactly one confirmed RUNNING canonical host and one confirmed STOPPED host. Ambiguous/conflicting/unknown states must abort. Recheck before stopping/replacing. The currently observed wrapper routes to Ubuntu after checking Windows is stopped; this hard-coded behavior does not yet satisfy host-agnostic routing.
- Push/pull semantics: pull is Ubuntu -> Windows; push is Windows -> Ubuntu. The destination server tree should become a verified copy of the authoritative source. Keep the central artifact cache separate from both server directories and do not change it during host synchronization.
- The current failed execution did not apply the live update. The later `--plan` was read-only. Do not claim Paper 249 or Geyser build 1302 is installed.
- GitHub memory is being maintained separately from source-code changes. Do not infer that local WSL patches have been committed/pushed or that GitHub default-branch code matches the WSL working tree. No server-manager source-code push without explicit approval.
- For every substantive HSMP project conversation, update the concise memory, the relevant workflow document, and the dated journal; record confirmed vs pending vs completed status and supersede stale current-focus notes.

## Maintenance responsibilities and order

### 1. Core server updater — current priority

The normal updater is limited to Paper server software, Geyser, and Floodgate. Detect what is installed and update only those managed components. Do not install missing components or update unrelated plugins such as Chunky unless the user changes the scope.

Discover current stable releases from official upstream sources without asking the user to type component names or versions. The Windows update-downloads folder is the designated central update-artifact cache: compare it with upstream releases, download newer verified artifacts into it, atomically replace cached artifacts only after verification, then transfer/re-verify/deploy to the positively identified active canonical host (Ubuntu or Windows). Detect the active host before every relevant transfer or live operation; never hard-code Ubuntu. If host status is unknown, conflicting, unreachable, both active, or both stopped, fail closed. Stage safely; save and gracefully stop only the verified active host; apply; restart that same host; verify readiness and resulting versions; recover/rollback safely on failure. Do not leave the server stopped when safe recovery is possible.

Routine updates must not silently create full TAR backups. A full backup is a separate operation requiring its own explicit authorization. Temporary rollback artifacts are not full backups.

### 2. VanillaTweaks datapack maintenance — next distinct workflow

Datapack maintenance is a separate script/workflow after the core Paper/Geyser/Floodgate updater. Never couple datapack installation or sync to normal `start` or the core software `update` command.

The built-in `vanilla`, `bukkit`, and `paper` entries shown by `/datapack list` are not independent downloadable update targets. Paper is updated as server software. The custom world datapacks currently known are VanillaTweaks packs.

A local datapack manager and manifest were added; 13 VanillaTweaks packs were registered for Minecraft 26.3. Registration/planning is not proof of deployment. Confirm installed state before sync. Do not silently overwrite, remove, prune, or deploy packs. The separate workflow handles compatibility and updates for the approved VanillaTweaks set.

### 3. Host switching and backup utilities — review after the above

Host switching/moving the authoritative server between Ubuntu and Windows, and backup utilities, are separate responsibilities. They are believed to be largely in place, but the user wants to review them after the core updater and datapack workflow. Legacy scripts may inform behavior but are not the main implementation authority.

## Known directory layout

These are the current intended/canonical paths. The user's latest explicit path clarification overrides older folder-preparation scripts and backup-folder names.

**Windows:**
- Live server: `D:\Hagonoy-SMP\minecraft-server`
- Backup vault: `D:\Hagonoy-SMP\server-backup`
- Update downloads/reference staging: `D:\Hagonoy-SMP\server-update-downloads`
- Legacy reference tree: `D:\Hagonoy-SMP\LINUX-HSMP - Emergency Evac`

**Ubuntu:**
- Live server: `/home/leonardodavinci/minecraft-server`
- Backup vault: `/home/leonardodavinci/server-backup`
- Manager checkout previously observed: `/home/leonardodavinci/hagonoy-smp`

**Development/control:**
- User's WSL checkout: `/home/lemuel/hagonoy-smp`
- Dual-host configuration: `config/dual-host.conf`

Windows server and staging paths appear in WSL as `/mnt/d/Hagonoy-SMP/...`. Do not infer a separate native Windows manager checkout; its location has not been established. Do not use the older `hsmp-evac-v2-win-backup` as the canonical backup vault; the user specified `server-backup` on both hosts.

## Current known implementation state (2026-11-12)

- WSL branch last reported: `fix/border-console-pane-and-parser-20261111`. It was not present in the remote branch list checked on 2026-11-12. Do not replace it with stale remote code or assume the worktree is on GitHub.
- The user exported the current worktree diff to `C:\Users\lemue\Downloads\hsmp-current-worktree.patch`; SHA-256: `fa19c46f7b5b8d710bbb7c0cb66ae337d0de8b0a7a36ac40329a1ce859c05a25`. The patch itself has not yet been attached in the active conversation, so the exact current local diff is unavailable for direct editing.
- Previously committed locally (presence on current branch must be confirmed from the patch): `67016c3` (Paper updater uses temporary rollback JAR rather than automatic TAR backup) and `7ca4d97` (world-border console targeting/reply parsing).
- Local datapack additions include `bin/hagonoy-datapacks.py`, `bin/hagonoy-datapacks-remote.py`, `config/approved-datapacks.json`, `tests/datapack-deploy-check.py`, and routing changes in the main/dual-host lifecycle scripts.
- The datapack manager was wired into `start` and `update`; that coupling is unwanted and must be removed while retaining standalone datapack commands.
- Earlier offline shell syntax, Python compilation, datapack tests, and `git diff --check` passed before the latest exported worktree. Do not represent them as fresh tests of the current tree.
- A historical point-build update attempt stopped at a generation/runtime verifier before server shutdown, save/stop, JAR replacement, or datapack deployment. Paper 26.3 build 244 was last observed installed; Paper 249 was downloaded and hash-verified in staging but not installed in that attempt. This does not undo the successful migration to Minecraft 26.3.
- Historical runtime observation: Ubuntu was authoritative, generation 6, Minecraft 26.3, Paper 26.3-244, tmux `mcserver`, port 25565 listening; Windows generation 5 was stopped. Treat this as historical, not live status.

## Historical immediate work sequence (2026-11-12; superseded by the controlling checkpoint above)

1. Obtain and inspect the exported worktree patch so edits target the exact current code.
2. Finish the Paper/Geyser/Floodgate updater: upstream release discovery, installed-component detection, safe update/rollback, readiness verification, and clear progress/errors.
3. Remove automatic datapack work from normal `start` and core `update`; keep datapack maintenance independent.
4. Finish the VanillaTweaks datapack update workflow as the next distinct feature.
5. Run focused tests, then review host-switching and backup utilities.
6. For live maintenance, identify the current authoritative host, run preflight, stop gracefully only when needed, then verify the server is healthy and running again.

## Historical addons/datapack work focus (2026-11-12; superseded by the controlling checkpoint above)

The user explicitly directed that the current session resume the addons/datapack tools now. This is the active work focus, even though the core Paper/Geyser/Floodgate updater remains a separate unfinished responsibility.

The detailed subsystem record is `memory/DATAPACK_WORKFLOW.md`. Read it alongside this project memory before continuing addon/datapack implementation. It records command semantics, safety invariants, target paths, source/staging/transport behavior, runtime verification requirements, recovered-code audit findings, and the follow-up patch status.

Important current distinctions:
- The 13 VanillaTweaks packs were recorded as registered in prior work; the exact manifest in the user's current WSL worktree was not directly inspected in this turn. Preserve it.
- The earlier additive manager patch was recovered from Library material and inspected. Findings about it are not proof that the unshared local WSL worktree has identical file contents.
- The user applied the reviewed datapack follow-up to the WSL checkout on 2026-11-12. Python compilation, datapack fixture tests (including stage and running-runtime checks), and lifecycle shell syntax checks passed. The user's local branch name/head after application has not been freshly recorded here; the exact local diff has not been uploaded to GitHub. The work was not applied to either live server.
- No datapack was deployed, enabled, removed, overwritten, or changed in a live world during this review.

## Conversation-history audit limitation

The user supplied two private ChatGPT conversation URLs marking the start and current end of a long, branched HSMP history. Direct retrieval of those `/c/` URLs was blocked. The accessible Library contains supporting scripts, patches, and pasted terminal-output snapshots, some of which were read to confirm paths and implementation history; these are not a complete transcript of all 23+ branches. Never claim the full history has been read until an accessible conversation export/transcript is supplied.

## Handoff protocol

At each continuation, read this memory together with current conversation context. The user's newest explicit direction wins over stale notes. After substantial work, update this file with verified decisions, state, tests, commits, and next action. Never store credentials, tokens, private keys, or other secrets.


## Latest addons checkpoint — 2026-11-12

Source: command output supplied by the user in the current continuation.

- `./hagonoy addons list` reports 13 approved VanillaTweaks datapacks in `config/approved-datapacks.json`.
- `./hagonoy status` reports Ubuntu LIVE: RUNNING; Windows canonical: STOPPED; Windows staging: STOPPED. The status command explicitly reports read-only behavior.
- `./hagonoy addons plan --host ubuntu` reports `DATAPACK_RUNTIME=RUNNING`, all 13 approved packs as `[ADD]` because each is missing, and `DATAPACK_PLAN=READY`.
- This is a plan, not a deployment. No live-world datapack changes, reload, or enablement have been confirmed.
- Do not run sync based only on this plan output. Deployment remains a separate action requiring the user's explicit authorization.
- Immediate next checkpoint: obtain explicit approval for adding all 13 listed approved packs to the Ubuntu live world; then execute the standalone Ubuntu sync and verify on-disk files plus runtime enabled-pack readback.


## Datapack sync incident — 2026-11-12

Source: complete `./hagonoy addons sync --host ubuntu` output supplied by the user.

- The command planned 13 additions, then reported `[INSTALLED_AND_HASH_VERIFIED]` for all 13 approved VanillaTweaks ZIP files.
- After all file writes and hash checks, the remote helper timed out waiting for Minecraft to confirm `reload`.
- The helper explicitly warned that the command may have run but its result is unverified and pointed to `/home/leonardodavinci/minecraft-server/logs/latest.log`.
- The addons command exited 1 because reload confirmation was inconclusive.
- Established: 13/13 archive writes were reported hash-verified before the runtime timeout.
- Not established: whether reload executed/completed, whether any datapacks loaded, or which packs are currently enabled.
- Treat this as a partial deployment with uncertain runtime state. Do not blindly rerun sync, restart the server, remove packs, or repeat reload until logs and a read-only `/datapack list enabled` query have been checked.
- No full backup was made or requested as part of this operation.


## Datapack deployment verified — 2026-11-12

Source: user supplied live Ubuntu SSH terminal output.

- The standalone command `./hagonoy addons sync --host ubuntu` reported `[INSTALLED_AND_HASH_VERIFIED]` for all 13 approved VanillaTweaks ZIPs.
- The helper then timed out waiting for Minecraft's `reload` confirmation and returned exit code 1. This was a runtime-confirmation timeout, not evidence that the file installation failed.
- The user queried the live Minecraft console with `datapack list enabled`. At 22:26:25 the server answered: 16 datapacks enabled.
- The returned list contains the 3 expected pre-existing vanilla/Paper/Bukkit entries and all 13 approved VanillaTweaks packs. Therefore all 13 custom packs are confirmed enabled in the Ubuntu live world.
- The reload began at 22:22:20 (`Reloading!`). Paper watchdog warnings occurred at 22:22:30 and 22:22:35. Thread dump during resource reload showed the server thread parsing YAML via SnakeYAML from Bukkit `HelpYamlReader` / `SimpleHelpMap.initializeGeneralTopics`. The server later processed the enabled-pack query at 22:26:25, proving it recovered and was responsive then.
- Exact cause of the long HelpYamlReader/YAML parse is not established; do not blame a particular plugin or YAML file without additional evidence.
- Deployment objective achieved: all 13 approved custom datapacks are installed and enabled on Ubuntu. No evidence of Windows deployment; Windows remains outside this operation.
- Follow-up engineering task: inspect local `bin/hagonoy-datapacks-remote.py` reload wait/confirmation logic and adjust it to tolerate genuinely slow resource reloads while retaining a bounded timeout, progress/status, and definitive post-reload `datapack list enabled` verification. Avoid interpreting a missing quick acknowledgement as failure if the reload is still processing. Test this using fixtures; do not cause another live reload just to test the helper.


## Reload-confirmation fix prepared — 2026-11-12

- After reviewing the exact local helper/test excerpts supplied by the user, a guarded patch bundle was prepared for `bin/hagonoy-datapacks-remote.py` and `tests/datapack-deploy-check.py`.
- Intended behavior: accept Paper's `Reloading!` line as request acceptance, then treat the queued `datapack list enabled` response as the post-reload completion barrier; allow up to 360 seconds for that response and print periodic wait progress.
- The test fixture is changed to simulate a delayed enabled-list response and verify that the helper waits and reports progress.
- The bundle was only prepared and its patch anchors were validated against reconstructed excerpts. It has not yet been applied to the user's WSL checkout or run against the full test file.
- No live server command, reload, sync, backup, or world-file change was performed for this tooling fix.

- Bundle packaging follow-up: the initial download was not extracted by the user, so the apply script path was naturally absent. The ZIP was rebuilt as `hsmp-reload-confirmation-fix-v2.zip`; it passes `unzip -t` and now normalizes the edited test file's trailing newlines to prevent the reported `git diff --check` blank-line warning. It is still unapplied to WSL.


## Slow-reload correction applied and tested — 2026-11-12

Source: user-provided WSL command output.

- Applied `hsmp-reload-confirmation-fix-v2` successfully.
- Updated local files:
  - `bin/hagonoy-datapacks-remote.py`, SHA-256 `7220b8bb598f9ff648bd797a00ef7841a69647faa19b391ae808b1f621c75bc7`
  - `tests/datapack-deploy-check.py`, SHA-256 `53dc7dbdffc397b66ac1686059ac051a3fadb52ac8dafb6972d649cc556784ef`
- Python bytecode compilation passed.
- `tests/datapack-deploy-check.py` passed all additive install, registration, staging, runtime verification, slow-reload, and disabled-pack tests. New slow-reload fixture specifically reports that queued enabled-list readback confirmed the new pack and wait progress was reported.
- `git diff --check` completed with no output/error (clean).
- Patch application explicitly made no Minecraft host contact, reload, sync, backup, or world-file operation.
- The local diff has not yet been reviewed in full or committed/pushed. Next: inspect `git diff --stat`, working-tree status, and the focused diff for the two changed files; confirm the code implements the stated bounded wait and final enabled-pack verification exactly. Do not run a live reload to test it.

## Latest test diagnosis and schedule correction — 2026-11-13

- User supplied the full numbered contents of `tests/dual-core-update-api-check.sh` and the `bash -x` traceback.
- The Python heredoc starts at shell line 4, so Python traceback `<stdin>, line 48` maps to physical shell-script line 52, not shell line 48.
- Physical line 52 is the stale URL expectation: `assert metadata["url"].endswith("/1300/downloads/Geyser-Spigot.jar")`. The production updater now correctly uses the GeyserMC API download key `spigot`, so the expected suffix must be `/1300/downloads/spigot`.
- The build-selection assertion at physical shell line 48 is not the failing assertion. The traceback is plain `AssertionError` because the URL assertion has no custom message. Do not alter production release selection or channel filtering for this failure.
- Required next edit is one guarded test-only string replacement in `tests/dual-core-update-api-check.sh`; then run all focused core/Paper tests in a fail-continue batch so every result is collected in one pass.
- User explicitly requires the maintenance work to stay within a two-day update window. Avoid repeated discovery/audit loops and serial one-test-at-a-time cycles. Batch diagnostics and tests, fix concrete blockers only, then finish the live update and post-update health verification.
- No live server, JAR, plugin, world, datapack, or backup was changed by this test failure.


## Operational acceptance requirement reaffirmed — 2026-11-13

- User requires the Minecraft server to return to a healthy, running state after every authorized maintenance/update operation. Server stop is allowed only when necessary for safe file replacement and should be limited to the required maintenance window.
- Completion is not defined by a successful download or JAR replacement alone. The updater must start the same authoritative active host again, confirm runtime readiness, confirm actual Paper/Geyser/Floodgate versions, and perform meaningful health/connectivity checks. If start or verification fails, carry out the tested rollback/recovery path and continue attempting safe recovery until the prior or updated server is running and verified; report honestly if recovery cannot be established.
- A successful update must leave one canonical host running and the other stopped, with active-host identity/generation and runtime state agreeing.
- User supplied SHA-256 for the current WSL updater source bundle: `bc9f4df991079266ba1957f16ac6bae13ea82cbc304696f1a59a9d365da288ce`, path `/mnt/d/Hagonoy-SMP/server-update-downloads/hsmp-updater-current-source.zip`. The ZIP bytes were not attached/available in this chat runtime, so its contents and hash have not been independently verified here. Do not claim inspection or patch preparation from the checksum alone.

## Verified source-bundle inspection — 2026-11-13

- User supplied and locally verified SHA-256 for `/mnt/d/Hagonoy-SMP/server-update-downloads/hsmp-updater-current-source.zip`: `bc9f4df991079266ba1957f16ac6bae13ea82cbc304696f1a59a9d365da288ce`. The archive listing and selected source were printed by a read-only script.
- The archive includes the top-level two-line `hagonoy` shim, `bin/hagonoy-dual-lifecycle`, `bin/hagonoy-generation`, `config/dual-host.conf`, and the focused core/Paper/Geyser tests. It omits `bin/hagonoy`, the actual command dispatcher invoked by the top-level shim; its command-routing behavior remains uninspected.
- Verified implementation gaps from the printed source:
  - `bin/hagonoy-dual-lifecycle` requires Ubuntu SSH configuration and always invokes the remote Ubuntu helper; its Windows check only proves Windows has no tmux/Java TCP/Bedrock UDP listener. Its output explicitly targets Ubuntu and excludes Windows staging.
  - `bin/hagonoy-generation:update_core_server()` requires manifest host == `ubuntu` and calls `verify_running_server(..., "ubuntu", ...)`.
  - `verify_core_update_runtime()` also hard-codes `ubuntu`.
  - Core update stages downloads beside the live server JAR/plugin JAR targets; it does not use `/mnt/d/Hagonoy-SMP/server-update-downloads` as the designated central artifact cache.
  - Existing generation helper contains Windows-specific runtime verification and host arguments in some lifecycle methods, but update flow does not thread the host through all verification/start/stop/rollback calls.
- The nine targeted tests are confirmed passing from the user's latest supplied batch. They do not currently exercise central cache integration or automatic host detection/routing.
- Next source inspection must include `bin/hagonoy` and the AST-extracted definitions of `verify_running_server`, `start_managed_server`, `stop_managed_server`, `verify_core_update_runtime`, `update_core_server`, and CLI parser/main. Do not patch the lifecycle dispatcher until its full routing contract is visible.
- Live update remains incomplete; no new server operation was performed during source inspection.

## Dispatcher and host lifecycle findings — 2026-11-13

- User supplied the actual `bin/hagonoy` dispatcher and AST-extracted functions from `bin/hagonoy-generation`.
- WSL `./hagonoy update --plan|--execute` routes to `bin/hagonoy-dual-lifecycle update`. The standalone single-host Paper-only updater is a distinct legacy path; do not conflate it with the combined Paper/Geyser/Floodgate updater.
- The dispatcher contains a duplicate `update)` case arm: the first routes to the dual lifecycle coordinator; the later rejection arm is unreachable. Avoid broad dispatcher refactoring, but account for this if editing that route.
- The generation helper already has Windows runtime verification, Windows start.bat launch selection, and Windows listener checks in lifecycle helpers. The combined updater remains Ubuntu-only: it rejects non-Ubuntu manifests, hard-codes Ubuntu during runtime verification, and omits host arguments on stop/start/verification/rollback calls.
- The dual-lifecycle wrapper only checks that Windows is stopped, then unconditionally invokes Ubuntu over SSH.
- The combined updater downloads beside live JAR targets and does not use the central D: cache.
- The archive omitted `bin/hagonoy-dual-status` and `bin/hagonoy-dual-windows-lifecycle`. These existing status/Windows scripts must be read before integrating host detection, to reuse the established status and generation semantics.
- Nine targeted regression suites pass. Central-cache integration and active-host routing remain unimplemented and untested. No live server changes were made.


## Active-host inspection checkpoint — 2026-11-13

User supplied the remaining WSL dual-host scripts and selected generation-helper functions. The inspection confirms there is no safe active-host detector to reuse as-is:

- bin/hagonoy-dual-status classifies each host mainly from tmux-session presence plus Java TCP listener count. It prints Bedrock UDP counts but does not require/use them for state classification. It does not validate generation manifest host/state/ID/ancestry, Java PID/process identity, or canonical process working directory.
- bin/hagonoy-dual-windows-lifecycle is a lifecycle guard, not a selector. It checks Ubuntu's manifest says stopped plus no tmux session/TCP/UDP before operating Windows; Windows start/stop then uses host-specific generation-helper commands.
- bin/hagonoy-dual contains backup-source selection only. Its lightweight state checks are not suitable for update authorization.
- bin/hagonoy-generation select() applies only when the extant generation manifests are STOPPED. It compares generation numbers and ancestry; equal generation IDs explicitly do not prove byte-identical server trees. Do not repurpose it to select a live host.
- verify_running_server_windows() gives useful partial evidence (unique Java process owning the TCP listener, server.jar command line, Bedrock UDP endpoint, tmux session and canonical pane path, runtime versions), but the Java process's own working directory is not independently tied to the canonical directory. verify_stopped_server() checks manifest stopped/session absence/listeners, but its Ubuntu branch only checks TCP while Windows checks TCP and UDP.
- A new updater-specific read-only detector is required. It must positively verify host reachability, manifest identity/state, tmux/process/listener evidence, Java/Bedrock endpoints, and canonical server process directory; exactly one host must be fully RUNNING and the other fully STOPPED. Conflicting, incomplete, unreachable, both-running, or both-stopped results abort. Re-probe immediately before stop/replacement.
- Do not use existing status output or the stopped-generation selector as sufficient authority evidence. The core updater still must be threaded with the selected host and D: cache end-to-end.

The previously passing nine local regression tests remain confirmed; they do not cover this detector or central-cache integration. No live operation or server-file change occurred during this inspection.


## Manifest and runtime-verifier inspection — 2026-11-13

User supplied the complete load() and generic verify_running_server() implementations from the WSL checkout.

- load() validates schema version 1; state is running/stopped; generation is a positive integer; generation_id and ancestry are valid; ancestry length equals generation minus one; and parent_generation_id matches the last ancestor (or is null for generation 1). It currently does not validate a host value as part of this loader.
- The Ubuntu branch of verify_running_server() already verifies canonical directory existence, tmux session and pane paths, unique Java TCP listener PID, executable name, Java process cwd equal to the canonical server directory, and live Paper/Minecraft version readback. Its default require_manifest_absent=True is for adoption; an update preflight of an existing managed server must explicitly preserve/validate its manifest rather than mistake this default for a host selector.
- The Windows branch delegates to verify_running_server_windows(); prior printed code confirmed Java owner/process command-line, Bedrock UDP presence, tmux pane path and runtime readback, but did not independently verify the Java process's own current directory against the canonical server directory.
- Remaining design requirements: require manifest host/state to agree with process evidence; require Bedrock UDP to be a validated part of RUNNING and STOPPED state on both hosts; add equivalent canonical-process-directory verification on Windows; prove exactly one host RUNNING and the other STOPPED; bind and recheck host/generation identity before stop and replacement. Existing loader validation is reusable rather than duplicated.
- No source patch, live server operation, or server-file modification occurred in this inspection. The nine previous tests remain confirmed but do not cover these gaps.


## Core transaction and CLI inspection — 2026-11-13

User supplied the complete WSL implementations of save(), save_new(), verify_core_update_runtime(), update_core_server(), and relevant CLI references.

- Existing core update transaction is worth preserving: stage all changed JARs, recheck generation and old hashes, create transaction-local rollback copies (not a full backup), gracefully stop, verify stopped manifest/generation, atomically replace the changed set, start and verify updated runtime, and attempt full-set rollback/restart on failure. Recovery copies are retained if recovery cannot be confirmed.
- update_core_server() currently rejects every non-Ubuntu manifest and hard-codes ubuntu in its pre-update verifier. verify_core_update_runtime() also hard-codes ubuntu.
- Transaction calls to stop_managed_server(), start_managed_server(), verify_running_server(), mark_failed_start_stopped(), and rollback/restart paths omit host in multiple places, so their defaults route to Ubuntu even if the top-level preflight were changed.
- Artifact staging remains adjacent to the live targets. The CLI core-update parser has no --host or --artifact-cache option, and dispatch does not pass either value. The core coordinator must populate the central D: cache and transfer/reverify artifacts before invoking the host-specific transaction; do not simply change the staging directory to D: when an atomic replace across filesystems is needed.
- save() atomically replaces an existing generation manifest; save_new() atomically creates a manifest without overwriting an existing one. The update needs to preserve the existing manifest lifecycle and validate its host/generation identity throughout stop/start/rollback.
- These are source inspection findings only. No source patch, live server operation, or server-file modification occurred. The previously confirmed nine tests do not cover host routing or cache behavior.


## Lifecycle host-parameter inspection — 2026-11-13

Latest user-supplied source excerpt adds these specific safeguards to the patch scope:

- start_managed_server() and stop_managed_server() accept host='ubuntu' but do not require the loaded manifest's host to match the requested host before transitioning or verifying. Add a strict host/manifest match so a wrong-host call cannot silently advance or stop another copy's generation.
- verify_stopped_server() validates manifest state and listener/session absence but does not compare manifest host against its host parameter. Add the same explicit check.
- mark_failed_start_stopped() is Ubuntu-only: it checks tmux and Linux ss TCP only, then calls finish(). It must accept the selected host and prove the correct host's Java TCP and Bedrock UDP listeners are absent before manifest reconciliation.
- stop_managed_server() checks both TCP and Bedrock UDP on Windows after graceful stop, but Ubuntu currently checks TCP only. Make UDP part of the Ubuntu stop verification too.
- The lifecycle CLI already supports --host for start-server and stop-server, but core-update still lacks a --host and artifact staging/cache interface.

No source patch or live operation has been performed. Keep these checks in the same consolidated host/cache patch and tests.

## Artifact download and cache handoff inspection — 2026-11-13

User supplied the exact current WSL implementations of Paper/Geyser metadata discovery, verified downloads, installed managed-plugin inspection, and release comparison.

- Paper stable metadata includes an official download URL, JAR name, byte size, and SHA-256. Its downloader streams to an exclusive temporary destination, checks exact byte count and SHA-256, and fsyncs the file.
- GeyserMC metadata selects the latest default-channel build, uses the Spigot download identifier, and supplies the official SHA-256. Its downloader streams to an exclusive temporary destination and checks SHA-256. Staged plugin JARs are subsequently inspected for plugin descriptor identity and release version.
- Existing installed-plugin discovery only targets already-installed, unambiguous Geyser-Spigot and Floodgate artifacts. It rejects managed-looking identity/filename conflicts and refuses unknown/custom installed hashes rather than replacing them blindly. Preserve these safeguards.
- Cache integration must retain these official metadata/checksum/identity checks. Cache downloads should use temporary files in the central cache filesystem, verify fully, then atomically promote; existing verified current cache entries may be reused. Never overwrite a valid cached artifact with a partial or failed candidate.
- Important transport constraint: WSL's /mnt/d/Hagonoy-SMP/server-update-downloads cache is local to Windows/WSL and is not directly available on the remote Ubuntu host. For Ubuntu-active execution, the coordinator needs a metadata handoff from the remote read-only plan, must populate/promote the central WSL cache locally, transfer verified artifacts to a controlled Ubuntu staging directory, and require destination-side SHA-256/JAR identity re-verification before the server stops. For Windows-active execution, the mounted central cache is directly available to the local generation helper.
- On both hosts, final JAR replacement staging must remain on the same filesystem as each live target so os.replace() remains atomic. Central cache storage must not be used directly as the final live target staging directory when that crosses filesystems.
- The existing helper already exposes all required metadata fields and the download/identity routines; no new upstream API or third-party downloader is needed. The full coordinator/cache handoff and both active-host routes still need implementation and dedicated tests.
- No source patch, server operation, file replacement, backup, or cleanup was performed during this inspection. The nine previous tests remain the last confirmed baseline and do not cover cache handoff/host routing.

## Current source-bundle handoff checkpoint — 2026-11-13

- User created the exact-source archive in WSL at `/mnt/d/Hagonoy-SMP/server-update-downloads/hsmp-core-updater-source-20261113.zip`.
- User-reported archive contains 16 required files and local SHA-256 `bfd49c91244869bab4ce0d48fe3a1d57fbba0fd89aad9a0d1dbc125fa10e5944`.
- The ZIP itself has not yet been attached to the conversation or materialized into the assistant runtime. Its contents and checksum have therefore NOT been independently inspected/verified by the assistant. Do not claim the bundle has been received or patched.
- Current phase: exact-source handoff, immediately before creating the consolidated updater patch. All required design findings are complete: existing transaction/rollback, host-specific lifecycle gaps, active-host evidence gaps, official artifact checks, and Windows/Ubuntu cache-transfer topology.
- Last confirmed tests are the nine focused baseline suites recorded above. No new tests have been run against this source ZIP, no consolidated patch exists yet, no fresh update plan has been run, and no live update has been performed.
- Next: user attaches the ZIP in this chat; verify the exact SHA-256 and inspect the archive files; create one consolidated host-routing/cache/rollback patch; batch existing and new tests; run a fresh read-only plan. Live execution remains a separate explicit-authorization step after the plan passes.

## Source archive availability check — 2026-11-13

- User asked to continue quickly and intelligently, with server health as the overriding acceptance criterion.
- Assistant checked the active runtime for `/mnt/d/Hagonoy-SMP/server-update-downloads/hsmp-core-updater-source-20261113.zip` and `/mnt/data/hsmp-core-updater-source-20261113.zip`; neither path exists in this session, and `/mnt/data` contains no uploaded files. Therefore the user-created WSL archive is still not attached/materialized here and cannot be independently verified or edited.
- Do not fabricate a patch from pasted excerpts or use GitHub default-branch code as a substitute for the current local WSL source. The current local branch/source may contain unpushed changes.
- No updater code, tests, live server process, JAR/plugin/world/datapack, or backup was changed in this turn. No fresh live status check is available.
- Next required input: attach the exact source ZIP to the chat. Then verify SHA-256 and archive manifest, prepare one coordinated patch, batch static/unit/host-route/cache/rollback tests, and run a fresh read-only plan. Keep all live actions gated by explicit authorization and successful preflight; never force-kill Java or sacrifice rollback/health verification for speed.
