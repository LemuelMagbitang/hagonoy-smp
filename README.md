# Hagonoy SMP Manager

A small Bash-based management tool for running the Hagonoy Minecraft Java server on the Ubuntu laptop. It uses `tmux` to keep the server running after SSH disconnects and deliberately keeps the live Minecraft directory outside this Git repository.

## Design principles

- **One authoritative live server.** Version 1 manages one Ubuntu host. It does not synchronize two active world copies between Windows and Ubuntu.
- **World data stays outside Git.** Only scripts, documentation, and a safe configuration template belong in this repository.
- **Graceful shutdown only.** The manager sends `save-all flush` and `stop`; it never uses `tmux kill-session`, `kill -9`, or deletes `logs/latest.log`.
- **Backups are uncompressed.** This avoids spending scarce CPU/RAM on compression on the Celeron laptop. Backups can be several gigabytes, so use a separate disk when possible.
- **Playit is optional.** The manager does not start the Playit agent until explicitly enabled in local config.
- **No automatic Minecraft update.** Updating the server jar, mod loader, plugins, or world format is a separate, deliberate operation.

## Before connecting the manager to the live server

Run the read-only host diagnostic on the Ubuntu laptop before changing configuration:

```bash
chmod +x tools/collect-host-info.sh
./tools/collect-host-info.sh
```

You can pass the existing server folder as an argument when it is not at the default path:

```bash
./tools/collect-host-info.sh "/absolute/path/to/your/server"
```

It reports Ubuntu/kernel, CPU, RAM/swap, disk and mount information, relevant command availability, tmux session names, and recognizable Minecraft server files. It does not start or stop Minecraft, alter files, or print process arguments or credentials. The output can contain usernames, filesystem labels, and mount paths, so redact anything you do not want to share.

Do not run `./hagonoy start`, `stop`, or `backup` until the real server path and the exact startup command have been confirmed.

## 1. Clone the repository

On the Ubuntu laptop:

```bash
git clone https://github.com/LemuelMagbitang/hagonoy-smp.git
cd hagonoy-smp
```

The repository already contains the manager files. Clone it directly; do not initialize a replacement repository or copy the live Minecraft server into this folder.

## 2. Install basic dependencies

```bash
chmod +x install.sh ./hagonoy ./bin/hagonoy ./tools/collect-host-info.sh
./install.sh
```

The installer adds Git, tmux, rsync, tar, core utilities, `ss` (from iproute2), `curl`, and `jq`. It does **not** install Java or Playit because the correct Java version depends on the server version, and Playit should use your existing account/agent configuration.

## 3. Configure the live server path

```bash
nano config/manager.conf
```

The installer creates this local file from `config/manager.conf.example`. Confirm at least:

```bash
MC_DIR="$HOME/minecraft-server"
TMUX_SESSION="mcserver"
START_COMMAND="./start.sh"
MINECRAFT_PORT="25565"
```

`MC_DIR` must point to the existing live server folder. `START_COMMAND` should be the exact command you currently use to start Minecraft from that folder. The manager runs it from `MC_DIR`.

Keep the real `manager.conf` local. It is ignored by Git. Do not put passwords, SSH keys, or Playit tokens in it.

## 4. Check before starting

```bash
./hagonoy doctor
./hagonoy status
```

Resolve missing dependencies and path errors before starting anything. Confirm that no second Minecraft server is running elsewhere with the same world.

## 5. Basic operation

```bash
./hagonoy start
./hagonoy status
./hagonoy attach
./hagonoy stop
```

When attached to the console, press `Ctrl+B`, then lowercase `d` to detach without stopping Minecraft. Do not close the server using `tmux kill-session`.

You can run these commands over SSH from your Windows computer. SSH into the Ubuntu laptop, `cd` to the manager repository, and run `./hagonoy status`; the server continues inside tmux after the SSH connection closes.

The manager waits for the configured `READY_PATTERN` in newly written content in `SERVER_LOG`. The default is `Done` in `logs/latest.log`, which matches the common Java server startup message. If your server software writes a different message or log path, adjust these settings.

