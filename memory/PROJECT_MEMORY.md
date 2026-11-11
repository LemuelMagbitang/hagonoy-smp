# HSMP Project Memory

Last updated: 2026-11-12 (Asia/Manila)

This is a continuity aid, not the project authority. The user's explicit decisions and clarifications are authoritative. Keep this file factual, compact, and current; never let an older note or legacy script override the user's direction.

## Mission and operating objective

- The project goal is a healthy, reliable HSMP server that returns to a working, verified state after maintenance. The server may be stopped briefly when an operation requires it; availability and correct recovery are the objective, not avoiding all downtime at the expense of maintenance.
- The Minecraft server was successfully upgraded from its earlier 1.21.x-era baseline to Minecraft 26.3 / Paper 26.3. Treat that major-version upgrade as completed and do not reopen it unless the user reports a problem.
- The update/maintenance manager is still being completed so future maintenance can be performed safely and reliably. Do not confuse successful migration to 26.3 with completion of the recurring update manager.
- Keep work simple, focused, and exceptional. Continue from known state; no repeated broad audits, unnecessary abstractions, directory proliferation, or redundant questions.
- The user's decisions are the source of truth. The repository is the implementation workspace and version-control record; legacy scripts are references only, not the authority.
- Clearly distinguish user-confirmed facts, historical command output, and anything not yet verified. Never claim local WSL edits, remote edits, server changes, or runtime verification that did not actually occur.

## Agreed maintenance responsibilities and order

### 1. Core server updater — current priority

The normal server update workflow is limited to:
- Paper server software.
- Geyser.
- Floodgate.

The updater must inspect what is actually installed and update only those managed components. Do not add missing components or update unrelated plugins such as Chunky unless the user explicitly changes scope.

The updater should discover current stable releases from their official upstream sources. Files in the Windows update-downloads folder are reference/staging material, not the only update source and not proof that a file is the latest release. Validate candidates and compatibility, stage safely, perform a graceful save/stop when needed, apply the update, restart, and verify startup/readiness and the resulting versions. On failure, recover/rollback safely and report the exact outcome. Do not leave the server stopped after a failed operation when a safe restart/recovery is possible.

Routine updates must not silently make full TAR backups. A full backup is a separate operation and requires its own explicit authorization. Temporary rollback artifacts used by the updater are not a substitute for, or authorization to create, a full backup.

### 2. VanillaTweaks datapack maintenance — next distinct workflow

Datapack maintenance is a separate script/workflow to address after the core Paper/Geyser/Floodgate updater. Do not couple datapack installation/sync to normal server start or the core software update command.

The user clarified that the built-in `vanilla`, `bukkit`, and `paper` entries shown by Minecraft's `/datapack list` are not independent downloadable update targets for the datapack updater. Paper is updated as server software. The custom world datapacks currently known are VanillaTweaks packs.

A local datapack manager and manifest were added; the manifest registered 13 VanillaTweaks packs for Minecraft 26.3. Registration/planning is not proof of deployment. Confirm actual installed state before any sync. Do not silently overwrite, remove, prune, or deploy packs. The separate datapack workflow should handle version compatibility and update/install decisions for the approved VanillaTweaks set.

### 3. Remaining host and backup utilities — review after the above

Host switching/moving the authoritative server between Ubuntu and Windows, and backup utilities, are separate maintenance responsibilities. They are believed to be largely in place but the user wants to review them after the core updater and datapack workflow are complete. Legacy scripts can inform behavior but must not be adopted as the main implementation without checking them against the user's current requirements.

## Known directory layout

Use these as the current intended/canonical paths. The user's latest explicit path clarification overrides older folder-preparation scripts and earlier backup-folder names.

**Windows (D: drive):**
- Live server: `D:\\Hagonoy-SMP\\minecraft-server`
- Backup vault: `D:\\Hagonoy-SMP\\server-backup`
- Update downloads/reference staging: `D:\\Hagonoy-SMP\\server-update-downloads`
- Legacy reference tree: `D:\\Hagonoy-SMP\\LINUX-HSMP - Emergency Evac`

