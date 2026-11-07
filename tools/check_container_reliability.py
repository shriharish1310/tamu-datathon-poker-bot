"""Check hidden strategy faults in the already-built official Docker image.

Run ONLY after ``bash tools/check_build.sh`` succeeds. This supplementary check
does not replace or modify the official build/smoke test. It repeats the official
smoke under the same restrictions, then inspects counters and stderr before
removing its uniquely named container. It never builds or pulls an image.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
FAULT_MARKER = "BOT_STRATEGY_FAULT"
OWNER_LABEL = "tamu-poker.reliability-check"
RESTRICTIONS = {
    "network": "none", "read_only": True, "tmpfs_mb": 512,
    "cap_drop": "ALL", "no_new_privileges": True,
    "pids_limit": 256, "cpus": 1, "memory": "4g", "port": 5008,
    "smoke_script_read_only": True,
}

# This probe executes inside the isolated container; no host port is published.
DIAGNOSTICS_PROBE = """
import http.client, json, os
connection = http.client.HTTPConnection('127.0.0.1', 5008, timeout=2)
try:
    connection.request('GET', '/', headers={'X-Agent-Token': os.environ.get('AGENT_TOKEN', '')})
    response = connection.getresponse()
    body = json.loads(response.read())
    print(json.dumps({'http_status': response.status,
                      'diagnostics': body.get('diagnostics') if isinstance(body, dict) else None}))
finally:
    connection.close()
"""


def _safe_text(value: str | bytes | None) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
    # Docker mount errors may include the host workspace; it is not report data.
    for prefix in (str(ROOT), ROOT.as_posix()):
        text = text.replace(prefix, "<project>")
    return text


def _docker(arguments: list[str], timeout: float = 30) -> dict:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            ["docker", *arguments], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            check=False, creationflags=flags,
        )
        return {"returncode": result.returncode,
                "stdout": _safe_text(result.stdout), "stderr": _safe_text(result.stderr)}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": None, "stdout": _safe_text(exc.stdout),
                "stderr": _safe_text(exc.stderr), "error": "Docker command timed out"}
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": "",
                "error": _safe_text(f"{type(exc).__name__}: {exc}")}


def build_run_arguments(image: str, container_name: str, nonce: str, smoke_script: Path) -> list[str]:
    """Use the organizer's restrictions, adding an ownership label and no pull."""
    return [
        "run", "--detach", "--pull", "never", "--name", container_name,
        "--label", f"{OWNER_LABEL}={nonce}",
        "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "256", "--cpus", "1", "--memory", "4g",
        "--env", "PORT=5008", "--env", "AGENT_TOKEN=local-check",
        "--volume", f"{smoke_script.resolve().as_posix()}:/smoke/smoke_test.py:ro",
        image,
    ]


def diagnostics_failures(probe: dict) -> list[str]:
    """Fail closed on absent or malformed counters, including bool-as-int values."""
    failures = []
    if probe.get("http_status") != 200:
        failures.append("Post-smoke health request did not return HTTP 200")
    state = probe.get("diagnostics")
    if not isinstance(state, dict):
        return failures + ["Reliability diagnostics are missing"]
    for key in ("fault_events", "fallback_decisions"):
        if type(state.get(key)) is not int or state[key] != 0:
            failures.append(f"Reliability diagnostic {key} must be integer zero")
    if state.get("disabled") is not False:
        failures.append("Reliability diagnostic disabled must be false")
    for key in ("last_fault_stage", "last_fault_type"):
        if key not in state or state[key] is not None:
            failures.append(f"Reliability diagnostic {key} must be present and null")
    return failures


def cleanup_owned(container_name: str, nonce: str, created: bool) -> dict:
    """Never remove a container unless its exact per-invocation label matches."""
    inspected = _docker([
        "container", "inspect", "--format", "{{json .Config.Labels}}", container_name,
    ], timeout=15)
    if inspected["returncode"] != 0:
        absent = (not created and inspected["returncode"] is not None
                  and ("No such container" in inspected["stderr"]
                       or "No such object" in inspected["stderr"]))
        return {"passed": absent, "removed": False, "inspection": inspected,
                "reason": "Container was not created" if absent else "Could not verify container ownership"}
    try:
        labels = json.loads(inspected["stdout"])
    except (ValueError, TypeError):
        labels = None
    if not isinstance(labels, dict) or labels.get(OWNER_LABEL) != nonce:
        return {"passed": False, "removed": False,
                "reason": "Ownership label did not match; no container was removed"}
    removed = _docker(["container", "rm", "--force", container_name], timeout=20)
    return {"passed": removed["returncode"] == 0,
            "removed": removed["returncode"] == 0, "result": removed}