## 6. Backups

```bash
./hagonoy backup
```

If Minecraft is running in the configured tmux session, the manager sends a save/stop sequence, creates a backup, and starts the server again. If Minecraft is listening on the configured port without the managed tmux session, backup is refused so it cannot silently archive a live world.

Backups are uncompressed `.tar` files. Logs and crash reports are excluded; world folders, plugin/mod data, server settings, and other server files are included. Before a backup is finalized, the manager runs `tar -tf` against the temporary archive to check that its archive structure can be read. This is a structural check, not a substitute for periodically restoring a backup into a separate test directory.

For the two-host installation, use `./bin/hagonoy-dual-backup --plan` to preview a cross-host backup. The matching `--execute` operation creates one complete TAR archive from the running authoritative host, verifies it, and stores byte-identical copies in the configured Windows and Ubuntu `server-backup` directories. It gracefully stops the source server for a consistent full-directory snapshot and attempts to restart it automatically afterward; do not run it during active play.

Two-host archive names record the source host, Minecraft version, Paper version/build, generation, and local timestamp. For example: `hagonoy-smp-ubuntu-mc26.3-paper26.3-244-gen6-20261110T223000+0800.tar`. The server's `.hagonoy-generation.json` is included inside the complete archive. The backup script refuses to proceed if the source generation manifest does not match the active host and running generation.

Hagonoy never automatically deletes existing backup archives. The legacy `BACKUP_RETENTION` setting is accepted for configuration compatibility but does not trigger cleanup. Existing recovery archives must be reviewed and removed manually, with explicit authorization.

**Important:** `~/minecraft-backups` is on the same disk by default. This protects against mistakes but not HDD failure. For real disaster recovery, set `BACKUP_DIR` to a mounted external drive or a different machine, and periodically test restoring a backup into a separate test directory. Ensure the target disk has enough free space for another full server copy.

## 7. Restore a backup safely

Restore only into a **new destination directory**. The command refuses to run while the managed Minecraft tmux session exists or the configured Java port is listening. It accepts only `hagonoy-smp-*.tar` archives inside `BACKUP_DIR`, checks the archive structure and member paths, and refuses destinations that already exist or are inside the live server, Git checkout, or backup directory.

Example:

```bash
./hagonoy restore \
  "$HOME/minecraft-backups/hagonoy-smp-20261107-024756.tar" \
  "$HOME/minecraft-restore-test/recovered-copy"
```

Hagonoy extracts into a temporary sibling directory first. It promotes that directory to the requested destination only after extraction succeeds and the top-level `server.properties` plus configured relative startup file are present. It does **not** start the restored server. Inspect the copy before deciding to use it. Failed extractions are left in their temporary directory for inspection; they do not overwrite the requested destination.

Run the isolated restore, Playit, and Paper updater safety tests with:

```bash
bash tests/restore-check.sh
bash tests/playit-detection-check.sh
bash tests/paper-update-check.sh
```

The Paper updater test uses a temporary fake server and mocked Paper API/download responses. It tests successful installation and rollback after a simulated readiness failure; it does not contact PaperMC or touch the live Minecraft directory.

## 8. Paper stable-build updates

The Paper updater checks the installed Paper version/build from the latest startup entry in `logs/latest.log`. It queries the official PaperMC Fill Downloads API v3 for the newest **STABLE build of that exact Minecraft version**. It never silently moves the world to a different Minecraft version.

Check without changing any server files:

```bash
./hagonoy paper-check
```

When you are ready to update, run:

```bash
./hagonoy paper-update
```

The update command requires the managed Minecraft server to be running and listening. It presents the exact Minecraft version and target Paper build, then asks for interactive confirmation. After approval it downloads to a temporary file outside the live server directory, checks the API-reported size and SHA-256, and verifies the file is a readable JAR. It then creates and structurally verifies a pre-update backup, gracefully stops Minecraft, preserves the previous JAR, replaces the configured `PAPER_JAR`, and starts the server.

