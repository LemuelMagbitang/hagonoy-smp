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

Source: user-supplied WSL terminal output.

- GeyserMC download URL construction in the WSL checkout now uses the API download identifier `spigot`, not the artifact filename. The added Geyser/Floodgate URL regression suite passes for build 1302 and build 141.
- The URL regression test fixture was corrected to obey the default-channel-only contract. The core API test's stale URL expectation was also corrected from `/downloads/Geyser-Spigot.jar` to `/downloads/spigot`.
- Latest batch: ALL NINE CHECKS PASSED:
  1. Python compilation of `bin/hagonoy-generation`.
  2. `tests/dual-runtime-version-probe-check.py`.
  3. `tests/dual-geyser-download-key-check.py`.
  4. `tests/dual-core-update-api-check.sh`.
  5. `tests/dual-core-update-plan-check.sh`.
  6. `tests/dual-core-update-execution-check.sh`.
  7. `tests/dual-paper-update-api-check.sh`.
  8. `tests/dual-paper-update-plan-check.sh`.
  9. `tests/dual-paper-update-execution-check.sh`.
- The simulated runtime mismatch/readiness failures in execution tests are intentional failure cases; the suites verified rollback/recovery.
- Tests did not contact or change the live server. The previous live execution downloaded and SHA-256-verified Paper 249, then encountered Geyser HTTP 404 before graceful shutdown, JAR replacement, or restart. The live server must still be treated as unchanged until a fresh live readback proves otherwise.
- Latest plan snapshot (refresh before execution): Ubuntu target, Minecraft 26.3, Paper 244 -> 249, Geyser 2.12.1 build 1302, Floodgate already current. The output said Windows staging was excluded; current routing is not host-agnostic and does not meet the user's requirement.
- GitHub `main` is the documentation record and may lag the user's local WSL checkout. Do not overwrite the WSL checkout from remote main. Do not push manager source changes without explicit approval.

## Current next actions

1. Complete the central artifact-cache flow using `D:\\Hagonoy-SMP\\server-update-downloads` / WSL `/mnt/d/Hagonoy-SMP/server-update-downloads`: discover stable releases, download to temporary files, verify, atomically promote, transfer to the selected active host, and verify again remotely.
2. Complete host-agnostic routing before any live update: confirm exactly one canonical host is running and the other stopped using manifest/generation identity, tmux/process state, Java TCP, Bedrock UDP, and reachability. Fail closed on any ambiguity; never default to Ubuntu.
3. Batch targeted tests for both changed workflows. Run one fresh read-only `./hagonoy update --plan` and confirm it reports the real active host, cache path, transfer path, and exact target artifacts.
4. Once both requirements are satisfied, request explicit live-update approval, execute on the detected host, and verify Paper/Geyser/Floodgate plus server readiness on that same host.

The user expects the maintenance work to finish within a two-day window. Avoid repetitive audits and one-test-at-a-time loops. Batch concrete work and proceed directly through the remaining gates. Do not bypass active-host detection, artifact verification, graceful lifecycle, or rollback safety to save time.

## Boundaries and deferred work

- VPN/firewall work is explicitly deferred; do not bring it into the active updater phase.
- Offline-mode/TLauncher-compatible authentication is a future security workstream; preserve the requirement, but do not change online-mode or add authentication plugins during updater work.
- Native Minecraft commands, datapack functions, dialogs, and command blocks are future in-game feature design work; do not add packs/plugins during updater work.
- Datapack deployment and the 13 enabled VanillaTweaks packs are separate from this updater phase.
- VanillaTweaks source/archive changes are handled only in the datapack workflow. The user mentioned intending to remove a duplicate `VanillaTweaks-26.3.zip` in favor of the original `VanillaTweaks_d831085_UNZIP_ME.zip`; deletion was not confirmed in the current conversation, so do not record it as completed or delete either file.


## Geyser regression-test fixture correction — 2026-11-13

- Source: user-supplied traceback from the WSL test run.
- The URL regression test's fake fetch_geysermc_default_builds() returned two entries: default build 1302 and experimental build 1802. The production helper filters the API build history to default-channel builds before returning, so this mock violated the mocked helper's contract.
- fetch_geysermc_default_build() selects the maximum build among the default builds it receives. In the invalid test fixture, it correctly chose 1802 because the fake injected an experimental item after the filtering boundary.
- This traceback does not demonstrate a production channel-selection defect. Channel filtering remains covered by dual-core-update-api-check.sh.
- A fixture-only patch bundle hsmp-geyser-test-fixture-fix.zip was prepared. It removes the experimental fixture item from this URL-construction test and clarifies that the real default-channel filtering is tested by the core API suite. It does not modify production updater code.
- The patch application's target anchors and Python compilation were tested against a temporary copy successfully. The user's WSL checkout has not yet received this fixture patch, and the actual Geyser regression test has not yet passed.
- Patch delivery uses D:\Hagonoy-SMP\server-update-downloads (WSL /mnt/d/Hagonoy-SMP/server-update-downloads), never the user's Windows Downloads folder.
- No live server, JAR, plugin, world, datapack, or backup was changed by this diagnosis or patch preparation.

