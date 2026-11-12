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