The updater accepts only stable builds and only updates within the already-installed Minecraft version. It does not update plugins, Geyser, Floodgate, Java, or the Minecraft version. After the server reports readiness, inspect the new startup log for plugin warnings; the readiness check does not prove every plugin works correctly. The pre-update TAR backup contains the original JAR as an additional recovery path. Previous Paper JARs are retained indefinitely; the legacy `PAPER_PREVIOUS_JAR_RETENTION` setting is accepted for compatibility but does not trigger cleanup. If the new server does not pass the configured readiness check and report the expected Paper version/build, Hagonoy attempts a graceful stop, restores the previous JAR, and starts the previous build. It never force-kills Java or replaces a JAR while the server may still be running.

Keep `PAPER_JAR` aligned with the JAR referenced by your configured startup script. For this server it is `server.jar`. Paper's own guidance recommends manual supervision and a working backup strategy for updates; this command always asks for approval and does not perform automatic updates.

The checker/updater requires `curl`, `jq`, `sha256sum`, and Python 3. Python's standard ZIP library verifies the downloaded JAR structure without requiring a full JDK `jar` utility. The repository installer adds `curl`, `jq`, and Python 3; Java itself is managed separately.

## 9. HSMP maintenance: world borders and addon inventory

The WSL dual-host coordinator includes a read-only world-border plan:

```bash
./hagonoy border --plan
```

The approved targets are full border diameters, not radii: Overworld 12,500 centered at X=-2349, Z=38; Nether 3,125 centered at X=-293.625, Z=4.75; and End diameter unchanged (the recorded baseline is 20,000) centered at X=0, Z=0. The Nether center is the Overworld center divided by eight. The End diameter is never set by this command.

To apply the Overworld and Nether expansion and set all three centers:

```bash
./hagonoy border --apply
```

The command checks which canonical host is running and reads all three current diameters. It refuses uncertain or dual-running host states and refuses to shrink an Overworld or Nether border that is already wider than its target. It then requires the exact interactive phrase `APPLY HSMP BORDER 12500 3125 KEEP-END`, applies dimension-specific commands, and verifies the resulting diameters. The End diameter is queried before and after and must remain unchanged. Border application does not restart Minecraft.

The one-command update preview is read-only:

```bash
./hagonoy update --plan
```

The equivalent component-specific command is `./hagonoy addons --plan`.

It lists every file in `D:\Hagonoy-SMP\server-update-downloads`, compares downloaded Paper/plugin metadata and SHA-256 hashes with the installed server, and inspects the nested datapack ZIPs in `VanillaTweaks_d831085_UNZIP_ME.zip`. A Paper candidate must match the newest stable build reported by the official PaperMC Fill API, including its published size and SHA-256, before it is marked verified. Plugin JARs are checked for ZIP integrity, descriptor versions and binary hashes. Chunky is compared with Modrinth's Paper/26.3 release metadata; Geyser and Floodgate artifacts are compared with GeyserMC's published Spigot/Paper build hashes. The publisher's latest stable artifact is checked before treating an identical installed/downloaded hash as already current, so an old matching file cannot hide a newer release. API-version declarations alone are not treated as proof of compatibility. That `UNZIP_ME` bundle is the authoritative selected set; `VanillaTweaks-26.3.zip` is displayed for comparison only and is not merged into the selected set. This prevents packs omitted from the selected bundle from being re-added from the secondary ZIP. The inventory checks each nested `pack.mcmeta` against Minecraft 26.3 data-pack format 121.0.

To apply the reviewed update selection, run:

```bash
./hagonoy update --execute
```

The deployment command rebuilds the plan from the current download folder and active canonical host. It refuses an ambiguous/dual-running host, a cross-Minecraft-version Paper candidate, an unverified Paper/plugin artifact, or a datapack whose metadata does not declare 26.3 format 121.0. The secondary VanillaTweaks ZIP is never merged into the selected set.