**Ubuntu host:**
- Live server: `/home/leonardodavinci/minecraft-server`
- Backup vault: `/home/leonardodavinci/server-backup`
- Manager checkout previously observed: `/home/leonardodavinci/hagonoy-smp`

**Development/control environment:**
- User's WSL checkout: `/home/lemuel/hagonoy-smp`
- Dual-host configuration: `config/dual-host.conf`

The Windows server and Windows staging paths appear in WSL as `/mnt/d/Hagonoy-SMP/...`. Do not infer a separate native Windows manager checkout; the exact location of any such checkout has not been established. Do not use the older `hsmp-evac-v2-win-backup` directory as the canonical backup vault; the user has explicitly specified `server-backup` on both hosts.

## Current known implementation state (2026-11-12)

- WSL branch last reported: `fix/border-console-pane-and-parser-20261111`. This local branch was not present in the remote branch list checked on 2026-11-12. Do not replace it with stale remote code or assume its worktree is on GitHub.
- User exported the current worktree diff to `C:\\Users\\lemue\\Downloads\\hsmp-current-worktree.patch`.
  - SHA-256: `fa19c46f7b5b8d710bbb7c0cb66ae337d0de8b0a7a36ac40329a1ce859c05a25`
  - The patch itself has not yet been attached in the active conversation, so the exact current local diff remains unavailable for direct editing.
- Previously committed locally (exact presence on the current branch should be confirmed from the patch, not inferred):
  - `67016c3` — Paper update uses a temporary rollback JAR rather than an automatic TAR backup.
  - `7ca4d97` — world-border console targeting and reply parsing.
- Datapack manager additions previously applied locally include:
  - `bin/hagonoy-datapacks.py`
  - `bin/hagonoy-datapacks-remote.py`
  - `config/approved-datapacks.json`
  - `tests/datapack-deploy-check.py`
  - related routing/integration changes in the main and dual-host lifecycle scripts.
- The datapack manager was integrated into `start` and `update`; that lifecycle coupling is not wanted and must be removed while retaining the standalone datapack commands.
- Earlier focused offline checks passed for shell syntax, Python compilation, `tests/datapack-deploy-check.py`, and `git diff --check`; those results predate the latest exported worktree and must not be represented as a fresh test of the current tree.
- Historical update attempt stopped at a generation/runtime verifier before server shutdown, save/stop, JAR replacement, or datapack deployment. Paper 26.3 build 244 was the last observed installed build; Paper 249 was downloaded and hash-verified in staging but was not installed in that attempt. This point-build history does not undo the successfully completed migration to Minecraft 26.3.
- Historical runtime observation: Ubuntu was authoritative, generation 6, Minecraft 26.3, Paper 26.3-244, tmux `mcserver`, port 25565 listening; Windows generation 5 was stopped. Treat these as historical, not live status.

## Immediate work sequence

1. Obtain and inspect the user's exported worktree patch so all edits target the exact current code.
2. Finish the core Paper/Geyser/Floodgate updater: upstream latest-release discovery, installed-component detection, safe update/rollback, start/readiness verification, and clear progress/errors.
3. Remove all automatic datapack work from normal `start` and core `update`; keep standalone datapack maintenance independent.
4. Build/finish the VanillaTweaks datapack update workflow as the next distinct maintenance feature.
5. Validate both workflows with focused tests and then review host-switching/backup utilities.
6. For any live maintenance, establish the current authoritative host and perform preflight, graceful shutdown only when required, then verify the server is healthy and running again. Do not assume or manufacture current runtime state.

## Conversation-history audit limitation

The user supplied two private ChatGPT conversation URLs marking the start and current end of a long, branched HSMP project history. Direct retrieval of those `/c/` URLs was blocked. The accessible Library contains supporting scripts, patches, and pasted terminal-output snapshots, some of which were read to confirm paths and implementation history; these are not a complete transcript of all 23+ conversation branches. Never claim the full history has been read until the user supplies an accessible conversation export/transcript. Preserve this gap explicitly rather than filling it with guesses.

## Handoff protocol

At each continuation, read this project memory together with the current conversation context. The user's newest explicit direction wins over stale notes. After substantial work, update this file with verified decisions, state, tests, commits, and the next concrete action. Never store credentials, tokens, private keys, or other secrets.
