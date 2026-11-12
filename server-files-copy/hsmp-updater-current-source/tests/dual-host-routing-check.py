import importlib.machinery
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "hsmp_host_routing", str(ROOT / "bin" / "hagonoy-generation")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)


def probe(host, state, generation, generation_id, ancestors):
    return {
        "host": host,
        "state": state,
        "generation": generation,
        "generation_id": generation_id,
        "ancestors": ancestors,
        "parent_generation_id": ancestors[-1] if ancestors else None,
    }


print("========== ACTIVE HOST: UBUNTU ==========")
ubuntu = probe("ubuntu", "running", 3, "u3", ["u1", "u2"])
windows = probe("windows", "stopped", 2, "u2", ["u1"])
result = module.select_active_host_probes(ubuntu, windows)
assert result["active_host"] == "ubuntu"
assert result["peer_host"] == "windows"
print("[OK] Ubuntu is selected only when it is RUNNING and proves descent from the stopped Windows generation.")

print("========== ACTIVE HOST: WINDOWS ==========")
ubuntu = probe("ubuntu", "stopped", 4, "w4", ["w1", "w2", "w3"])
windows = probe("windows", "running", 5, "w5", ["w1", "w2", "w3", "w4"])
result = module.select_active_host_probes(ubuntu, windows)
assert result["active_host"] == "windows"
print("[OK] Windows is selected when it is RUNNING and proves descent from the stopped Ubuntu generation.")

print("========== SHARED GENERATION ==========")
ubuntu = probe("ubuntu", "running", 2, "same-2", ["same-1"])
windows = probe("windows", "stopped", 2, "same-2", ["same-1"])
assert module.select_active_host_probes(ubuntu, windows)["active_host"] == "ubuntu"
print("[OK] Equal generation is accepted only when ID and ancestry are identical.")

print("========== FAIL-CLOSED AMBIGUOUS STATES ==========")
invalid_pairs = [
    (probe("ubuntu", "running", 1, "u1", []), probe("windows", "running", 1, "u1", []), "both RUNNING"),
    (probe("ubuntu", "stopped", 1, "u1", []), probe("windows", "stopped", 1, "u1", []), "both STOPPED"),
    (probe("ubuntu", "unknown", 1, "u1", []), probe("windows", "stopped", 1, "u1", []), "unknown"),
    (probe("ubuntu", "running", 2, "u2", ["u1"]), probe("windows", "stopped", 3, "w3", ["w1", "w2"]), "stopped peer newer"),
    (probe("ubuntu", "running", 2, "u2", ["u1"]), probe("windows", "stopped", 2, "w2", ["w1"]), "equal generation conflict"),
    (probe("ubuntu", "running", 3, "u3", ["u1", "u2"]), probe("windows", "stopped", 2, "w2", ["w1"]), "inconsistent ancestry"),
]
for left, right, label in invalid_pairs:
    try:
        module.select_active_host_probes(left, right)
    except RuntimeError:
        pass
    else:
        raise AssertionError(f"Unsafe host selection was accepted: {label}")
    print(f"[OK] Rejects {label}.")

try:
    module.select_active_host_probes(
        probe("wrong-host", "stopped", 1, "w1", []),
        probe("windows", "running", 1, "w1", []),
    )
except RuntimeError as exc:
    assert "mismatched" in str(exc)
else:
    raise AssertionError("Mismatched host identity was accepted.")
print("[OK] Rejects mismatched manifest host identity.")

print("[DONE] Dual-host routing and generation-lineage tests passed.")
