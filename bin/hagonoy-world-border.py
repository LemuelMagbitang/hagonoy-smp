#!/usr/bin/env python3
"""Plan-first bidirectional Overworld/Nether border synchronizer."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "dual-host.conf"
STATE = ROOT / ".hagonoy-world-border-state.json"
OVERWORLD = "minecraft:overworld"
NETHER = "minecraft:the_nether"
END = "minecraft:the_end"
DIMENSIONS = (OVERWORLD, NETHER, END)
LABELS = {OVERWORLD: "Overworld", NETHER: "Nether", END: "End"}
# Current, user-confirmed centers are informational and intentionally untouched.
CENTERS = {
    OVERWORLD: ("-2349", "38"),
    NETHER: ("-293", "4"),
    END: ("0", "0"),
}
SCALE = 8.0
WIDTH_RE = re.compile(
    r"world border is currently\s+([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
    r"\s+(?:blocks?|block\(s\))\s+wide",
    re.IGNORECASE,
)


def fail(message: str) -> "NoReturn":
    print(f"[hagonoy] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(args: list[str], *, timeout: int = 15) -> str:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"Command failed: {args[0]} ({exc})")
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"Command failed ({args[0]}): {detail or result.returncode}")
    return result.stdout.strip()


def config_values() -> tuple[str, str, str, str]:
    if not CONFIG.is_file():
        fail(f"Missing coordinator configuration: {CONFIG}")
    code = (
        'source "$1" || exit 1; '
        'printf "%s\\0" "$WINDOWS_TMUX_SESSION" "$UBUNTU_SSH_TARGET" '
        '"$UBUNTU_TMUX_SESSION" "$MINECRAFT_PORT"'
    )
    output = run(["bash", "-c", code, "bash", str(CONFIG)])
    values = output.rstrip("\0").split("\0")
    if len(values) != 4 or any(not value for value in values):
        fail("Dual-host configuration is missing a required border-maintenance setting.")
    return tuple(values)  # type: ignore[return-value]


def chunky_settings() -> dict[str, str]:
    if not CONFIG.is_file():
        fail(f"Missing coordinator configuration: {CONFIG}")
    code = (
        'source "$1" || exit 1; '
        'printf "%s\\0" "$WINDOWS_SERVER_DIR" "$UBUNTU_SERVER_DIR" '
        '"${CHUNKY_OVERWORLD_WORLD:-world}" '
        '"${CHUNKY_NETHER_WORLD:-world_nether}" '
        '"${CHUNKY_END_WORLD:-world_the_end}" '
        '"${CHUNKY_RATE_LIMIT:-1}"'
    )
    output = run(["bash", "-c", code, "bash", str(CONFIG)])
    values = output.rstrip("\0").split("\0")
    if len(values) != 6 or any(not value for value in values):
        fail("Dual-host configuration is missing the server directories required by Chunky pre-generation.")
    for name in values[2:5]:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
            fail(f"Unsafe/unsupported Chunky Bukkit world name in config: {name!r}")
    if not values[5].isdigit() or int(values[5]) < 0 or int(values[5]) > 1000:
        fail("CHUNKY_RATE_LIMIT must be an integer from 0 through 1000.")
    return {
        "windows_server_dir": values[0],
        "ubuntu_server_dir": values[1],
        "overworld": values[2],
        "nether": values[3],
        "end": values[4],
        "rate_limit": values[5],
    }


def run_chunky_helper(
    mode: str,
    host: str,
    target: str,
    session: str,
    server_dir: str,
    settings: dict[str, str],
) -> None:
    helper = ROOT / "bin" / "hagonoy_chunky_pregen.py"
    if not helper.is_file():
        fail(f"Missing Chunky pre-generation helper: {helper}")
    args = [
        sys.executable, str(helper), mode, host, target, session, server_dir,
        settings["overworld"], settings["nether"], settings["end"], settings["rate_limit"],
    ]
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=240, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"Chunky pre-generation helper could not complete: {exc}")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"Chunky pre-generation did not complete successfully: {detail or result.returncode}")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")


def tmux_pane_target(session: str) -> str:
    return f"={session}:"


def windows_state(session: str, port: str) -> str:
    session_running = subprocess.run(
        ["tmux", "has-session", "-t", f"={session}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    command = (
        f"$c=Get-NetTCPConnection -State Listen -LocalPort {int(port)} "
        "-ErrorAction SilentlyContinue; if ($c) {'LISTENING'} else {'STOPPED'}"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            text=True, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    port_state = result.stdout.strip().replace("\r", "") if result.returncode == 0 else "UNKNOWN"
    if session_running and port_state == "LISTENING":
        return "RUNNING"
    if not session_running and port_state == "STOPPED":
        return "STOPPED"
    return "UNKNOWN"


def ubuntu_state(target: str, session: str, port: str) -> str:
    code = (
        f"if tmux has-session -t '={session}' 2>/dev/null && "
        f"ss -H -ltn 'sport = :{int(port)}' 2>/dev/null | grep -q .; then "
        "echo RUNNING; "
        f"elif ! tmux has-session -t '={session}' 2>/dev/null && "
        f"! ss -H -ltn 'sport = :{int(port)}' 2>/dev/null | grep -q .; then "
        "echo STOPPED; else echo UNKNOWN; fi"
    )
    try:
        result = subprocess.run(
            ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, code],
            text=True, capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    if result.returncode:
        return "UNKNOWN"
    value = result.stdout.strip()
    return value if value in {"RUNNING", "STOPPED"} else "UNKNOWN"


def console_send(host: str, target: str, session: str, command: str) -> None:
    if host == "WINDOWS":
        run(["tmux", "send-keys", "-t", tmux_pane_target(session), command, "C-m"])
    else:
        remote = (
            "tmux send-keys -t " + shlex.quote(tmux_pane_target(session)) + " "
            + shlex.quote(command) + " C-m"
        )
        run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, remote])


def console_capture(host: str, target: str, session: str) -> str:
    if host == "WINDOWS":
        return run(["tmux", "capture-pane", "-p", "-t", tmux_pane_target(session), "-S", "-120"])
    return run([
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target,
        "tmux", "capture-pane", "-p", "-t", tmux_pane_target(session), "-S", "-120",
    ])


def query_width(host: str, target: str, session: str, dimension: str) -> float:
    command = f"execute in {dimension} run worldborder get"
    before = console_capture(host, target, session)
    before_count = len(WIDTH_RE.findall(before))
    console_send(host, target, session, command)
    deadline = time.monotonic() + 8
    latest = before
    while time.monotonic() < deadline:
        time.sleep(0.25)
        latest = console_capture(host, target, session)
        matches = WIDTH_RE.findall(latest)
        if len(matches) > before_count:
            return float(matches[-1])
    tail = "\n".join(latest.splitlines()[-12:])
    fail(
        f"Could not read the {dimension} border width from the server console. "
        f"Expected the normal 'world border is currently ... block(s) wide' reply.\n{tail}"
    )


def ratio_matches(widths: dict[str, float]) -> bool:
    return abs(widths[OVERWORLD] - widths[NETHER] * SCALE) <= 0.01


def load_state() -> dict[str, float] | None:
    if not STATE.exists():
        return None
    try:
        raw = json.loads(STATE.read_text(encoding="utf-8"))
        if raw.get("schema") != 1:
            fail(f"Unsupported world-border state schema in {STATE}.")
        widths = raw["widths"]
        result = {OVERWORLD: float(widths[OVERWORLD]), NETHER: float(widths[NETHER])}
        if any(value <= 0 for value in result.values()):
            fail(f"Invalid non-positive width in {STATE}.")
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail(f"Cannot read valid world-border synchronization state {STATE}: {exc}")


def save_state(widths: dict[str, float]) -> None:
    payload = {
        "schema": 1,
        "scale": 8,
        "widths": {
            OVERWORLD: widths[OVERWORLD],
            NETHER: widths[NETHER],
        },
        "note": "Last successfully verified Overworld/Nether border diameters. End is independent.",
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".hagonoy-world-border-", dir=STATE.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def calculate_targets(
    current: dict[str, float], previous: dict[str, float] | None
) -> tuple[dict[str, float], str, bool]:
    """Return target widths, explanation, and whether this is state initialization."""
    if previous is None:
        if not ratio_matches(current):
            fail(
                "No synchronization baseline exists and the live Overworld/Nether widths "
                "are not in an 8:1 ratio. Refusing to guess which dimension is authoritative."
            )
        return dict(current), "Initialize baseline from the already-matching live borders", True

    ow_changed = abs(current[OVERWORLD] - previous[OVERWORLD]) > 0.01
    nether_changed = abs(current[NETHER] - previous[NETHER]) > 0.01

    if not ow_changed and not nether_changed:
        if not ratio_matches(current):
            fail("Live borders no longer match the saved 8:1 baseline; refusing an ambiguous sync.")
        return dict(current), "No changes detected; borders are already synchronized", False

    if ow_changed and nether_changed:
        if not ratio_matches(current):
            fail(
                "Both Overworld and Nether widths changed since the last sync and no longer "
                "match 8:1. Choose one authoritative dimension manually; no changes were made."
            )
        return dict(current), "Both dimensions were changed and already agree at 8:1", False

    if ow_changed:
        target = {OVERWORLD: current[OVERWORLD], NETHER: current[OVERWORLD] / SCALE}
        return target, "Overworld changed; derive Nether diameter = Overworld / 8", False

    target = {NETHER: current[NETHER], OVERWORLD: current[NETHER] * SCALE}
    return target, "Nether changed; derive Overworld diameter = Nether * 8", False


def display_plan(
    current: dict[str, float],
    targets: dict[str, float],
    end_width: float,
    explanation: str,
    initializing: bool,
) -> None:
    print("========== HSMP WORLD-BORDER SYNCHRONIZATION PLAN ==========")
    print("Border widths below are full diameters. Minecraft horizontal axes are X and Z; Y is unused.")
    print("Overworld/Nether coordinate and diameter scale: 8:1.")
    print()
    print(f"Decision: {explanation}")
    for dimension in (OVERWORLD, NETHER):
        now, target = current[dimension], targets[dimension]
        delta = target - now
        change = "no change" if abs(delta) <= 0.01 else f"{delta:+g} blocks"
        center = CENTERS[dimension]
        print(f"{LABELS[dimension]}:")
        print(f"  Current diameter: {now:g}")
        print(f"  Planned diameter: {target:g} ({change})")
        print(f"  Center reference: X {center[0]}, Z {center[1]} (not queried or modified)")
    print(f"End:")
    print(f"  Current diameter: {end_width:g} (independent; will not be changed)")
    print(f"  Center reference: X {CENTERS[END][0]}, Z {CENTERS[END][1]} (not queried or modified)")
    if initializing:
        print()
        print("No world-border command is needed. --apply will record the current verified widths as the baseline.")
    print()
    print("The synchronizer changes diameters only. It does not move centers, edit the End, or restart the server.")


def apply_targets(
    host: str, target: str, session: str, current: dict[str, float],
    targets: dict[str, float], end_width: float
) -> None:
    for dimension in (OVERWORLD, NETHER):
        desired = targets[dimension]
        if abs(current[dimension] - desired) <= 0.01:
            continue
        console_send(
            host, target, session,
            f"execute in {dimension} run worldborder set {desired:.12g} 0",
        )

    after = {
        dimension: query_width(host, target, session, dimension)
        for dimension in DIMENSIONS
    }
    for dimension in (OVERWORLD, NETHER):
        expected = targets[dimension]
        if abs(after[dimension] - expected) > 0.01:
            fail(
                f"{LABELS[dimension]} width verification failed: expected {expected:g}, "
                f"got {after[dimension]:g}. The baseline was not updated; inspect the server console."
            )
    if abs(after[END] - end_width) > 0.01:
        fail(
            f"End width changed unexpectedly during synchronization "
            f"({end_width:g} -> {after[END]:g}). The baseline was not updated."
        )
    if not ratio_matches(after):
        fail("Post-apply Overworld/Nether 8:1 verification failed. The baseline was not updated.")

    try:
        save_state(after)
    except OSError as exc:
        fail(
            f"Borders were verified, but the local synchronization baseline could not be saved: {exc}. "
            "Do not repeat changes blindly; inspect the live widths first."
        )

    print()
    print("[hagonoy] Verified synchronized diameters:")
    print(f"  Overworld: {after[OVERWORLD]:g}")
    print(f"  Nether:    {after[NETHER]:g}")
    print(f"  End:       {after[END]:g} (unchanged)")
    print("[hagonoy] Synchronization baseline saved. Border centers were not modified.")
    print("[hagonoy] No server restart was requested.")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"--plan", "--apply", "--chunks-status"}:
        fail("Usage: ./hagonoy border --plan|--apply|--chunks-status")

    windows_session, ubuntu_target, ubuntu_session, port = config_values()
    chunky = chunky_settings()
    win = windows_state(windows_session, port)
    ubu = ubuntu_state(ubuntu_target, ubuntu_session, port)
    print(f"Windows canonical: {win}")
    print(f"Ubuntu canonical:  {ubu}")
    if win == "UNKNOWN" or ubu == "UNKNOWN":
        fail("A host state is uncertain. No border command was sent.")
    if win == "RUNNING" and ubu == "RUNNING":
        fail("Both canonical servers appear to be running. Refusing to target either.")
    if win == "STOPPED" and ubu == "STOPPED":
        fail("Both canonical servers are stopped. Start the authoritative server first.")

    if ubu == "RUNNING":
        host, target, session = "UBUNTU", ubuntu_target, ubuntu_session
    else:
        host, target, session = "WINDOWS", "", windows_session

    server_dir = chunky["windows_server_dir"] if host == "WINDOWS" else chunky["ubuntu_server_dir"]
    if sys.argv[1] == "--chunks-status":
        run_chunky_helper("--status", host, target, session, server_dir, chunky)
        return

    current = {
        dimension: query_width(host, target, session, dimension)
        for dimension in DIMENSIONS
    }
    pair = {OVERWORLD: current[OVERWORLD], NETHER: current[NETHER]}
    targets, explanation, initializing = calculate_targets(pair, load_state())
    display_plan(pair, targets, current[END], explanation, initializing)

    print()
    print("Chunky will import the live center/radius and pre-generate the square selection independently for all three configured worlds.")
    print(f"Chunky rate limit: {chunky['rate_limit']} chunks/second per world (0 = unlimited).")

    if sys.argv[1] == "--plan":
        print("[hagonoy] PLAN ONLY. No world-border settings or synchronization state were changed.")
        return

    run_chunky_helper("--preflight", host, target, session, server_dir, chunky)

    shrink = any(targets[d] < pair[d] - 0.01 for d in (OVERWORLD, NETHER))
    phrase = (
        f"APPLY HSMP BORDER OW {targets[OVERWORLD]:g} NETHER {targets[NETHER]:g}"
        + (" ALLOW-SHRINK" if shrink else "")
    )
    print()
    if shrink:
        print("[hagonoy] WARNING: This plan shrinks at least one live border.")
        print("[hagonoy] Players near the affected edge may become outside the new border.")
    print("Only Overworld and Nether diameters can change. Centers and End remain untouched.")
    print(f"To confirm this exact plan, type: {phrase}")
    answer = input("> ").strip()
    if answer != phrase:
        print("[hagonoy] Cancelled. No world-border settings or synchronization state were changed.")
        return
    apply_targets(host, target, session, pair, targets, current[END])
    run_chunky_helper("--run", host, target, session, server_dir, chunky)


if __name__ == "__main__":
    main()
