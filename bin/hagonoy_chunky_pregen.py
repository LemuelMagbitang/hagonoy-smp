#!/usr/bin/env python3
"""Synchronize Chunky generation selections with the live Paper world borders."""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".hagonoy-world-border-chunky-state.json"
PLUGINS_RE = re.compile(r"Plugins\s*\(\d+\)\s*:\s*(.*)", re.IGNORECASE)
CENTER_RE = re.compile(
    r"Center changed to\s+(-?(?:\d+(?:\.\d+)?|\.\d+)),"
    r"\s*(-?(?:\d+(?:\.\d+)?|\.\d+))\.",
    re.IGNORECASE,
)
RADIUS_RE = re.compile(r"Radius changed to\s+(-?(?:\d+(?:\.\d+)?|\.\d+))\.", re.IGNORECASE)
WORLD_MISSING_RE = re.compile(r"World .* not found\. Available worlds:", re.IGNORECASE)
STARTED_RE = re.compile(r"Task started in ", re.IGNORECASE)
START_CONFIRM_RE = re.compile(r"A task was already started for this world", re.IGNORECASE)
ALREADY_ACTIVE_RE = re.compile(r"Task already started for ", re.IGNORECASE)
START_LIMIT_RE = re.compile(r"maximum pre-generation radius", re.IGNORECASE)
SHAPE_RE = re.compile(r"Shape changed to square\.", re.IGNORECASE)
LIMIT_RE = re.compile(r"Rate limit for .* set to .* chunks per second\.", re.IGNORECASE)
NO_TASKS_RE = re.compile(r"No tasks to cancel\.", re.IGNORECASE)
CANCEL_PROMPT_RE = re.compile(r"Cancelled tasks cannot be continued", re.IGNORECASE)
CANCELLED_RE = re.compile(r"Task cancelled for ", re.IGNORECASE)
PROGRESS_RE = re.compile(r"Task running for (.+?)\. Processed:", re.IGNORECASE)
NO_PROGRESS_RE = re.compile(r"No tasks running\.", re.IGNORECASE)
TASK_LOG_RE = re.compile(r"^\[[^\]]+\]\s+(\w+)\s+(.*)$")
NUMBER_RE = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def checked_run(args: list[str], *, timeout: int = 15) -> str:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"Command failed: {args[0]} ({exc})")
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"Command failed ({args[0]}): {detail or result.returncode}")
    return result.stdout


class Console:
    def __init__(self, host: str, ssh_target: str, session: str):
        if host not in {"UBUNTU", "WINDOWS"}:
            fail(f"Unsupported canonical host: {host}")
        self.host = host
        self.ssh_target = ssh_target
        self.session = session
        self.pane = f"={session}:"

    def capture(self) -> str:
        if self.host == "WINDOWS":
            return checked_run(["tmux", "capture-pane", "-p", "-t", self.pane, "-S", "-240"])
        return checked_run([
            "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            self.ssh_target, "tmux", "capture-pane", "-p", "-t", self.pane, "-S", "-240",
        ])

    def send(self, command: str) -> None:
        if self.host == "WINDOWS":
            checked_run(["tmux", "send-keys", "-t", self.pane, command, "C-m"])
        else:
            remote = "tmux send-keys -t " + shlex.quote(self.pane) + " " + shlex.quote(command) + " C-m"
            checked_run([
                "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                self.ssh_target, remote,
            ])

    def command(
        self,
        command: str,
        *,
        required: tuple[re.Pattern[str], ...] = (),
        any_of: tuple[re.Pattern[str], ...] = (),
        rejected: tuple[re.Pattern[str], ...] = (),
        timeout: float = 8,
    ) -> str:
        before = self.capture()
        patterns = required + any_of + rejected
        counts = [len(pattern.findall(before)) for pattern in patterns]
        self.send(command)
        deadline = time.monotonic() + timeout
        latest = before
        while time.monotonic() < deadline:
            time.sleep(0.2)
            latest = self.capture()
            current = [len(pattern.findall(latest)) for pattern in patterns]
            required_ok = all(current[i] > counts[i] for i in range(len(required)))
            any_start = len(required)
            any_ok = not any_of or any(
                current[i] > counts[i] for i in range(any_start, any_start + len(any_of))
            )
            rejected_start = len(required) + len(any_of)
            rejected_hit = any(
                current[i] > counts[i] for i in range(rejected_start, len(patterns))
            )
            if rejected_hit:
                tail = "\n".join(latest.splitlines()[-16:])
                fail(f"Chunky rejected '{command}'. Console output:\n{tail}")
            if required_ok and any_ok:
                return latest
        tail = "\n".join(latest.splitlines()[-16:])
        fail(f"Timed out waiting for Chunky to acknowledge '{command}'. Console output:\n{tail}")


