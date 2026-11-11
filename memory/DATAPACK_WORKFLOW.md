# HSMP Datapack / Addons Workflow Memory

Last updated: 2026-11-12 (Asia/Manila)

## Purpose and authority

This document records the intended design and the inspected implementation of HSMP's custom datapack management tools. It is a continuity aid. The user's latest explicit instructions are authoritative; neither this document nor older code may override them.

The user's current direction (2026-11-12) is to resume work on the addons/datapack maintenance tools now. The earlier plan to finish the core software updater first is not a reason to postpone this user-directed work.

The server's major migration to Minecraft 26.3 / Paper 26.3 is already complete. This work is about safely maintaining custom world datapacks, not repeating the migration.

## Scope

This workflow is for the custom VanillaTweaks datapacks registered for the HSMP world.

It is separate from the core server software updater:

- Core software updater: Paper, Geyser, Floodgate only; detect and update already-installed/managed components; no silent installs of missing components; Chunky is out of scope.
- Datapack manager: user-approved custom VanillaTweaks ZIP packs for the selected canonical world.
- Built-in datapack entries `vanilla`, `bukkit`, and `paper` are not separate downloadable pack targets. Paper is server software.

Do not attach datapack work to `start`, `restart`, or the core `update` operation. The user must be able to start the server without an implicit datapack download, copy, removal, or reload. Datapack actions are standalone `addons` commands.

## Vocabulary — keep these states distinct

1. **Source available**: a ZIP exists in the configured downloads folder.
2. **Registered / approved**: its filename, source, byte count, SHA-256, and compatibility metadata are recorded in `config/approved-datapacks.json`.
3. **Staged**: the manager has re-read the approved source, rechecked byte count and SHA-256, and prepared the transport payload.
4. **Installed on disk**: the approved ZIP exists under the selected world's `datapacks` directory and its bytes match the approved SHA-256.
5. **Enabled at runtime**: Minecraft reports the ZIP in `/datapack list enabled` after a running-world reload or server start.

Registration, planning, staging, and installation are not interchangeable. Never report a pack as enabled merely because it is present in the manifest or on disk.

Prior work recorded 13 VanillaTweaks packs as registered for Minecraft 26.3. The exact manifest from the latest private WSL worktree was not available during the 2026-11-12 review. Do not replace or regenerate the user's manifest from an older initial empty-manifest template.

## Intended command interface

Run from the HSMP repository root:

```bash
./hagonoy addons list
./hagonoy addons add <filename.zip>
./hagonoy addons add-bundle <VanillaTweaks-bundle.zip>
./hagonoy addons plan --host ubuntu
./hagonoy addons plan --host windows
./hagonoy addons sync --host ubuntu
./hagonoy addons sync --host windows
```

The no-argument host default may be Ubuntu, but operational commands should state the chosen host explicitly in logs. The old `./hagonoy addons --plan` spelling may remain as a compatibility alias, but it must route to the datapack-only planner, never the old broad inventory of Paper/plugins/Chunky.

Command semantics:

- `list`: show registered approvals only; no server contact or world mutation.
- `add`: register one ZIP found inside `D:\\Hagonoy-SMP\\server-update-downloads`; no server contact or world mutation.
- `add-bundle`: inspect a VanillaTweaks `UNZIP_ME` bundle and register its compatible nested ZIPs individually; no server contact or world mutation.
- `plan`: inspect the selected canonical world and show `PRESENT`, `ADD`, or `CONFLICT`; read-only.
- `sync`: the explicit mutating command. Add only approved, missing ZIPs to one selected canonical world. It never overwrites a different existing file and never removes or prunes unselected packs.

Do not call `sync` from lifecycle scripts. Do not run it merely because a pack was registered. A user invocation of the separate `addons sync` command is the explicit action that authorizes the additions in that run.

The earlier implementation included a `prestart` action and inserted automatic pre-start/start/update calls. The intended follow-up removes the `prestart` action and all lifecycle hooks. A stopped server can receive an explicitly requested `sync`; those files are then loaded on the next normal server start.

## Source and configuration paths

