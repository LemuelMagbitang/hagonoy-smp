# HSMP Project Memory

Last updated: 2026-11-12 (Asia/Manila)

This file is the durable handoff for work on the HSMP server-management tools. Read it before making project changes and update it when decisions, implementation state, or blockers change. Keep it concise and factual; remove stale details rather than accumulating repeated notes.

## Working rules

- Keep the work simple, fast, and focused. Continue from the latest known state; do not repeat broad audits or rediscovery.
- The GitHub repository is the source of truth for committed project code. Do not treat an old remote branch as the user's latest local working tree.
- User runs commands in their WSL/Ubuntu/Windows environment. Never claim to have edited their local checkout or live server unless a tool actually did so.
- Make changes in this repository; reuse existing scripts and layout. Do not add directories or abstractions without a concrete need.
- No automatic full backups. A full backup requires a separate, explicit user decision.
- Do not add, remove, replace, retire, prune, or deploy plugins, datapacks, or other server content without explicit approval for that specific operation.
- Keep maintenance output clear, with phase/progress/error reporting for long operations.
- Do not stop or modify the live server during code-only work.

## Agreed workflow boundaries

1. **Software updates** (./hagonoy update): update Paper and only already-installed, explicitly managed components such as Geyser and Floodgate. Inspect installed state; do not silently install missing components or alter unrelated plugins.
2. **Datapacks**: independent workflow using the existing datapack/addons commands. Datapack registration/planning/sync must not be part of start or update. Datapack files live in the world's datapacks folder.
3. **Server settings**: a separate logical workflow for server configuration (for example view distance, simulation distance, Paper and Geyser settings). No need to create a separate physical directory unless a real implementation need appears.

Never let a software update or server start unexpectedly change world datapacks.

## Current project state (known 2026-11-12)

- User's WSL checkout: /home/lemuel/hagonoy-smp.
- Last known local branch: fix/border-console-pane-and-parser-20261111. This branch was not present in the GitHub branch listing checked on 2026-11-12; do not assume its commits or worktree changes are on GitHub.
- Remote branches seen: feature/dual-host-manager, main, maintenance/backup-path-and-metadata, maintenance/world-border-datapack-updater.
- A current-worktree patch was exported by the user to C:\Users\lemue\Downloads\hsmp-current-worktree.patch; SHA-256: fa19c46f7b5b8d710bbb7c0cb66ae337d0de8b0a7a36ac40329a1ce859c05a25. The patch file itself still needs to be attached in the ChatGPT conversation before it can be inspected or used to prepare an exact change. Do not reconstruct the branch from stale remote code.
- Previously committed locally (exact availability on current remote branch not confirmed):
  - 67016c3 — Paper updates use a temporary rollback JAR rather than an automatic TAR backup.
  - 7ca4d97 — world-border console targeting and reply parsing.
- Datapack manager files were added locally by the user in an earlier step:
  - bin/hagonoy-datapacks.py
  - bin/hagonoy-datapacks-remote.py
  - config/approved-datapacks.json
  - tests/datapack-deploy-check.py
  - Related modifications to bin/hagonoy, dual lifecycle scripts, and addons inventory.
- The approved datapack manifest currently lists 13 VanillaTweaks packs. Registration was completed; deployment was not. Do not deploy them unless the user explicitly authorizes a separate datapack sync.
- The datapack manager was wired into start and update; this coupling is unwanted and must be removed from those lifecycle paths while preserving standalone datapack commands.
- Offline checks previously passed for shell syntax, Python compilation, tests/datapack-deploy-check.py, and git diff --check at that earlier point. Re-run only focused tests after relevant edits.

## Last known live-server state (do not assume still current)

- Ubuntu was the authoritative live host, remote server path /home/leonardodavinci/minecraft-server, generation 6, Minecraft 26.3, Paper 26.3-244-main@35a2d15, tmux session mcserver, port 25565 listening.
- Windows server path: /mnt/d/Hagonoy-SMP/minecraft-server, generation 5, stopped.
- Paper 249 was downloaded and SHA-verified in temporary staging but was not installed.
- The failed update stopped at the generation-verifier stage, before server shutdown, save/stop, JAR replacement, or datapack deployment. Last observed live version remained Paper 244.
- Treat all runtime details above as historical until the user provides a newer status. Do not re-audit the server unless the next concrete operation requires it.

## Next work

1. Obtain and inspect the user's exported patch (SHA above) so edits target the exact current branch/worktree.
2. Remove datapack sync hooks from start and update; preserve standalone datapack commands and registration.
3. Run only the focused syntax and datapack/update regression checks affected by that change.
4. Then finish the simple installed-component software updater (Paper plus installed/managed Geyser and Floodgate) without expanding scope into unrelated plugins or datapacks.
5. Give the user one clear next command at a time, only when an action in their environment is actually needed.

## Session handoff protocol

At the start of an HSMP continuation, read this file and the current ChatGPT project context. Prefer the newest dated facts when they conflict. After meaningful work, update this file with the new state, tests, commits, and the single next action. Do not store credentials, tokens, private keys, or other secrets here.