def run_check(image: str) -> dict:
    nonce = uuid.uuid4().hex
    container_name = f"poker-reliability-{nonce}"
    smoke_script = ROOT / "tools" / "smoke_test.py"
    report = {
        "schema": "container-reliability-check-v1",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "prerequisite": "Run after the official tools/check_build.sh succeeds",
        "image": image, "container": container_name,
        "restrictions": dict(RESTRICTIONS), "failures": [],
        "passed": False, "fault_log_markers": None,
    }
    failures = report["failures"]
    if not smoke_script.is_file():
        failures.append("Official tools/smoke_test.py is missing")
        return report
    report["smoke_script_sha256"] = hashlib.sha256(smoke_script.read_bytes()).hexdigest()
    image_check = _docker(["image", "inspect", "--format", "{{.Id}}", image], timeout=15)
    report["image_inspection"] = image_check
    if image_check["returncode"] != 0:
        failures.append("Already-built image is unavailable; run the official build check first")
        return report
    image_id = image_check["stdout"].strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        failures.append("Image inspection did not return a valid immutable image ID")
        return report
    report["image_id"] = image_id
    created = False
    try:
        # Run the inspected ID, so another process cannot swap a mutable tag.
        launch = _docker(build_run_arguments(image_id, container_name, nonce, smoke_script), timeout=60)
        report["launch"] = launch
        created = launch["returncode"] == 0
        if not created:
            failures.append("Could not start the restricted container")
            return report
        smoke = _docker([
            "exec", container_name, "python", "/smoke/smoke_test.py", "--port", "5008", "--startup", "15",
        ], timeout=60)
        report["official_smoke"] = smoke
        if smoke["returncode"] != 0 or "SMOKE TEST PASSED" not in smoke["stdout"]:
            failures.append("Official smoke checks failed or success output is missing")
        probe_result = _docker(["exec", container_name, "python", "-c", DIAGNOSTICS_PROBE], timeout=15)
        report["diagnostics_probe"] = probe_result
        if probe_result["returncode"] != 0:
            failures.append("Could not collect post-smoke reliability diagnostics")
        else:
            try:
                probe = json.loads(probe_result["stdout"])
            except (ValueError, TypeError):
                probe = None
            if not isinstance(probe, dict):
                failures.append("Reliability probe returned malformed JSON")
            else:
                report["diagnostics"] = probe.get("diagnostics")
                report["diagnostics_http_status"] = probe.get("http_status")
                failures.extend(diagnostics_failures(probe))
        logs = _docker(["logs", container_name], timeout=15)
        report["container_logs"] = logs
        if logs["returncode"] != 0:
            failures.append("Could not collect container logs before cleanup")
        else:
            count = (logs["stdout"] + "\n" + logs["stderr"]).count(FAULT_MARKER)
            report["fault_log_markers"] = count
            if count:
                failures.append(f"Container logs contain {count} {FAULT_MARKER} marker(s)")
    except Exception as exc:
        failures.append(_safe_text(f"Reliability check could not complete: {type(exc).__name__}: {exc}"))
    finally:
        report["cleanup"] = cleanup_owned(container_name, nonce, created)
        if not report["cleanup"]["passed"]:
            failures.append("Owned test-container cleanup could not be verified")
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["passed"] = not failures
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="poker-agent-check:latest")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "container-reliability.json")
    args = parser.parse_args()
    report = run_check(args.image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CONTAINER RELIABILITY {'PASSED' if report['passed'] else 'FAILED'}")
    print(f"fault_log_markers={report['fault_log_markers']} diagnostics={report.get('diagnostics')}")
    for failure in report["failures"]:
        print(f"  {failure}")
    print(f"Report: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
