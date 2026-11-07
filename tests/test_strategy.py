"""Strategy checks independent of the FastAPI server and transport."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game import Action, AgentConfig, Game, make_deal
from tools.benchmark_strategy import OPPONENTS, paired_summary, run_match


@pytest.mark.parametrize("opponent", OPPONENTS)
def test_strategy_plays_legal_actions_in_both_seats(opponent):
    result = run_match(opponent, deals=20, seed=f"strategy-legality-{opponent}")
    assert result["errors"] == 0
    assert len(result["paired_bb"]) == 20
    assert {half["seat"] for half in result["halves"]} == {0, 1}
    assert all(half["hand_callbacks"] == 20 for half in result["halves"])
    assert all(half["decisions"] > 0 for half in result["halves"])


def test_benchmark_starts_each_half_with_fresh_memory_and_delivers_results():
    """A prior half's learned state must never leak into its duplicate half."""
    memories = []

    def new_half(config, memory):
        assert memory == {}
        memory["completed"] = 0
        memories.append(memory)

    def choose_action(obs, memory):
        # All earlier results must arrive before the next hand's decision.
        assert memory["completed"] == obs.hand_index
        return Action.CHECK_CALL

    def on_hand_end(result, memory):
        assert result.hand_index == memory["completed"]
        memory["completed"] += 1

    probe = SimpleNamespace(new_half=new_half, choose_action=choose_action, on_hand_end=on_hand_end)
    result = run_match("calling", deals=5, seed="callback-order", strategy=probe)
    assert memories[0] is not memories[1]
    assert [memory["completed"] for memory in memories] == [5, 5]
    # Identical always-call policies cancel exactly under duplicate dealing.
    assert result["paired_bb"] == [0.0] * 5
    assert result["verdict"] == "CHOP"


def test_fresh_strategy_state_is_independent_of_prior_play():
    import strategy

    config = AgentConfig(num_hands=10)
    old, fresh = {}, {}
    strategy.new_half(config, old)
    obs = Game(make_deal("memory-isolation", 0), button_seat=0).observation(0)
    assert strategy.choose_action(obs, old) in obs.legal_actions
    old["_test_prior_half_marker"] = object()
    strategy.new_half(config, fresh)
    assert "_test_prior_half_marker" not in fresh
    assert strategy.choose_action(obs, fresh) in obs.legal_actions
    # Mutable per-half structures must not be shared across memory dictionaries.
    for key in old.keys() & fresh.keys():
        if isinstance(fresh[key], (dict, list, set)):
            assert old[key] is not fresh[key], f"shared mutable per-half state: {key}"


def test_paired_scoring_uses_paired_deals_not_individual_hands():
    result = paired_summary([2, 4, 6], [0, 2, 4])
    assert result["paired_bb"] == [1.0, 3.0, 5.0]
    assert result["mean_bb_per_paired_deal"] == 3.0
    assert result["std_bb"] == 2.0
    assert result["ci95_bb"][0] == pytest.approx(3 - 1.96 * 2 / 3**0.5)


def test_benchmark_rejects_illegal_action_immediately():
    probe = SimpleNamespace(
        new_half=lambda config, memory: None,
        choose_action=lambda obs, memory: "RAISE_POT",
        on_hand_end=lambda result, memory: None,
    )
    with pytest.raises(AssertionError, match="Illegal strategy action"):
        run_match("calling", deals=1, seed="invalid-action", strategy=probe)
