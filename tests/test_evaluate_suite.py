"""Acceptance checks for the adapter over saved official judge results."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from judge_engine import AgentStats, HalfResult, combine_halves
from tools.evaluate_suite import read_official, summarize


def save_official(tmp_path, *, own_times=(1.0, 1.0), own_errors=0,
                  opponent_errors=0, opponent_forfeit=False, own_timeout=False):
    """Create fixtures with the real judge serializer and scoring function."""
    path = tmp_path / "matches" / "random_seed7.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    halves = []
    for half in (1, 2):
        part = HalfResult(
            half=half, match_seed="7", num_deals=3, agent1_seat=half - 1,
            nets_agent1=[2, 2, 2], nets_agent2=[-2, -2, -2],
            stats_agent1=AgentStats(time_seconds=own_times[half - 1],
                                   errors=own_errors, timed_out=own_timeout),
            stats_agent2=AgentStats(errors=opponent_errors, forfeited=opponent_forfeit),
            logs=[{"hand_index": i} for i in range(3)],
        )
        path.with_suffix(f".half{half}.json").write_text(part.to_json(), encoding="utf-8")
        halves.append(part)
    report = combine_halves(*halves).to_dict()
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, report


def test_reader_preserves_official_verdict_and_metrics(tmp_path):
    path, official = save_official(tmp_path)
    row = read_official(path, "7", 3, "random", 4.0)
    assert row["verdict"] == official["verdict"]
    assert row["points"] == official["points"]["agent1"]
    assert row["mean_bb_per_deal"] == official["mean_bb_per_deal"]
    assert row["ci"] == official["ci"]
    assert row["agent_stats"] == official["agent_stats"]
    assert row["report"] == "matches/random_seed7.json"


@pytest.mark.parametrize("fault", ["wrong_seed", "truncated_match", "wrong_seat", "short_half", "short_logs"])
def test_reader_rejects_incomplete_or_mismatched_reports(tmp_path, fault):
    path, report = save_official(tmp_path)
    if fault == "wrong_seed":
        report["match_seed"] = "19"
    elif fault == "truncated_match":
        report["paired_bb"].pop()
    elif fault == "short_logs":
        report["logs"]["half2"].pop()
    else:
        half_path = path.with_suffix(".half2.json")
        part = json.loads(half_path.read_text(encoding="utf-8"))
        if fault == "wrong_seat":
            part["agent1_seat"] = 0
        else:
            part["nets_agent1"].pop()
        half_path.write_text(json.dumps(part), encoding="utf-8")
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        read_official(path, "7", 3, "random", 4.0)


def test_runtime_target_is_strict_for_each_half(tmp_path):
    path, _ = save_official(tmp_path, own_times=(0.1, 4.0))
    row = read_official(path, "7", 3, "random", 4.0)
    assert row["bot_valid"]  # A missed 4s target is not itself an official violation.
    assert row["max_time_seconds"] == 4.0
    assert not row["runtime_target_met"]


@pytest.mark.parametrize("kwargs,key", [
    ({"own_errors": 1}, "bot_valid"),
    ({"own_timeout": True}, "bot_valid"),
    ({"opponent_errors": 1}, "opponent_valid"),
    ({"opponent_forfeit": True}, "opponent_valid"),
])
def test_faults_in_either_bot_invalidate_evidence(tmp_path, kwargs, key):
    path, _ = save_official(tmp_path, **kwargs)
    row = read_official(path, "7", 3, "random", 4.0)
    assert not row[key]
    result = summarize([row], 4.0)
    assert not result["bot_valid" if key == "bot_valid" else "opponents_valid"]


def test_summary_keeps_opponent_downside_and_does_not_pool_ci(tmp_path):
    path, _ = save_official(tmp_path)
    good = read_official(path, "7", 3, "random", 4.0)
    # Summary input is deliberately heterogeneous to expose a hidden weakness.
    bad = {**good, "opponent": "pot", "seed": "19", "points": 0.0,
           "verdict": "AGENT2_WIN", "mean_bb_per_deal": -0.5,
           "ci": [-0.9, -0.1], "max_time_seconds": 4.1,
           "runtime_target_met": False}
    result = summarize([good, bad], 4.0)
    assert result["matches_completed"] == 2
    assert result["total_points"] == good["points"]
    assert not result["positive_average_each_opponent"]
    assert not result["runtime_target_met"]
    by_opponent = {row["opponent"]: row for row in result["per_opponent"]}
    assert by_opponent["pot"]["worst_match_bb_per_deal"] == -0.5
    assert by_opponent["pot"]["min_official_ci_lower"] == -0.9
    assert "ci" not in result
    assert good["ci"] == [2.0, 2.0]  # Adapter must not alter original match intervals.
