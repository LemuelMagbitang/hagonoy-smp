# HSMP Core Updater and Host-Routing Workflow

Last updated: 2026-11-13 (Asia/Manila)

## Purpose

This document is the detailed design record for the HSMP core server-software updater. The objective is to keep the currently authoritative HSMP server healthy while updating only the already-installed managed core components. The updater is a maintenance tool; the live server's verified health is the outcome that matters.

The user's explicit instructions and latest decisions are authoritative. This document supplements `memory/PROJECT_MEMORY.md`; it does not override it.

## Managed scope

The core updater manages only:
- Paper server JAR.
- Geyser-Spigot, only when the exact installed managed plugin identity is verified.
- Floodgate Spigot, only when the exact installed managed plugin identity is verified.

Rules:
- Discover latest official stable/default-channel releases automatically from upstream metadata. Do not require the user to type component names, versions, or build numbers.
- Update only components already installed and recognized. Never silently install a missing component.
- Never update, install, replace, remove, or otherwise alter unrelated plugins (including Chunky) unless the user changes scope.
- Never modify worlds, configs, plugin data, server.properties, datapacks, or other content as part of a core update.
- Do not create a full backup automatically. A full backup requires separate explicit authorization. Temporary verified JAR rollback copies are distinct from a full server backup.
- Keep datapack registration/planning/sync separate from Paper/Geyser/Floodgate update and lifecycle start/stop commands.

## Artifact cache and download workflow

Canonical Windows update-artifact cache:
- Windows: `D:\Hagonoy-SMP\server-update-downloads`
- WSL: `/mnt/d/Hagonoy-SMP/server-update-downloads`

This directory is the user's designated central cache/reference location for current server update artifacts. It is not the live Minecraft server directory and must not be confused with the manager checkout or user Windows Downloads directory.

Expected behavior:
1. Query official upstream metadata for current release/builds and compatibility.
2. Compare the upstream stable/default-channel candidates with the installed active-host artifacts and local cache.
3. Download newer candidates into the central cache using temporary/partial filenames.
4. Verify HTTP success, complete byte count, archive/JAR integrity, official SHA-256, expected artifact identity, and compatibility.
5. Atomically promote a verified candidate into the central cache, replacing the prior cached artifact only after verification. Retain no partial or checksum-invalid file as the current cache artifact.
6. Transfer the verified artifact from the central cache to a controlled temporary staging location on the verified active server host. For Ubuntu, this means transfer from WSL's mounted D: cache to the configured Ubuntu host; for Windows, deploy from the local mounted cache to the Windows live server.
7. Re-verify the transferred file on the destination host before any live-server stop or replacement.
8. Stage all required component updates before graceful shutdown.
9. Gracefully save/stop only the verified active server, apply the JAR transaction, start the same host, and verify runtime readiness and actual component versions.
10. On failure, restore all changed managed JARs together and attempt to restore the original running state safely. Never force-kill Java or replace JARs while Java may still be using them.

Do not make the central cache the source of truth for which host is active. The cache holds artifacts; the dual-host state/generation checks determine the active server.

A patch archive for manager source code is not a server update artifact. Do not place patch ZIPs in or describe them as Paper/Geyser/Floodgate JARs. For user-delivered project patch archives, use the designated `server-update-downloads` path when supplying shell instructions, unless the user explicitly chooses another path. Never assume `C:\Users\...\Downloads`.

## Required active-host detection and routing

The updater must identify whether the canonical live server is currently hosted on Ubuntu or Windows and direct every relevant read, transfer, stop/start, file move, JAR replacement, verification, and rollback to that same active host.

Preflight must examine both canonical hosts using multiple independent signals:
- Generation manifest identity, host, generation number/ancestry, and running/stopped state.
- Configured tmux session.
- Java TCP listener for the Minecraft Java port.
- Bedrock UDP listener for the configured Bedrock port, where expected.
- Process/runtime identity and canonical server directory.
- Host reachability and ability to read back state.

Routing rules:
- Exactly one canonical host must be positively verified as RUNNING and the other positively verified as STOPPED.
- The active host's manifest must identify the same host and agree with observed runtime.
- The inactive host must have no conflicting live process/listeners.
- If both hosts appear active, both appear stopped, either host is UNKNOWN/unreachable, manifests disagree, generation identity is inconsistent, or evidence conflicts, fail closed. Do not guess, default to Ubuntu, or pick whichever host responds first.
- Recheck the selected active host and inactive host immediately before shutdown and before any live replacement to prevent host-state races.
- Print the resolved active host, server directory, generation and ID, and explicit destination for each operation.
- `--plan` must be read-only and show the chosen host and exact artifact/deployment destinations.
- `--execute` may operate only on the same host that passed the preflight. A target host must never silently change between plan and execution; if state changes, abort and require a fresh plan.
- Do not use the inactive host as a staging or replacement target for the live server update. Host synchronization is a separate command/workflow.

