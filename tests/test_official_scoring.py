"""The development harness must use the organizer's scoring implementation."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import judge_engine
from tools.benchmark_strategy import paired_summary


def test_summary_delegates_to_official_combiner_and_json_fields(monkeypatch):
    seen = []
    # Deliberately distinctive values prove the wrapper does not recompute them.
    payload = {
        "mean_bb_per_deal": 12.25,
        "std_bb": 7.5,
        "stderr_bb": 2.25,
        "ci": [-0.125, 9.875],
        "verdict": judge_engine.CHOP,
        "points": {"agent1": 0.5, "agent2": 0.5},
        "paired_bb": [3.0, -2.5],
    }

    def official_combiner(first, second):
        seen.extend((first, second))
        return SimpleNamespace(to_dict=lambda: payload)

    monkeypatch.setattr(judge_engine, "combine_halves", official_combiner)
    first_nets, second_nets = [2, -4], [4, -1]
    result = paired_summary(first_nets, second_nets)
    assert result == {
        "mean_bb_per_paired_deal": payload["mean_bb_per_deal"],
        "std_bb": payload["std_bb"],
        "stderr_bb": payload["stderr_bb"],
        "ci95_bb": payload["ci"],
        "verdict": "CHOP",
        "official_verdict": judge_engine.CHOP,
        "points": payload["points"]["agent1"],
        "paired_bb": payload["paired_bb"],
    }
    assert all(isinstance(half, judge_engine.HalfResult) for half in seen)
    assert [half.half for half in seen] == [1, 2]
    assert [half.agent1_seat for half in seen] == [0, 1]
    assert seen[0].match_seed == seen[1].match_seed
    assert [half.num_deals for half in seen] == [2, 2]
    assert seen[0].nets_agent1 == first_nets
    assert seen[1].nets_agent1 == second_nets
    assert seen[0].nets_agent2 == [-2, 4]
    assert seen[1].nets_agent2 == [-4, 1]
    assert seen[0].nets_agent1 is not first_nets
    assert seen[0].stats_agent1 is not seen[1].stats_agent1


@pytest.mark.parametrize(
    ("net", "verdict", "points"),
    [(2, judge_engine.AGENT1_WIN, 1.0),
     (-2, judge_engine.AGENT2_WIN, 0.0),
     (0, judge_engine.CHOP, 0.5)],
)
def test_actual_official_outcomes_are_preserved(net, verdict, points):
    result = paired_summary([net] * 4, [net] * 4)
    assert result["official_verdict"] == verdict
    assert result["points"] == points


def test_touching_zero_uses_official_chop_rule_and_current_constant(monkeypatch):
    # This produces an exact lower endpoint of zero when the official Z is one.
    # The wrapper must honor the judge's current configuration without its own Z.
    monkeypatch.setattr(judge_engine, "CHOP_Z", 1.0)
    result = paired_summary([0, 4], [0, 0])
    assert result["ci95_bb"] == [0.0, 2.0]
    assert result["official_verdict"] == judge_engine.CHOP
    assert result["points"] == 0.5


@pytest.mark.parametrize(("first", "second"), [([], []), ([2], []), ([2], [2, 4])])
def test_incomplete_or_empty_paired_results_are_rejected(first, second):
    with pytest.raises(ValueError, match="same positive number"):
        paired_summary(first, second)