def clean_text(value: str) -> str:
    value = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
    value = re.sub(r"§.", "", value)
    return value.replace("\r", "")


def check_plugin(console: Console) -> None:
    output = clean_text(console.command(
        "plugins",
        required=(PLUGINS_RE,),
        timeout=8,
    ))
    matches = PLUGINS_RE.findall(output)
    if not matches:
        fail("Could not read the Paper plugin list; refusing to change world borders.")
    names = [name.strip().lower() for name in matches[-1].split(",") if name.strip()]
    if "chunky" not in names:
        fail("Chunky is not shown as an enabled Paper plugin. No world border was changed.")


def import_border(console: Console, world: str) -> dict[str, float | str]:
    output = clean_text(console.command(
        f"chunky worldborder {world}",
        required=(CENTER_RE, RADIUS_RE),
        rejected=(WORLD_MISSING_RE,),
        timeout=8,
    ))
    centers = CENTER_RE.findall(output)
    radii = RADIUS_RE.findall(output)
    if not centers or not radii:
        fail(f"Chunky did not report the live world-border center and radius for {world}.")
    x, z = float(centers[-1][0]), float(centers[-1][1])
    radius = float(radii[-1])
    if not all(math.isfinite(v) for v in (x, z, radius)) or radius <= 0:
        fail(f"Invalid world-border selection returned by Chunky for {world}: {centers[-1]}, {radii[-1]}")
    return {"world": world, "center_x": x, "center_z": z, "radius_x": radius, "radius_z": radius, "shape": "square"}


def read_server_text(host: str, ssh_target: str, server_dir: str, relative: str, *, tail: int | None = None) -> str:
    path = Path(server_dir) / relative
    if host == "WINDOWS":
        try:
            if not path.is_file():
                return ""
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            fail(f"Could not read {path}: {exc}")
    else:
        qpath = shlex.quote(str(path))
        if tail is None:
            remote = f"if [ -f {qpath} ]; then cat -- {qpath}; fi"
        else:
            remote = f"if [ -f {qpath} ]; then tail -n {int(tail)} -- {qpath}; fi"
        text = checked_run([
            "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            ssh_target, remote,
        ])
    if tail is not None:
        text = "\n".join(text.splitlines()[-tail:])
    return text


def task_paths(world: str) -> tuple[str, str]:
    relative_name = world.replace(":", "/")
    if not re.fullmatch(r"[A-Za-z0-9_.:/-]+", relative_name) or ".." in relative_name.split("/"):
        fail(f"Unsafe Chunky task world identifier: {world!r}")
    return (
        f"plugins/Chunky/tasks/{relative_name}.properties",
        "plugins/Chunky/tasks.log",
    )