It asks for one explicit confirmation: `APPLY HSMP SERVER UPDATES`. It then creates a complete pre-update TAR with matching SHA-256 copies in both canonical `server-backup` folders and leaves the authoritative server stopped while it stages changes. When `pv` is installed, archive creation displays byte/percentage/speed/ETA progress; the cross-host transfer and staged/rollback copies use `rsync --info=progress2`. `pv` is optional. Paper is installed as the configured `server.jar`; verified plugin JARs replace the corresponding older JARs; all 13 datapacks from the selected `UNZIP_ME` bundle are reconciled into `world/datapacks`. Older active/disabled VanillaTweaks ZIPs absent from that bundle are retired without separate prompts. Unrelated datapacks and plugin configuration folders are preserved.

After deployment, Hagonoy starts the same authoritative host and verifies the Paper build, plugin JAR hashes, selected datapack hashes and critical plugin-load errors in the new startup log. If verification fails and the server can be safely stopped, the updater re-checks the TAR SHA-256, restores the complete pre-update archive using a staged full-directory restore, and starts the previous server generation only if the secondary host remains stopped. If the backup check fails after the initial stop, the updater restarts the unchanged source only when both hosts are confirmed stopped. If either host is running or uncertain, it avoids a restart that could create split brain and retains the verified backup for recovery.

The command does not automatically copy the updated world to the secondary canonical host. Use the existing generation-verified `./hagonoy pull --plan` / `--execute` workflow separately when you are ready to synchronize the stopped Windows secondary. The updater does not change any world border.

The machine-specific ignored `config/dual-host.conf` must point Windows backups at `/mnt/d/Hagonoy-SMP/server-backup`; the updater refuses to run its pre-update backup while that setting still points at the legacy vault.
## 10. Playit.gg (optional)

On Ubuntu, installing Playit through its APT package can create a systemd service named `playit.service` that runs the agent in the background. Check it with:

```bash
systemctl is-active playit
sudo systemctl status playit --no-pager
systemctl is-enabled playit
```

Hagonoy detects an active `playit.service` and reports `Playit agent: RUNNING (systemd service)`. It will not launch a duplicate tmux agent when the system service or another `playitd` process is already active.

`PLAYIT_AUTO_START="false"` disables only Hagonoy's optional tmux-based auto-start. It does not stop, disable, or override the independent systemd service. The Ubuntu service may start automatically at boot if it is enabled.

When no Playit service or process is active, manual Hagonoy controls are available:

```bash
./hagonoy playit-start
./hagonoy status
./hagonoy playit-stop
```

`playit-stop` stops only the Playit process inside Hagonoy's tmux session. If the agent is managed by systemd, Hagonoy refuses to stop it; only use `sudo systemctl stop playit` when you deliberately want the system agent offline.

Do not upload Playit credentials or agent configuration. Hagonoy does not manage website tunnel assignments or transfer tunnels between agents.

## 11. Updating the manager

After cloning and pushing the project to GitHub, update only the manager checkout with:

```bash
./hagonoy update-manager
```

It refuses to pull if local manager files have uncommitted changes and uses `git pull --ff-only`. This command does not update Minecraft itself.

## 12. Recovery and safety

- Never copy or synchronize a live world directory while Minecraft is writing to it.
- Never run the server simultaneously from the Ubuntu laptop and Windows copy if both point to independently edited worlds.
- Before changing server versions, Java versions, loaders, or plugins, take a backup and verify compatibility.
- Do not delete the old Minecraft directory until the new manager has started the intended world and a separate backup has been verified.

## 13. Hardware notes

The ASUS laptop has 2 GB RAM and an older Intel Celeron N3060. This manager itself has a very small resource footprint, but Minecraft's Java heap and server software determine most of the load. Do not blindly copy memory flags from another machine or a different Minecraft version. Confirm the actual Minecraft version, server type (Vanilla/Paper/Spigot/Fabric/Forge/etc.), and current `start.sh` before changing Java flags.

## 14. Current scope / later work

Version 1 is intentionally a single-host Ubuntu manager. Once its paths and startup behaviour are verified, remote backup to the Windows PC or another storage device can be added as a separate, explicit backup target. That avoids bringing back the old scripts' dangerous active-server detection and overwrite behaviour prematurely.
