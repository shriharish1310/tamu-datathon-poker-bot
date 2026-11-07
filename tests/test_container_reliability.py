"""Release gates and cleanup boundaries; these tests never invoke Docker."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import check_container_reliability as checker


def clean_probe() -> dict:
    return {"http_status": 200, "diagnostics": {
        "fault_events": 0, "fallback_decisions": 0, "disabled": False,
        "last_fault_stage": None, "last_fault_type": None,
    }}


@pytest.mark.parametrize("key,value", [
    ("fault_events", 1), ("fallback_decisions", 1), ("disabled", True),
    ("fault_events", False), ("fallback_decisions", "0"), ("disabled", 0),
    ("last_fault_stage", "choose_action"),
])
def test_diagnostics_reject_faults_and_malformed_zero_values(key, value):
    probe = clean_probe()
    probe["diagnostics"][key] = value
    assert checker.diagnostics_failures(probe)


def test_missing_diagnostics_fail_closed():
    assert checker.diagnostics_failures({"http_status": 200})
    for key in clean_probe()["diagnostics"]:
        probe = clean_probe()
        del probe["diagnostics"][key]
        assert checker.diagnostics_failures(probe), key
    assert checker.diagnostics_failures(clean_probe()) == []


def test_cleanup_refuses_a_container_with_another_invocations_label(monkeypatch):
    commands = []

    def docker(args, timeout=30):
        commands.append(args)
        return {"returncode": 0, "stdout": json.dumps({checker.OWNER_LABEL: "someone-else"}), "stderr": ""}

    monkeypatch.setattr(checker, "_docker", docker)
    result = checker.cleanup_owned("unique-name", "our-nonce", True)
    assert result["passed"] is False
    assert all("rm" not in command for command in commands)


def test_cleanup_removes_only_its_exact_labelled_container(monkeypatch):
    commands = []

    def docker(args, timeout=30):
        commands.append(args)
        output = json.dumps({checker.OWNER_LABEL: "our-nonce"}) if "inspect" in args else "unique-name"
        return {"returncode": 0, "stdout": output, "stderr": ""}

    monkeypatch.setattr(checker, "_docker", docker)
    result = checker.cleanup_owned("unique-name", "our-nonce", True)
    assert result["passed"] and result["removed"]
    assert commands[-1] == ["container", "rm", "--force", "unique-name"]


def test_restricted_run_never_publishes_network_ports_or_pulls_an_image(tmp_path):
    args = checker.build_run_arguments("sha256:fixture", "unique-name", "nonce", tmp_path / "smoke_test.py")
    for option, value in (("--network", "none"), ("--pull", "never"), ("--cpus", "1"),
                          ("--memory", "4g"), ("--pids-limit", "256"),
                          ("--cap-drop", "ALL"), ("--security-opt", "no-new-privileges")):
        assert args[args.index(option) + 1] == value
    assert "--read-only" in args
    assert "--publish" not in args and "-p" not in args
    assert args[args.index("--tmpfs") + 1] == "/tmp:rw,nosuid,nodev,size=512m"
    assert args[args.index("--volume") + 1].endswith(":/smoke/smoke_test.py:ro")


def test_log_fault_rejects_even_a_successful_smoke_and_clean_counters(monkeypatch):
    cleaned = []

    def docker(args, timeout=30):
        result = {"returncode": 0, "stdout": "", "stderr": ""}
        if args[:2] == ["image", "inspect"]:
            result["stdout"] = "sha256:" + "a" * 64
        elif args[0] == "run":
            result["stdout"] = "b" * 64
        elif args[0] == "exec" and "-c" in args:
            result["stdout"] = json.dumps(clean_probe())
        elif args[0] == "exec":
            result["stdout"] = "SMOKE TEST PASSED"
        elif args[0] == "logs":
            result["stderr"] = "ERROR BOT_STRATEGY_FAULT injected\n"
        return result

    monkeypatch.setattr(checker, "_docker", docker)
    monkeypatch.setattr(checker, "cleanup_owned", lambda *args: cleaned.append(args) or {"passed": True})
    report = checker.run_check("fixture")
    assert report["official_smoke"]["returncode"] == 0
    assert report["fault_log_markers"] == 1
    assert report["passed"] is False
    assert cleaned