def properties(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.lstrip().startswith(("#", "!")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def fingerprint_matches(saved: dict[str, object], desired: dict[str, object]) -> bool:
    for key in ("center_x", "center_z", "radius_x", "radius_z"):
        try:
            if abs(float(saved[key]) - float(desired[key])) > 0.01:
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return str(saved.get("shape", "")).lower() == "square"


def task_fingerprint_from_properties(values: dict[str, str]) -> dict[str, object] | None:
    try:
        radius = float(values["radius"])
        return {
            "center_x": float(values["center-x"]),
            "center_z": float(values["center-z"]),
            "radius_x": radius,
            "radius_z": float(values.get("radius-z", radius)),
            "shape": values.get("shape", "square").lower(),
        }
    except (KeyError, TypeError, ValueError):
        return None


def latest_task_event(task_log: str, world: str) -> tuple[str, dict[str, object]] | None:
    latest = None
    for line in task_log.splitlines():
        match = TASK_LOG_RE.match(line.strip())
        if not match:
            continue
        event, rest = match.groups()
        fields = dict(re.findall(r"([a-z-]+)=([^\s]+)", rest))
        if fields.get("world") != world:
            continue
        fingerprint = task_fingerprint_from_properties(fields)
        if fingerprint is not None:
            latest = (event.lower(), fingerprint)
    return latest


def task_snapshot(
    host: str, ssh_target: str, server_dir: str, world: str
) -> tuple[dict[str, str], tuple[str, dict[str, object]] | None]:
    task_path, log_path = task_paths(world)
    props_text = read_server_text(host, ssh_target, server_dir, task_path)
    log_text = read_server_text(host, ssh_target, server_dir, log_path, tail=2000)
    return properties(props_text), latest_task_event(log_text, world)


def load_pregen_state() -> dict[str, object]:
    if not STATE.is_file():
        return {"schema": 1, "worlds": {}}
    try:
        payload = json.loads(STATE.read_text(encoding="utf-8"))
        if payload.get("schema") != 1 or not isinstance(payload.get("worlds"), dict):
            fail(f"Unsupported Chunky pre-generation state in {STATE}.")
        return payload
    except (OSError, ValueError, TypeError) as exc:
        fail(f"Cannot read Chunky pre-generation state {STATE}: {exc}")


def save_pregen_state(payload: dict[str, object]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".hagonoy-chunky-border-", dir=STATE.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
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


def progress_worlds(console: Console) -> set[str]:
    output = clean_text(console.command(
        "chunky progress",
        any_of=(PROGRESS_RE, NO_PROGRESS_RE),
        timeout=5,
    ))
    return {name.strip() for name in PROGRESS_RE.findall(output)}


def set_square_and_limit(console: Console, rate_limit: int) -> None:
    console.command(
        "chunky shape square",
        required=(SHAPE_RE,),
        timeout=8,
    )
    console.command(
        f"chunky limit {rate_limit}",
        required=(LIMIT_RE,),
        timeout=8,
    )


def cancel_world_task(console: Console, world: str) -> None:
    output = clean_text(console.command(
        f"chunky cancel {world}",
        any_of=(NO_TASKS_RE, CANCEL_PROMPT_RE),
        timeout=8,
    ))
    if CANCEL_PROMPT_RE.search(output):
        output = clean_text(console.command(
            "chunky confirm",
            required=(CANCELLED_RE,),
            timeout=12,
        ))
    # Allow Chunky's worker to finish in-flight chunk futures and remove its task.
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            active = progress_worlds(console)
        except RuntimeError:
            active = set()
        if world not in active:
            return
        time.sleep(1)
    fail(f"Chunky task for {world} did not stop after cancellation; refusing to start a replacement.")


def configured_task_radius_limit(
    host: str, ssh_target: str, server_dir: str
) -> float | None:
    content = read_server_text(host, ssh_target, server_dir, "plugins/Chunky/.chunky.properties")
    for line in content.splitlines():
        if line.strip().startswith("radius-limit="):
            try:
                value = float(line.split("=", 1)[1].strip())
            except ValueError:
                fail("Chunky's .chunky.properties contains an invalid radius-limit value.")
            if not math.isfinite(value) or value < 0:
                fail("Chunky's .chunky.properties contains an invalid radius-limit value.")
            return value
    return None


def preflight(
    console: Console,
    host: str,
    ssh_target: str,
    server_dir: str,
    worlds: dict[str, str],
    expected_diameters: dict[str, float] | None = None,
) -> dict[str, dict[str, object]]:
    check_plugin(console)
    limit = configured_task_radius_limit(host, ssh_target, server_dir)
    selections: dict[str, dict[str, object]] = {}
    seen = set()
    for dimension, world in worlds.items():
        if world in seen:
            fail(f"Chunky world name '{world}' is assigned to more than one dimension.")
        seen.add(world)
        selection = import_border(console, world)
        radius_to_check = (
            float(expected_diameters[dimension]) / 2
            if expected_diameters is not None and dimension in expected_diameters
            else float(selection["radius_x"])
        )
        if limit is not None and radius_to_check > limit:
            fail(
                f"Chunky's configured radius-limit ({limit:g}) is smaller than the "
                f"planned {world} world-border radius ({radius_to_check:g}); "
                "increase the Chunky limit deliberately before applying this border."
            )
        selections[dimension] = selection
    return selections


def sync_world(
    console: Console,
    host: str,
    ssh_target: str,
    server_dir: str,
    world: str,
    desired: dict[str, object],
    rate_limit: int,
    state: dict[str, object],
) -> str:
    # Import this world's own live Bukkit border, never a shared hard-coded radius.
    current = import_border(console, world)
    if not fingerprint_matches(current, desired):
        fail(f"{world}: Chunky's imported border selection did not match the preflight fingerprint.")

    props, event = task_snapshot(host, ssh_target, server_dir, world)
    saved = task_fingerprint_from_properties(props)
    worlds_state = state["worlds"]
    assert isinstance(worlds_state, dict)
    active_worlds = progress_worlds(console)
    is_active = world in active_worlds

    if saved is not None and fingerprint_matches(saved, current):
        is_cancelled = props.get("cancelled", "true").strip().lower() == "true"
        if not is_cancelled:
            if is_active:
                worlds_state[world] = {**current, "status": "running"}
                save_pregen_state(state)
                return "already running"
            # Resume this world's exact saved border selection. No task is duplicated:
            # Chunky's continue command refuses to add a second task for a running world.
            set_square_and_limit(console, rate_limit)
            output = clean_text(console.command(
                f"chunky continue {world}",
                any_of=(re.compile(r"Task continuing for ", re.IGNORECASE),
                        ALREADY_ACTIVE_RE,
                        re.compile(r"No tasks to continue\.", re.IGNORECASE)),
                timeout=10,
            ))
            if re.search(r"No tasks to continue\.", output, re.IGNORECASE):
                fail(f"{world}: Chunky had an incomplete saved task but refused to continue it.")
            worlds_state[world] = {**current, "status": "running"}
            save_pregen_state(state)
            return "resumed"

    # A completed task is reusable only when its logged center and radius still
    # match the current border and there is no conflicting active task.
    if (
        not is_active
        and event is not None
        and event[0] == "completed"
        and fingerprint_matches(event[1], current)
        and (saved is None or props.get("cancelled", "true").strip().lower() == "true")
    ):
        worlds_state[world] = {**current, "status": "completed"}
        save_pregen_state(state)
        return "already complete"

    if is_active or (saved is not None and props.get("cancelled", "true").strip().lower() == "false"):
        cancel_world_task(console, world)

    set_square_and_limit(console, rate_limit)
    output = clean_text(console.command(
        f"chunky start {world} square",
        any_of=(STARTED_RE, START_CONFIRM_RE, ALREADY_ACTIVE_RE),
        rejected=(START_LIMIT_RE,),
        timeout=10,
    ))
    if ALREADY_ACTIVE_RE.search(output):
        worlds_state[world] = {**current, "status": "running"}
        save_pregen_state(state)
        return "already running"
    if START_CONFIRM_RE.search(output):
        output = clean_text(console.command(
            "chunky confirm",
            required=(STARTED_RE,),
            rejected=(START_LIMIT_RE,),
            timeout=10,
        ))
    if not STARTED_RE.search(output):
        fail(f"{world}: Chunky did not confirm that a new generation task started.")
    worlds_state[world] = {**current, "status": "running"}
    save_pregen_state(state)
    return "started"


def run_pregen(
    host: str,
    ssh_target: str,
    session: str,
    server_dir: str,
    worlds: dict[str, str],
    rate_limit: int,
) -> None:
    console = Console(host, ssh_target, session)
    selections = preflight(console, host, ssh_target, server_dir, worlds)
    state = load_pregen_state()
    print("========== CHUNKY BORDER PRE-GENERATION ==========")
    print("Selection shape: square. Centers and radii are imported from each live Bukkit world border.")
    print(f"Per-world rate limit: {rate_limit} chunks/second (0 means unlimited).")
    for dimension, world in worlds.items():
        print(
            f"{dimension} -> {world}: center X {selections[dimension]['center_x']:g}, "
            f"Z {selections[dimension]['center_z']:g}; radius {selections[dimension]['radius_x']:g}"
        )
    for dimension, world in worlds.items():
        outcome = sync_world(
            console, host, ssh_target, server_dir, world,
            selections[dimension], rate_limit, state,
        )
        print(f"[hagonoy] {dimension} ({world}): {outcome}.")
    print("[hagonoy] Chunky tasks were started/resumed per dimension; completion is checked with --chunks-status.")


def show_status(
    host: str,
    ssh_target: str,
    session: str,
    server_dir: str,
    worlds: dict[str, str],
) -> None:
    console = Console(host, ssh_target, session)
    selections = preflight(console, host, ssh_target, server_dir, worlds)
    active_worlds = progress_worlds(console)
    print("========== CHUNKY BORDER PRE-GENERATION STATUS ==========")
    for dimension, world in worlds.items():
        props, event = task_snapshot(host, ssh_target, server_dir, world)
        saved = task_fingerprint_from_properties(props)
        desired = selections[dimension]
        if world in active_worlds and saved is not None and fingerprint_matches(saved, desired):
            status = "RUNNING"
        elif saved is not None and fingerprint_matches(saved, desired):
            cancelled = props.get("cancelled", "true").strip().lower() == "true"
            if not cancelled and event is not None and event[0] == "paused":
                status = "PAUSED (resumable)"
            elif cancelled and event is not None and event[0] == "completed" and fingerprint_matches(event[1], desired):
                status = "COMPLETE"
            elif cancelled and event is not None and event[0] == "cancelled":
                status = "CANCELLED"
            else:
                status = "NOT RUNNING / VERIFY TASK LOG"
        elif event is not None and event[0] == "completed" and fingerprint_matches(event[1], desired):
            status = "COMPLETE (task file unavailable)"
        else:
            status = "NOT STARTED FOR CURRENT BORDER"
        print(
            f"{dimension} ({world}): {status}; center X {desired['center_x']:g}, "
            f"Z {desired['center_z']:g}; radius {desired['radius_x']:g}"
        )
    print("Completion is authoritative only when Chunky's tasks.log records 'completed' for the current center/radius.")


def main() -> int:
    if len(sys.argv) not in {10, 13}:
        print("Internal invocation requires host, SSH target, session, server directory, three world names, rate limit, and optionally three planned diameters.", file=sys.stderr)
        return 2
    mode, host, ssh_target, session, server_dir, ow, nether, end, rate = sys.argv[1:10]
    expected = None
    if len(sys.argv) == 13:
        try:
            expected = {
                "overworld": float(sys.argv[10]),
                "nether": float(sys.argv[11]),
                "end": float(sys.argv[12]),
            }
        except ValueError:
            print("Invalid planned border diameter supplied for Chunky preflight.", file=sys.stderr)
            return 2
    worlds = {"overworld": ow, "nether": nether, "end": end}
    try:
        console = Console(host, ssh_target, session)
        if mode == "--preflight":
            selections = preflight(console, host, ssh_target, server_dir, worlds, expected)
            for dimension, selection in selections.items():
                print(
                    f"{dimension}: world={selection['world']} center=({selection['center_x']}, "
                    f"{selection['center_z']}) current radius={selection['radius_x']}"
                )
            if expected is not None:
                print("Chunky radius-limit preflight also passed for all proposed border diameters.")
        elif mode == "--run":
            if not rate.isdigit() or int(rate) < 0 or int(rate) > 1000:
                fail("Chunky rate limit must be an integer from 0 through 1000.")
            run_pregen(host, ssh_target, session, server_dir, worlds, int(rate))
        elif mode == "--status":
            show_status(host, ssh_target, session, server_dir, worlds)
        else:
            print("Unknown Chunky pre-generation mode.", file=sys.stderr)
            return 2
        return 0
    except RuntimeError as exc:
        print(f"[hagonoy-chunky] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
