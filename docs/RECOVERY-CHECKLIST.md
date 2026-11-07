# First recovery checklist

1. Keep the existing `minecraft-server` directory untouched.
2. Confirm where the authoritative world currently lives. Do not assume timestamps alone prove which copy is newest.
3. Clone/install this manager beside the server directory, not inside the live server directory.
4. Set `MC_DIR` to the existing server path in `config/manager.conf`.
5. Run `./hagonoy doctor` and resolve path/dependency errors.
6. Run `./hagonoy status` and confirm no other copy of the server is active.
7. Make a backup to a disk with enough free space.
8. Start with `./hagonoy start`; inspect the console with `./hagonoy attach` if readiness is not detected.
9. Verify local LAN connectivity before testing Playit.
10. Enable Playit automation only after its local agent is confirmed working.
