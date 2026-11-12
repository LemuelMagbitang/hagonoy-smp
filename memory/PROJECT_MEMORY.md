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
- User successfully applied the Geyser download-key patch in the WSL checkout: `bin/hagonoy-generation` now uses API download key `spigot`; `tests/dual-geyser-download-key-check.py` was added. The first run of that test failed because its mocked `fetch_geysermc_default_builds()` returned both default build 1302 and experimental build 1802, violating the helper's default-channel-only contract. The production selection chose the maximum of the supplied mock entries (1802); this traceback identifies a faulty test fixture, not a production channel-filter regression. A test-only fixture correction has been prepared and remains unapplied. The existing core API suite covers filtering experimental builds.
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
