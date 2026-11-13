#!/usr/bin/env python3
"""Plan-first world-border maintenance for the HSMP dual-host coordinator."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "dual-host.conf"

# Border diameters are full widths, not radii.
TARGETS = {
    "minecraft:overworld": {
        "label": "Overworld",
        "center": ("-2349", "38"),
        "diameter": 12500,
        "change_diameter": True,
    },
    "minecraft:the_nether": {
        "label": "Nether",
        "center": ("-293.625", "4.75"),
        "diameter": 3125,
        "change_diameter": True,
    },
    "minecraft:the_end": {
        "label": "End",
        "center": ("0", "0"),
        "diameter": 20000,
        "change_diameter": False,
    },
}
WIDTH_RE = re.compile(
    r"world border is currently\s+([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s+blocks?\s+wide",
    re.IGNORECASE,
)


def tmux_pane_target(session: str) -> str:
    """Select the exact session's active window/pane for pane-target commands."""
    return f"={session}:"


def fail(message: str) -> "NoReturn":
    print(f"[hagonoy] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(args: list[str], *, input_text: str | None = None, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            args, input=input_text, text=True, capture_output=True,
            timeout=timeout, check=False,
        )
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


def display_plan(widths: dict[str, float]) -> None:
    print("========== HSMP WORLD-BORDER MAINTENANCE PLAN ==========")
    print("These are full border diameters; no Y coordinate is used (Minecraft uses X/Z).")
    print()
    for dimension, spec in TARGETS.items():
        current = widths[dimension]
        center = ", ".join(spec["center"])
        if spec["change_diameter"]:
            action = f"{current:g} -> {spec['diameter']} blocks"
        else:
            action = f"{current:g} blocks (must remain unchanged; recorded target {spec['diameter']})"
        print(f"{spec['label']}:")
        print(f"  Current width:  {current:g}")
        print(f"  Target width:   {action}")
        if not spec["change_diameter"] and current != spec["diameter"]:
            print("  WARNING: End width differs from the 20,000-block baseline; it will not be changed.")
        print(f"  Center to set:  X {center.split(', ')[0]}, Z {center.split(', ')[1]}")
    print()
    print("Nether center is the Overworld center divided by 8: (-293.625, 4.75).")
    print("End width is deliberately not changed; only its center is set to (0, 0).")
    print("Apply changes only with: ./hagonoy border --apply")


def apply_plan(host: str, target: str, session: str, widths: dict[str, float]) -> None:
    for dimension, spec in TARGETS.items():
        if spec["change_diameter"] and widths[dimension] > spec["diameter"]:
            fail(
                f"{spec['label']} is already wider than the approved target "
                f"({widths[dimension]:g} > {spec['diameter']}). Refusing to shrink it."
            )

    print("[hagonoy] Sending dimension-specific world-border commands...")
    for dimension, spec in TARGETS.items():
        x, z = spec["center"]
        console_send(
            host, target, session,
            f"execute in {dimension} run worldborder center {x} {z}",
        )
        if spec["change_diameter"] and widths[dimension] != spec["diameter"]:
            console_send(
                host, target, session,
                f"execute in {dimension} run worldborder set {spec['diameter']} 0",
            )
        print(f"[hagonoy] {spec['label']}: center command sent.")

    after: dict[str, float] = {}
    for dimension in TARGETS:
        after[dimension] = query_width(host, target, session, dimension)

    for dimension, spec in TARGETS.items():
        expected = spec["diameter"] if spec["change_diameter"] else widths[dimension]
        if after[dimension] != expected:
            fail(
                f"{spec['label']} width verification failed: expected {expected:g}, "
                f"got {after[dimension]:g}. Check the server console before retrying."
            )

    print()
    print("[hagonoy] Width verification passed:")
    for dimension, spec in TARGETS.items():
        print(f"  {spec['label']}: {after[dimension]:g} blocks")
    print("[hagonoy] End diameter was preserved. Center commands were sent for all dimensions.")
    print("[hagonoy] No server restart was requested.")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"--plan", "--apply"}:
        fail("Usage: ./hagonoy border --plan|--apply")

    windows_session, ubuntu_target, ubuntu_session, port = config_values()
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

    widths = {
        dimension: query_width(host, target, session, dimension)
        for dimension in TARGETS
    }
    display_plan(widths)

    if sys.argv[1] == "--plan":
        print("[hagonoy] PLAN ONLY. No world-border settings were changed.")
        return

    print()
    print("This will expand the Overworld to 12,500 and Nether to 3,125.")
    print("The End diameter will remain exactly as queried; its center will be set to 0, 0.")
    print("The server stays online; this changes border settings only.")
    answer = input("Type APPLY HSMP BORDER 12500 3125 KEEP-END to proceed: ").strip()
    if answer != "APPLY HSMP BORDER 12500 3125 KEEP-END":
        print("[hagonoy] Cancelled. No world-border settings were changed.")
        return
    apply_plan(host, target, session, widths)


if __name__ == "__main__":
    main()