- Approved manifest: `config/approved-datapacks.json`
- Dual-host configuration: `config/dual-host.conf`
- Download/source folder: `D:\\Hagonoy-SMP\\server-update-downloads` (WSL: `/mnt/d/Hagonoy-SMP/server-update-downloads`)
- Ubuntu live server: `/home/leonardodavinci/minecraft-server`
- Windows live server: `D:\\Hagonoy-SMP\\minecraft-server` (WSL path: `/mnt/d/Hagonoy-SMP/minecraft-server`)
- Ubuntu manager checkout historically observed: `/home/leonardodavinci/hagonoy-smp`
- User's WSL development checkout: `/home/lemuel/hagonoy-smp`

The source ZIP may be a standalone file or an entry inside a VanillaTweaks bundle. The manager checks the source is in the configured downloads folder, validates ZIP structure and top-level `pack.mcmeta`, verifies Minecraft 26.3 data-pack format 121.0 compatibility, and records byte count and SHA-256.

At sync time, the source must still exist and match the registered byte count and SHA-256. If it changed, stop and require deliberate re-registration/review. Do not silently adopt new bytes from the download folder.

## Target world and dual-host safety

The remote helper resolves the actual world name from `server.properties` (`level-name`) and targets:

`<selected-server>/<level-name>/datapacks/`

Do not assume the world folder is always named `world`; `server.properties` is the source for the configured world name. Refuse unsafe world paths, symlink world/datapacks paths, or an unsafe `server.properties`.

Only one authoritative server host may be targeted. Before writing, the manager checks that the *other* host is stopped. The intended checks cover the opposite host's configured tmux session and Minecraft TCP / Bedrock UDP listeners. The selected target is checked against `.hagonoy-generation.json` host and running/stopped state, plus the tmux session and Minecraft TCP listener. A mismatch or ambiguous runtime must block the operation.

The user-confirmed host layout is:
- Windows live server: `D:\\Hagonoy-SMP\\minecraft-server`
- Ubuntu live server: `/home/leonardodavinci/minecraft-server`

Do not copy the same registered files to both hosts in one implicit operation. The selected canonical host is the only write target.

## Additive-only safety invariants

These invariants are mandatory:

- Validate the whole approved manifest before acting.
- Re-read and hash-check every source at staging time.
- Validate every pending ZIP before the first live-world write.
- Preflight every approved pack against the target world before writing any of them.
- Same filename + same SHA-256 is idempotently `PRESENT`.
- Same filename with different content is a conflict.
- Same logical pack identity (for example, same pack name at a different version filename) is a conflict, not an implicit upgrade.
- An existing directory, symlink, or other path occupying an approved pack identity is a conflict.
- On any preflight conflict, make no changes.
- Publish complete files without overwriting an existing target; use atomic hard-link publication where supported and exclusive-create fallback where needed.
- Verify byte length and SHA-256 after staging and after installation.
- Never delete an installed pack because it is absent from the approved manifest or a later VanillaTweaks bundle.
- Never overwrite a different installed version implicitly.
- Never enable/disable, reorder, or remove an existing pack automatically. An already-present but disabled pack is left unchanged.
- No full TAR backup is created by this workflow. Full backups remain a separate, explicitly authorized action.

If a disk or I/O failure interrupts a multi-pack copy after some individual files have been atomically published, report exactly which files were installed. A later plan/sync must be safe to rerun: installed same-hash files become `PRESENT`; no overwrites or deletion are allowed.

## Runtime activation and verification

For a stopped selected server:
- Sync verifies the files on disk and reports they will be loaded on the next normal start.
- It does not start the server.

For a running selected server:
1. After new files are installed and hash-verified, send `reload` to the exact console pane `=<tmux-session>:0.0`.
2. Wait for a positive reload completion response in `logs/latest.log`; a command merely being sent is not proof it completed.
3. Run `datapack list enabled` and verify each newly installed pack appears under its `file/<filename>` id.
4. If a newly added pack is shown under `datapack list available` but not enabled, report that state and do not silently enable it. If it appears in neither list, report runtime discovery failure. Keep the installed files intact for investigation.

Existing packs that were already present but disabled must be reported as such and left untouched. The manager must not change user load order or pack enablement.

