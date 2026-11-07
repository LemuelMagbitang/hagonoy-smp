# First recovery checklist

1. Keep the existing `minecraft-server` directory untouched.
2. Confirm where the authoritative world currently lives. Do not assume timestamps alone prove which copy is newest.
3. Clone/install this manager beside the server directory, not inside the live server directory.
4. Set `MC_DIR` to the existing server path in `config/manager.conf`.
5. Run `./hagonoy doctor` and resolve path/dependency errors.
6. Run `./hagonoy status` and confirm no other copy of the server is active.
7. Make a backup to a disk with enough free space and confirm the archive passes `tar -tf`.
8. For a recovery rehearsal, use `./hagonoy restore <backup.tar> <new-empty-destination>`. The destination must not exist; the command does not start the restored server.
9. Inspect the recovered files and world data before considering any cutover. Keep the original server directory and backup unchanged.
10. Start with `./hagonoy start`; inspect the console with `./hagonoy attach` if readiness is not detected.
11. Verify local LAN connectivity before testing Playit.
12. Enable Playit automation only after its local agent is confirmed working.

Never restore over the live server directory. Never run two copies of the same world simultaneously.
