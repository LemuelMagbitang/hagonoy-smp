# HSMP Project Memory

Last updated: 2026-11-12 (Asia/Manila)

This is a continuity aid, not the project authority. The user's explicit decisions and clarifications are authoritative. Keep this file factual and current; never let older notes or legacy scripts override the user's direction.

## Mission

- The goal is a healthy, reliable HSMP server that returns to a working, verified state after maintenance. Brief downtime is acceptable when required; correct recovery and a verified running server are the objective.
- The major upgrade from the earlier Minecraft 1.21.x-era baseline to Minecraft 26.3 / Paper 26.3 was successfully completed. Do not reopen that migration unless the user reports a problem.
- The recurring update/maintenance manager is still being completed. Do not confuse the completed upgrade to 26.3 with completion of the updater.
- Keep work simple, focused, and high quality. No repeated broad audits, unnecessary abstractions, redundant questions, or directory proliferation.
- The user's decisions are the source of truth. The repository is the implementation workspace and version-control record. Legacy scripts are references only, not the authority.
- Separate user-confirmed facts, historical command output, and unverified current state. Never claim local or server changes that were not made.

## Maintenance responsibilities and order

### 1. Core server updater — current priority

The normal updater is limited to Paper server software, Geyser, and Floodgate. Detect what is installed and update only those managed components. Do not install missing components or update unrelated plugins such as Chunky unless the user changes the scope.

Discover current stable releases from official upstream sources. Files in the Windows update-downloads folder are reference/staging material, not the sole source of updates or proof of latest versions. Validate candidates and compatibility; stage safely; save and gracefully stop when required; apply; restart; and verify readiness and resulting versions. Recover/rollback safely on failure and do not leave the server stopped when safe recovery is possible.

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

## Immediate work sequence

1. Obtain and inspect the exported worktree patch so edits target the exact current code.
2. Finish the Paper/Geyser/Floodgate updater: upstream release discovery, installed-component detection, safe update/rollback, readiness verification, and clear progress/errors.
3. Remove automatic datapack work from normal `start` and core `update`; keep datapack maintenance independent.
4. Finish the VanillaTweaks datapack update workflow as the next distinct feature.
5. Run focused tests, then review host-switching and backup utilities.
6. For live maintenance, identify the current authoritative host, run preflight, stop gracefully only when needed, then verify the server is healthy and running again.

## Current addons/datapack work focus (2026-11-12)

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