Current known state is that Ubuntu was the active canonical host during the latest user-supplied plan, while Windows was confirmed without canonical Java TCP or Bedrock UDP listeners. This is a historical checkpoint, not permission to hard-code Ubuntu forever.

## Host synchronization semantics

The user's intended direction is:
- Pull server = Ubuntu to Windows. When Ubuntu is the authoritative active source and pull/handoff is explicitly run, Windows should receive the verified same server tree/generation. The exact existing pull modes and stop/start safety rules remain in force.
- Push server = Windows to Ubuntu. When Windows is the authoritative source and push is explicitly run, Ubuntu should receive the verified same server tree/generation.
- A completed pull/push should produce a verified identical server-directory copy with generation lineage preserved, subject to the existing generation/handoff design.
- The active authoritative host is the source; the inactive peer is the destination. Never infer source direction from timestamps, JAR versions, or whichever tree looks newer.
- The separate central `server-update-downloads` cache is outside both server directories and must not be deleted, overwritten, or moved by pull/push.
- Host synchronization must not be triggered automatically by a routine core update.

## Current implementation checkpoint — 2026-11-13

Source: user-supplied terminal output in the current conversation.

- User applied the GeyserMC download-key correction to the WSL checkout:
  - Updated `bin/hagonoy-generation` to use API download identifier `spigot` instead of the artifact filename in the request URL.
  - Added `tests/dual-geyser-download-key-check.py`.
  - The patch reported manager source/test changes only; no Minecraft process, server JAR, plugin, world, datapack, or backup was touched.
- The test suite has NOT yet been rerun after this patch. An earlier test command failed immediately because the regression test did not exist before the patch was applied. Run the regression test and the existing targeted updater/Paper suites now.
- Latest successful plan-only output: Minecraft 26.3; Paper build 244 -> 249; Geyser 2.12.1 build 1302; Floodgate already current (2.2.5 snapshot/build 141, official hash matched). No unrelated plugins/world/datapacks targeted.
- A previous live execution attempt downloaded Paper 249 and verified its SHA-256, then failed downloading Geyser build 1302 with HTTP 404. The failure occurred during download/staging, before graceful shutdown, live JAR replacement, or restart. Do not claim the update was installed.
- The Geyser 404 was traced in the local source to constructing the URL with the artifact filename (for example `Geyser-Spigot.jar`) rather than the API's download key `spigot`. The correction has now been applied locally; verification is pending.
- After the Geyser regression and existing tests pass, rerun `./hagonoy update --plan`. Do not retry execution until the plan confirms both artifacts and the intended active-host route.
- The plan output previously said `Target: Ubuntu canonical server` and `Windows staging is excluded`. Current dual-lifecycle routing was observed to check Windows is stopped and then hard-code the Ubuntu remote lifecycle. That does not yet satisfy the newly explicit requirement to detect and route updates to whichever canonical host is actually active. This is a required design gap, not completed behavior.
- GitHub default branch code was observed to differ from the user's WSL working copy/router behavior. Do not assume remote `main` contains all latest WSL changes. Keep source patch application and Git commit/push as distinct actions. Do not push code without explicit approval.

## Current next actions

1. Run `python3 -m py_compile bin/hagonoy-generation`.
2. Run `python3 tests/dual-geyser-download-key-check.py`.
3. Run the existing focused API, plan, execution, and Paper regression suites.
4. Run `./hagonoy update --plan` and review the active host and artifact routing.
5. Implement and test active-host detection/routing; current Ubuntu-only hard-coding must not be represented as host-agnostic.
6. Integrate the canonical D: artifact cache so all component candidates are downloaded, verified, atomically cached, transferred, and deployed to the detected active host.
7. Only after those gates pass, perform an explicitly authorized live update and verify the same active host returns healthy.

## Boundaries and deferred work

- VPN/firewall work is explicitly deferred; do not bring it into the active updater phase.
- Offline-mode/TLauncher-compatible authentication is a future security workstream; preserve the requirement, but do not change online-mode or add authentication plugins during updater work.
- Native Minecraft commands, datapack functions, dialogs, and command blocks are future in-game feature design work; do not add packs/plugins during updater work.
- Datapack deployment and the 13 enabled VanillaTweaks packs are separate from this updater phase.
- VanillaTweaks source/archive changes are handled only in the datapack workflow. The user mentioned intending to remove a duplicate `VanillaTweaks-26.3.zip` in favor of the original `VanillaTweaks_d831085_UNZIP_ME.zip`; deletion was not confirmed in the current conversation, so do not record it as completed or delete either file.