Minecraft behavior reference: data packs placed in an existing world's `datapacks` directory are reloaded with `/reload`, and `/datapack list enabled` verifies which packs are active. Certain registry/world-generation content may require reopening/restarting the world rather than an in-place reload. See Minecraft Wiki's [reload command](https://minecraft.wiki/w/Commands/reload), [datapack command](https://minecraft.wiki/w/Commands/datapack), and [multiplayer import instructions](https://minecraft.wiki/w/Tutorial:Importing_a_data_pack).

## Inspected earlier implementation — findings and gaps

Audit basis: the original additive datapack patch was recovered from the ChatGPT project Library and its payload files were extracted and reviewed on 2026-11-12. The exact current WSL branch/worktree was not accessible in this review. Therefore, these are verified findings about that recovered patch version, not a claim that the user's current local files are identical.

### Existing useful behavior

- `bin/hagonoy-datapacks.py` provides registration, bundle registration, listing, plan, and sync commands.
- `bin/hagonoy-datapacks-remote.py` handles target-world inspection and additive installation.
- `config/approved-datapacks.json` stores the approval inventory. Preserve the actual user's copy.
- `tests/datapack-deploy-check.py` uses temporary test worlds; it does not require a live server.
- The remote installer detects exact same-content files, conflicts, duplicate logical identities, directories, and symlinks; it preflights conflicts before writing and retains unselected packs.
- The manager checks that the opposite host is stopped and that the target generation/runtime matches.

### Defects found in that patch version

1. The registration success message falsely said packs would be installed by the next `start` or `update`.
2. The integration patch wired datapack sync/planning into Ubuntu `start`, Windows `start`, and the core `update` path. This contradicts the separate-workflow rule.
3. `./hagonoy addons --plan` was special-routed to the old broad addon inventory, rather than the datapack-only planner. That inventory also mentioned components such as Chunky, which is outside the core update scope.
4. The remote helper recursively deleted its supplied staging path in a `finally` block. Cleanup ownership belongs to the orchestrator that created a manager-generated stage directory; the helper must never delete an arbitrary caller-supplied directory.
5. The manager could leave a staging directory behind if source validation failed during stage construction.
6. The original installer validated each staged ZIP immediately before writing that ZIP. It should validate every pending ZIP first, then begin writes, so an invalid later ZIP cannot cause avoidable partial deployment.
7. On a running server, the original helper only sent `reload` and printed `DATAPACK_RELOAD=REQUESTED`. It did not wait for a completion response or verify the new pack in `/datapack list enabled`.
8. The original test suite covered additive install, idempotence, conflict preflight, identity conflicts, incompatible format rejection, and bundle registration, but not reload/runtime readback or the stage cleanup ownership defect.
9. The installer needs to preserve the distinction between a pack already present but disabled and a newly added pack that fails to become enabled. Never auto-enable an existing disabled pack to make a test appear green.

## Follow-up implementation prepared on 2026-11-12

A separate follow-up bundle was prepared from the recovered baseline. It contains:
- revised `bin/hagonoy-datapacks.py` (registration-only messaging, no implicit prestart action, explicit plan/sync, stage failure cleanup, datapack-only `--plan` compatibility alias);
- revised `bin/hagonoy-datapacks-remote.py` (validated manager-generated stage paths, no self-deletion of stage, whole-batch validation before writes, log-based reload completion check, enabled/available runtime readback);
- expanded `tests/datapack-deploy-check.py` (whole-batch prevalidation and mocked running-runtime verification);
- `apply-followup.py`, a fail-closed patcher that checks exact baseline SHA-256 values, removes automatic start/update integration from both host lifecycle scripts, changes the main command routing/help and inventory wording, then applies the changes atomically.

The patcher:
- does not modify `config/approved-datapacks.json`;
- does not contact Ubuntu or Windows;
- does not run `addons sync`;
- aborts before writing if the three datapack source files do not match the reviewed baseline, so user-local code is not silently overwritten.

The follow-up was tested against a synthetic repository fixture matching the known earlier integration anchors. Python compilation passed. The expanded datapack tests passed in temporary fixture worlds, including a mocked console/log flow confirming reload completion and `/datapack list enabled`. These are offline code tests only, not live-world validation.

The bundle currently exists as a ChatGPT-generated artifact for the user to apply to the WSL checkout. It has not been committed into the user's local branch or the repository by this review. If the local source hashes differ, stop and reconcile rather than forcing the patch.

Additional offline tests were added after the initial record: a newly installed pack that appears under `available` but not `enabled` now fails verification without auto-enabling it; an already-present disabled pack is reported as `AVAILABLE_NOT_ENABLED` and preserved. The expanded test suite passed again on 2026-11-12.

## User-applied follow-up and verification (2026-11-12)

The user successfully extracted and ran `hsmp-datapack-followup/apply-followup.py` in the WSL checkout `~/hagonoy-smp`. The patcher reported all intended changes applied:
- revised datapack manager, remote helper, and datapack tests;
- main `hagonoy addons` routing now points to datapack-only commands;
- automatic datapack hooks removed from Ubuntu and Windows lifecycle integration;
- broad addon inventory wording corrected;
- `config/approved-datapacks.json`, live worlds, server state, and backups unchanged.

The user then ran:
```bash
python3 -m py_compile bin/hagonoy-datapacks.py bin/hagonoy-datapacks-remote.py tests/datapack-deploy-check.py
python3 tests/datapack-deploy-check.py
bash -n bin/hagonoy-dual-lifecycle bin/hagonoy-dual-windows-lifecycle
```
All commands completed successfully. Test output confirmed:
- additive install, idempotence, conflicts, duplicate identities, uncompressed-identity conflict, and incompatible format rejection;
- registration-only behavior and idempotent bundle registration;
- whole-batch validation before world writes;
- running-server reload completion and enabled-pack readback;
- caller-owned stage cleanup and source-failure-before-stage creation;
- newly installed but disabled packs are reported without auto-enabling;
- already-present disabled packs remain untouched and are distinguished from enabled packs.

These are offline fixture tests. The output's registration test used a synthetic two-pack bundle; it does **not** establish the user's real 13-pack manifest/source state or the live server's installed/enabled state. The follow-up patcher explicitly reported the real approval manifest and live worlds unchanged. No `addons sync` or live deployment has been run.

Next safe sequence is to inspect the real manifest with `./hagonoy addons list`, then run the read-only `./hagonoy addons plan --host <actual-authoritative-host>`. Determine the actual host from live host/generation status; do not assume the historical Ubuntu runtime is still current. Review every `PRESENT`, `ADD`, and `CONFLICT` before any sync. `addons sync` remains a separate user-authorized mutation.

## Remaining work

1. Apply/reconcile the follow-up against the exact WSL checkout; preserve the user's actual approval manifest.
2. Inspect the resulting `bin/hagonoy`, Ubuntu lifecycle, Windows lifecycle, and legacy inventory routing; verify no automatic datapack hooks remain.
3. Run Python compilation, datapack fixture tests, shell syntax checks, and focused static checks on those hooks.
4. Inspect the real 13-pack approval manifest and corresponding source ZIPs on the user's machine; confirm filenames, bytes, SHA-256 values, and 26.3 compatibility without changing or deploying anything.
5. Run `addons plan` against the selected canonical host and review every `PRESENT`, `ADD`, and `CONFLICT`.
6. Only after the user explicitly requests a deployment, run the standalone `addons sync` against the selected host. Verify on-disk hashes and, if running, reload completion and `/datapack list enabled`.
7. After the datapack workflow is complete, resume the broader maintenance work and later review host switching/backup tools.

## Continuity discipline

Update this document when a user decision changes, when a code defect is verified/fixed, or when a test or live operation establishes new state. Label observations by source and date. Never store credentials, tokens, private keys, or other secrets. Never claim a live datapack was installed or enabled based on offline fixture tests.


## Live-world planning checkpoint — 2026-11-12

User-provided WSL output establishes this checkpoint:

1. `./hagonoy addons list` printed 13 approved VanillaTweaks ZIP entries, all marked for Minecraft 26.3.
2. `./hagonoy status` printed Ubuntu LIVE as RUNNING and both Windows canonical and Windows staging as STOPPED.
3. `./hagonoy addons plan --host ubuntu` printed `DATAPACK_HOST=UBUNTU`, `DATAPACK_RUNTIME=RUNNING`, exactly 13 `[ADD]` rows (one for every approved manifest entry), and `DATAPACK_PLAN=READY`.

Interpretation:
- The plan sees all 13 approved packs as absent from the selected Ubuntu world and eligible to be added.
- No `PRESENT` or `CONFLICT` row appeared in this plan output.
- `READY` is the manager's planning result, not proof that deployment has happened or that the packs are enabled.
- The plan output does not itself confirm successful file writes, reload completion, or `/datapack list enabled` state.

Deployment gate:
- Do not execute `./hagonoy addons sync --host ubuntu` until the user explicitly authorizes adding these 13 packs to the Ubuntu live world.
- Once authorized, use the standalone addons sync only. Do not route through `start`, `update`, Paper updates, or unrelated plugin maintenance.
- After sync, capture the complete output and verify every expected ZIP on disk by filename and SHA-256. For a running server, confirm reload completion and verify actual pack names in `/datapack list enabled`.
- If a newly added pack is present but disabled, report it accurately; never auto-enable it without separate approval.
- If sync reports any error or runtime verification is incomplete, stop and diagnose before retrying. Do not create a full backup automatically.


## Deployment attempt and runtime timeout — 2026-11-12

The user ran `./hagonoy addons sync --host ubuntu` and provided the complete output.

### What succeeded

The helper emitted `[INSTALLED_AND_HASH_VERIFIED]` for each of the 13 approved packs:

1. afk display v1.1.18 (MC 26.3).zip
2. anti enderman grief v1.1.18 (MC 26.3).zip
3. chunk loaders v1.0.19 (MC 26.3).zip
4. durability ping v1.1.19 (MC 26.3).zip
5. more mob heads v2.20.1 (MC 26.3).zip
6. multiplayer sleep v2.6.18 (MC 26.3).zip
7. name colors v1.0.16 (MC 26.3).zip
8. painting picker v1.1.5 (MC 26.3).zip
9. player head drops v1.1.18 (MC 26.3).zip
10. silence mobs v1.2.12 (MC 26.3).zip
11. track raw statistics v1.7.14 (MC 26.3).zip
12. track statistics v1.1.20 (MC 26.3).zip
13. villager workstation highlights v1.1.18 (MC 26.3).zip

### What failed / remains unknown

After the 13 successful write/hash reports, remote helper output:

`ERROR: Timed out waiting for Minecraft to confirm 'reload'. The command may have run, but its result is unverified. Check /home/leonardodavinci/minecraft-server/logs/latest.log.`

The caller then reported sync failure and exit code 1.

This does not prove reload failed. It proves only that the expected confirmation was not observed before timeout. The server may have accepted the command and completed reload, may still be processing it, or may not have received it. Enabled state is unknown until queried.

### Mandatory recovery sequence

- Do not rerun sync immediately: the 13 archives were already reported installed and hash-verified.
- Do not remove or overwrite any of the files.
- Do not restart or stop the live server just to clear this error.
- Read the relevant recent reload/datapack/error entries from `/home/leonardodavinci/minecraft-server/logs/latest.log`.
- Query the running server with the read-only console command `datapack list enabled` (without slash when sent to the server console) and capture the returned output.
- Verify whether all 13 expected datapacks appear enabled. If they are present but disabled, report that accurately; do not enable them automatically.
- If logs show reload still running, errors, or incomplete datapack loading, diagnose the first concrete failure before another action.
- Once runtime state is known, run the read-only addons plan again only if needed to confirm the on-disk inventory; do not mistake an all-present disk plan for proof of enabled status.
- Do not create a full backup automatically; no backup was part of this operation.

Current status: **files reported installed and hash-verified 13/13; reload confirmation timed out; enabled state unverified.**


## Successful live deployment — 2026-11-12

### Installation result

The user executed `./hagonoy addons sync --host ubuntu`. The sync output reported `[INSTALLED_AND_HASH_VERIFIED]` for all 13 manifest entries:

- afk display v1.1.18 (MC 26.3).zip
- anti enderman grief v1.1.18 (MC 26.3).zip
- chunk loaders v1.0.19 (MC 26.3).zip
- durability ping v1.1.19 (MC 26.3).zip
- more mob heads v2.20.1 (MC 26.3).zip
- multiplayer sleep v2.6.18 (MC 26.3).zip
- name colors v1.0.16 (MC 26.3).zip
- painting picker v1.1.5 (MC 26.3).zip
- player head drops v1.1.18 (MC 26.3).zip
- silence mobs v1.2.12 (MC 26.3).zip
- track raw statistics v1.7.14 (MC 26.3).zip
- track statistics v1.1.20 (MC 26.3).zip
- villager workstation highlights v1.1.18 (MC 26.3).zip

### Runtime confirmation and interpretation

The first sync command exited 1 because the helper timed out waiting for a `reload` acknowledgement. The user then inspected Ubuntu's `logs/latest.log` and queried the live console.

Log evidence:
- `22:22:20`: `System chat: Reloading!`
- `22:22:30` and `22:22:35`: Paper watchdog warnings that the server thread had not responded for 10/15 seconds.
- Thread dump remained in `MinecraftServer.reloadResources` / `ReloadCommand`; the visible stack was parsing YAML through SnakeYAML in Bukkit `HelpYamlReader` / `SimpleHelpMap.initializeGeneralTopics`.
- This establishes that resource reload was in progress and temporarily stalled the main server thread. It does not identify the offending YAML file/plugin or establish why parsing took several minutes.
- `22:26:25`: Minecraft responded to `datapack list enabled` with 16 enabled datapacks.

The enabled list explicitly contains all 13 approved custom datapacks:
1. afk display
2. anti enderman grief
3. chunk loaders
4. durability ping
5. more mob heads
6. multiplayer sleep
7. name colors
8. painting picker
9. player head drops
10. silence mobs
11. track raw statistics
12. track statistics
13. villager workstation highlights

The other 3 entries were `vanilla`, `paper`, and `bukkit` (built-in/server entries). Thus all 13 custom packs are confirmed **enabled**, not merely present as files. The live Ubuntu deployment objective is achieved.

### Remaining tool defect / next engineering phase

The manager treated a slow reload as an operation failure because the remote helper's acknowledgement wait expired before the Minecraft server finished processing reload. The server eventually recovered and answered the read-only enabled-list command. Improve helper behavior so a slow reload is distinguished from a failed reload:

- Inspect current local helper implementation before editing; GitHub main does not contain the user's unpushed working tree source files.
- Keep the timeout bounded, but make the deadline appropriate for real Paper resource reloads and expose elapsed time/progress/status.
- If the reload acknowledgement channel is delayed by the blocked server thread, continue polling safely within the bounded deadline instead of immediately treating the first timeout as failure.
- Always perform final runtime readback using `datapack list enabled`; require all expected approved pack names before reporting complete success.
- If the final response is partial or ambiguous, report `installed; reload/runtime unverified`, not a misleading generic failure or success.
- Add fixture tests for slow acknowledgement, delayed command processing, reload failure, missing enabled packs, and complete success.
- Do not trigger another reload on the live server merely to test the helper. The 13 packs are already successfully enabled.
- Do not auto-reload or re-run sync as part of core server start/update. Datapack management remains a separate workflow.


## Helper timeout correction prepared — 2026-11-12

The exact local helper and test excerpts were supplied by the user. A guarded application bundle has been prepared (not yet applied to WSL):

- Replace the reload completion wait for literal `reload complete` with recognition of `Reloading!` / `Reload complete` as request acceptance (30-second bounded acceptance wait).
- Follow the request with `datapack list enabled`. Minecraft processes the queued console query after the reload operation; this response, not the initial acknowledgement, is the completion barrier.
- Give the enabled-list query a 360-second maximum for slow resource reloads. Print periodic `[WAIT]` messages with elapsed and maximum time.
- Preserve final per-pack enabled verification; only report `DATAPACK_RELOAD=CONFIRMED` after all newly installed packs are confirmed enabled.
- Extend the main runtime fixture to simulate Paper's observed `Reloading!` response and delay the enabled-list response across multiple poll cycles. Assert progress output and successful final runtime verification.
- Exact-anchor guard: the patcher checks each inspected source block occurs exactly once before writing either file. It does not contact Minecraft.
- Application, full fixture test run, and review of the real WSL diff are still pending. Do not rerun sync or reload to test this tooling change; all 13 custom packs are already confirmed enabled in Ubuntu.

### Bundle packaging follow-up — 2026-11-12

The user attempted to invoke the script before extracting the ZIP; consequently `apply-fix.py` was not present at the target path. The original fixture tests they ran still passed against the old helper and therefore do not validate the proposed slow-reload fix. Their `git diff --check` reported a new blank line at EOF in `tests/datapack-deploy-check.py`.

A refreshed archive, `hsmp-reload-confirmation-fix-v2.zip`, was created and verified with `unzip -t`. Its patcher keeps the same exact-anchor guards and additionally normalizes trailing newlines in the edited test file. It remains unapplied; do not assume the local helper has changed.

Correct WSL application sequence:
```bash
cd ~/hagonoy-smp &&
unzip -o /mnt/c/Users/lemue/Downloads/hsmp-reload-confirmation-fix-v2.zip -d /mnt/c/Users/lemue/Downloads &&
python3 /mnt/c/Users/lemue/Downloads/hsmp-reload-confirmation-fix/apply-fix.py .
```
Then run py_compile, the datapack fixture test, and `git diff --check`. This remains offline code maintenance only; do not rerun live sync/reload.
