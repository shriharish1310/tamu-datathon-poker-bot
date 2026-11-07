"""A legal fallback must not masquerade as a clean release evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evaluate_suite import read_reliability, summarize, write_report
from tools.run_local_match import scan_fault_log, validate_diagnostics


def clean_diagnostics():
    return {"fault_events": 0, "fallback_decisions": 0, "disabled": False,
            "last_fault_stage": None, "last_fault_type": None}


def sidecar_fixture(tmp_path):
    path = tmp_path / "random_seed7.json"
    evidence = {"schema": "bot-reliability-v1", "status": "complete", "match_seed": "7",
                "num_deals": 1000, "halves": [
                    {"half": half, "diagnostics": clean_diagnostics(), "log_fault_events": 0}
                    for half in (1, 2)
                ]}
    return path, evidence


def save_evidence(path, evidence):
    path.with_suffix(".reliability.json").write_text(json.dumps(evidence), encoding="utf-8")


@pytest.mark.parametrize("mutation", ["missing", "negative", "boolean_counter", "bad_latch", "missing_stage"])
def test_diagnostics_fail_closed_on_malformed_data(mutation):
    value = clean_diagnostics()
    if mutation == "missing":
        value = None
    elif mutation == "negative":
        value["fault_events"] = -1
    elif mutation == "boolean_counter":
        value["fallback_decisions"] = False
    elif mutation == "bad_latch":
        value["disabled"] = 0
    else:
        value.pop("last_fault_stage")
    with pytest.raises(ValueError):
        validate_diagnostics(value)


@pytest.mark.parametrize("kind", ["fault", "fallback", "latch", "log_marker"])
def test_each_fault_signal_independently_invalidates_clean_judge_results(tmp_path, kind):
    path, evidence = sidecar_fixture(tmp_path)
    second = evidence["halves"][1]
    if kind == "fault":
        second["diagnostics"]["fault_events"] = 1
    elif kind == "fallback":
        second["diagnostics"]["fallback_decisions"] = 100
    elif kind == "latch":
        second["diagnostics"]["disabled"] = True
    else:
        second["log_fault_events"] = 1  # Counter says zero; stderr still catches it.
    save_evidence(path, evidence)
    result = read_reliability(path, "7", 1000)
    assert not result["reliability_clean"]


@pytest.mark.parametrize("mutation", ["failed", "seed", "deals", "short", "duplicate_half", "missing_log"])
def test_stale_or_incomplete_reliability_evidence_is_rejected(tmp_path, mutation):
    path, evidence = sidecar_fixture(tmp_path)
    if mutation == "failed":
        evidence["status"] = "failed"
    elif mutation == "seed":
        evidence["match_seed"] = "19"
    elif mutation == "deals":
        evidence["num_deals"] = 10
    elif mutation == "short":
        evidence["halves"].pop()
    elif mutation == "duplicate_half":
        evidence["halves"][1]["half"] = 1
    else:
        evidence["halves"][1]["log_fault_events"] = None
    save_evidence(path, evidence)
    with pytest.raises(ValueError):
        read_reliability(path, "7", 1000)


def test_missing_sidecar_is_not_treated_as_success(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_reliability(tmp_path / "missing.json", "7", 1000)


def test_log_scan_counts_faults_independently_and_rejects_missing_startup(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text("INFO: Application startup complete.\nERROR: BOT_STRATEGY_FAULT\nTraceback...\n", encoding="utf-8")
    assert scan_fault_log(log) == 1
    log.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="startup evidence"):
        scan_fault_log(log)


def test_fallbacks_fail_release_gate_even_when_official_score_is_a_win(tmp_path):
    row = {"opponent": "random", "num_deals": 1000, "points": 1.0,
           "mean_bb_per_deal": 1.0, "ci": [0.5, 1.5], "max_time_seconds": 1.0,
           "bot_valid": True, "opponent_valid": True, "runtime_target_met": True,
           "reliability_clean": False, "fault_events": 1, "fallback_decisions": 10,
           "log_fault_events": 1}
    result = summarize([row], 4.0)
    assert result["total_points"] == 1.0  # Never modify official points.
    assert not result["release_gates_passed"]
    assert result["fallback_decisions"] == 10
    payload = {"status": "complete", "expected_matches": 1, "summary": result, "matches": [row]}
    write_report(tmp_path, payload)
    saved = json.loads((tmp_path / "summary.json").read_text())
    assert not saved["summary"]["release_gates_passed"]


def test_partial_suite_cannot_claim_release_success(tmp_path):
    summary = summarize([], 4.0)
    payload = {"status": "running", "expected_matches": 20, "summary": summary, "matches": []}
    write_report(tmp_path, payload)
    assert not json.loads((tmp_path / "summary.json").read_text())["summary"]["release_gates_passed"]


@pytest.mark.parametrize("clean,exit_code", [(False, 1), (True, 0)])
def test_cli_returns_nonzero_on_gate_failure_after_saving_reports(tmp_path, monkeypatch, clean, exit_code):
    import tools.evaluate_suite as suite

    output = tmp_path / "suite"
    row = {"opponent": "random", "num_deals": 1000, "points": 1.0,
           "verdict": "AGENT1_WIN", "mean_bb_per_deal": 1.0, "ci": [0.5, 1.5],
           "max_time_seconds": 1.0, "bot_valid": True, "opponent_valid": True,
           "runtime_target_met": True, "reliability_clean": clean,
           "fault_events": 0 if clean else 1, "fallback_decisions": 0 if clean else 10,
           "log_fault_events": 0 if clean else 1}
    monkeypatch.setattr(sys, "argv", ["evaluate_suite.py", "--opponents", "random",
                                      "--seeds", "7", "--output", str(output)])
    monkeypatch.setattr(suite, "SOURCE_FILES", ())
    monkeypatch.setattr(suite, "fingerprints", lambda: {})
    monkeypatch.setattr(suite, "version", lambda name: "test")
    monkeypatch.setattr(suite.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(suite.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(suite, "read_official", lambda *args: row)
    assert suite.main() == exit_code
    saved = json.loads((output / "summary.json").read_text())
    assert saved["status"] == "complete"
    assert saved["summary"]["release_gates_passed"] is clean
    assert saved["matches"][0]["points"] == 1.0