Next: apply the fixture correction from the central cache; run the URL regression and existing focused updater/Paper suites; then re-run plan mode. Do not retry live execution yet.


## Post-fixture test result and eventual cleanup — 2026-11-13

- User applied `hsmp-geyser-test-fixture-fix.zip` successfully. Only `tests/dual-geyser-download-key-check.py` was changed.
- `python3 -m py_compile bin/hagonoy-generation` passed.
- `python3 tests/dual-geyser-download-key-check.py` passed:
  - Geyser build 1302 uses `/downloads/spigot`, not the artifact filename.
  - Floodgate build 141 uses `/downloads/spigot`, not the artifact filename.
- User then ran the six core/Paper suites as an `&&` chain. The first suite, `tests/dual-core-update-api-check.sh`, stopped with an embedded Python traceback `File "<stdin>", line 48, AssertionError`. Because of `&&`, no subsequent core plan/execution or Paper suites ran in that command. Exact assertion is unknown. Next: inspect the script around its embedded Python block and run `bash -x tests/dual-core-update-api-check.sh`; do not change production code until the failing expectation is identified.
- Later cleanup is a distinct post-update phase requested by the user. Once the server update is complete and verified, inventory files outside the structured Windows/Ubuntu live server directories, including obsolete contents in `D:\Hagonoy-SMP\server-update-downloads`. Classify keep/archive/delete candidates, preserve required original source archives, current artifacts, recovery/rollback material until safe, and all canonical server/manager files. Do not perform automatic or premature deletion; obtain explicit approval for destructive cleanup.

## Immediate test correction and timebox — 2026-11-13

- The user-provided numbered test file establishes that the embedded Python traceback at `<stdin>, line 48` maps to shell file line 52 (Python begins at shell line 5).
- The failing assertion is the old URL expectation `/1300/downloads/Geyser-Spigot.jar`; after the production fix, it must expect `/1300/downloads/spigot`.
- This is a test-only expectation correction. Do not modify the production default-channel filter or build-selection logic to satisfy this failure.
- After the guarded one-line correction, run compilation, the Geyser URL regression, and every core/Paper API, plan, and execution suite in one fail-continue batch; report all failures together rather than stopping at the first `&&` failure.
- Schedule priority: user expects this maintenance/update work to finish within the two-day window. Batch work, avoid repeated rediscovery and unnecessary audits, and focus on the remaining concrete blockers: test baseline, central D: artifact cache, correct active-host detection/routing, live update, and health verification.
- Do not execute the live update until the cache and host-routing requirements are actually met; do not represent those requirements as complete based on the current Ubuntu-specific plan.


## Operational acceptance: server must return healthy and running

- The purpose of every maintenance operation is to leave HSMP healthy, verified, and running on the same authoritative host that was positively identified at preflight.
- A stop is a temporary maintenance action only when the selected files cannot safely be replaced while the server is running. Do not stop the server merely to probe, plan, or test code.
- Keep the server online during all plan-only, metadata discovery, download, checksum, archive/JAR integrity, compatibility, and remote-stage verification work. Complete these steps before graceful shutdown.
- For an executed update: revalidate host identity/state immediately before stop; save and gracefully stop; apply only the verified managed JAR set; start the same host; wait for readiness; verify Minecraft version unchanged, Paper build, Geyser/Floodgate runtime versions, Java and Bedrock listeners as applicable, and a successful live status/readback. Perform practical player-connection checks where available.
- If any post-replacement check fails, restore all changed managed JARs together and restart the original set. Verify the restored server reaches readiness. Do not report success until the server is running and health checks pass.
- Never force-kill Java or leave the canonical server stopped as a normal terminal result. If automated recovery cannot restore service, report the precise failed recovery step and provide the safest immediate recovery action; do not claim the server is healthy.
- The inactive host must remain stopped throughout the update; exactly one canonical host should be running after successful completion.
- The user provided the current-source ZIP's local SHA-256 as `bc9f4df991079266ba1957f16ac6bae13ea82cbc304696f1a59a9d365da288ce`. The archive itself was not attached to the assistant's runtime as of this checkpoint; verify the uploaded archive's hash before inspection or patching.
