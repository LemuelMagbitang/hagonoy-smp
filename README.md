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

The installer adds Git, tmux, rsync, tar, core utilities, and `ss` (from iproute2). It does **not** install Java or Playit because the correct Java version depends on the server version, and Playit should use your existing account/agent configuration.

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

Run the restore safety tests with:

```bash
bash tests/restore-check.sh
```

## 8. Playit.gg (optional)

First confirm that the Playit agent works when run manually as your Ubuntu user. Then edit `config/manager.conf`:

```bash
PLAYIT_AUTO_START="true"
PLAYIT_COMMAND="playit"
PLAYIT_SESSION="playit-tunnel"
PLAYIT_STOP_WITH_SERVER="false"
```

Then use:

```bash
./hagonoy playit-start
./hagonoy status
./hagonoy playit-stop
```

Do not upload Playit credentials or agent configuration. The manager only invokes the local `playit` command; it does not manage your Playit website tunnel assignments.

## 9. Updating the manager

After cloning and pushing the project to GitHub, update only the manager checkout with:

```bash
./hagonoy update-manager
```

It refuses to pull if local manager files have uncommitted changes and uses `git pull --ff-only`. This command does not update Minecraft itself.

## Recovery and safety

- Never copy or synchronize a live world directory while Minecraft is writing to it.
- Never run the server simultaneously from the Ubuntu laptop and Windows copy if both point to independently edited worlds.
- Before changing server versions, Java versions, loaders, or plugins, take a backup and verify compatibility.
- Do not delete the old Minecraft directory until the new manager has started the intended world and a separate backup has been verified.

## Hardware notes

The ASUS laptop has 2 GB RAM and an older Intel Celeron N3060. This manager itself has a very small resource footprint, but Minecraft's Java heap and server software determine most of the load. Do not blindly copy memory flags from another machine or a different Minecraft version. Confirm the actual Minecraft version, server type (Vanilla/Paper/Spigot/Fabric/Forge/etc.), and current `start.sh` before changing Java flags.

## Current scope / later work

Version 1 is intentionally a single-host Ubuntu manager. Once its paths and startup behaviour are verified, remote backup to the Windows PC or another storage device can be added as a separate, explicit backup target. That avoids bringing back the old scripts' dangerous active-server detection and overwrite behaviour prematurely.
