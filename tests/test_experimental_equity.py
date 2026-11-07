"""Statistical/reference checks for range conditioning and incremental sampling."""
from dataclasses import replace
import json
from pathlib import Path
import runpy
import sys
from random import Random

import pytest

import baseline_strategy
from advanced_policy import Policy, position_margin, range_parameters
from equity import estimate_equity
from game import Action, AgentConfig, Game, Street, make_deal
from policy_config import BASE, PROFILES
from range_equity import Rollouts, midrank_percentiles, summarize_weighted, visible_strength


@pytest.mark.parametrize("count", [0, 3, 4, 5])
def test_uniform_incremental_rollouts_equal_original_official_reference(count):
    cards = Random(135).sample(range(36), 10)
    batch = Rollouts(cards[:5], cards[5:5+count], 47)
    batch.extend(24)
    batch.extend(64)
    actual = batch.estimates()[0]
    reference = estimate_equity(cards[:5], cards[5:5+count], samples=64, seed=47)
    assert actual.equity == reference.equity
    assert actual.stderr == pytest.approx(reference.stderr)
    assert actual.effective_samples == 64
    single = Rollouts(cards[:5], cards[5:5+count], 47)
    single.extend(64)
    assert batch.payoffs == single.payoffs
    assert batch.strengths == single.strengths


def test_importance_weighting_and_effective_sample_size():
    estimate = summarize_weighted([0, 0.5, 1], [9, 1, 1])
    assert estimate.equity == pytest.approx(1.5 / 11)
    assert estimate.effective_samples == pytest.approx(121 / 83)
    assert estimate.stderr > 0
    assert midrank_percentiles([2, 2, 8, 0]) == [0.5, 0.5, 0.875, 0.125]


def test_visible_range_features_never_use_unseen_runout():
    hole, board = (0, 5, 10, 15, 20), (21, 26, 31)
    villain = [2, 6, 11, 16, 24]
    batches = [Rollouts(hole, board, 0) for _ in range(2)]
    for batch, runout in zip(batches, ([27, 32], [28, 33])):
        class Fixed:
            def sample(self, population, k):
                draw = [1 << card for card in villain + runout]
                assert len(draw) == k and set(draw).issubset(population)
                return draw
        batch.rng = Fixed()
        batch.extend(1)
        batch.estimates(range_mix=0.5)
    assert batches[0].strengths == batches[1].strengths
    assert batches[0].strengths == [visible_strength(villain, board)]


def test_lazy_features_preserve_preoptimization_weighted_results():
    cases = json.loads((Path(__file__).parent / "fixtures/range_equity_reference.json").read_text())
    reference_type = runpy.run_path(str(Path(__file__).parent / "fixtures/range_equity_eager.py"))["Rollouts"]
    for case in cases:
        # Python 3.12 changed float summation; tiny preflop feature differences
        # can change percentile ties. Compare against the frozen eager algorithm
        # on the SAME interpreter, not hardcoded Python 3.10 floating-point ranks.
        eager = reference_type(case["hole"], case["board"], case["seed"])
        eager.extend(case["samples"])
        expected = eager.estimates(**case["parameters"])
        batch = Rollouts(case["hole"], case["board"], case["seed"])
        batch.extend(24)
        batch.estimates()  # Uniform queries must not compute unused range features.
        assert batch.strengths == []
        batch.estimates(**case["parameters"])  # Also invalidate cached weighted ranks on extension.
        batch.extend(case["samples"])
        actual = batch.estimates(**case["parameters"])
        for estimate, reference, saved in zip(actual, expected, case["expected"]):
            assert estimate.equity == pytest.approx(reference.equity, abs=1e-12)
            assert estimate.stderr == pytest.approx(reference.stderr, abs=1e-12)
            assert estimate.effective_samples == pytest.approx(reference.effective_samples, abs=1e-12)
            if sys.version_info[:2] == (3, 10):
                assert estimate.equity == pytest.approx(saved["equity"], abs=1e-12)
        assert batch.estimates(**case["parameters"]) == actual


def test_conditioning_river_callers_lowers_equity_against_stronger_hands():
    batch = Rollouts((0, 5, 10, 15, 20), (21, 26, 31, 7, 12), 901)
    batch.extend(256)
    current, half, pot = batch.estimates(caller_power=1.0, fold_rate=0.65)
    assert pot.equity <= half.equity <= current.equity
    assert 0 < pot.effective_samples <= current.effective_samples


def test_range_conditions_on_real_raises_and_flattens_for_habitual_aggression():
    game = Game(make_deal("range-tests", 0), 0)
    obs = game.observation(0)
    assert range_parameters(obs, 0.1, 1.0)[0] == 0  # Blind is not a raise.
    game.apply(Action.RAISE_POT)
    obs = game.observation(1)
    assert range_parameters(obs, 0.1, 1.0)[0] > range_parameters(obs, 0.5, 1.0)[0]
    assert range_parameters(obs, 0.9, 1.0)[0] == 0


def test_position_ablation_distinguishes_street_order_from_future_position():
    obs = Game(make_deal("position", 0), 0).observation(0)
    assert position_margin(obs, "street_order") == 0.015
    assert position_margin(obs, "legacy") == 0
    bb = replace(obs, is_button=False)
    assert position_margin(bb, "legacy") == 0.015
    assert position_margin(bb, "street_order") == 0
    assert position_margin(bb, "no_preflop") == 0
    assert position_margin(replace(bb, street=Street.FLOP), "no_preflop") == 0.015


def test_all_features_disabled_reproduce_frozen_policy_actions():
    experimental = Policy(BASE)
    original_memory, new_memory = {}, {}
    config = AgentConfig(num_hands=1000)
    baseline_strategy.new_half(config, original_memory)
    experimental.new_half(config, new_memory)
    rng = Random(778)
    for index in range(25):
        game = Game(make_deal("ablation-equivalence", index), index % 2, index)
        while not game.is_terminal:
            obs = game.observation(game.to_act)
            if game.to_act == 0:
                # Remove machine-load-dependent pacing from this equivalence check.
                original_memory["compute_seconds"] = new_memory["compute_seconds"] = 0
                old = baseline_strategy.choose_action(obs, original_memory)
                new = experimental.choose_action(obs, new_memory)
                assert old == new
                action = old
            else:
                action = rng.choice(obs.legal_actions)
            game.apply(action)
        result = game.hand_result(0)
        baseline_strategy.on_hand_end(result, original_memory)
        experimental.on_hand_end(result, new_memory)


@pytest.mark.parametrize("name", list(PROFILES)[1:])
def test_each_ablation_plays_legal_actions_and_resets(name):
    policy, memory = Policy(PROFILES[name]), {}
    policy.new_half(AgentConfig(num_hands=1000), memory)
    for index in range(8):
        game = Game(make_deal("ablation-legal", index), index % 2, index)
        while not game.is_terminal:
            obs = game.observation(game.to_act)
            action = policy.choose_action(obs, memory) if game.to_act == 0 else Action.CHECK_CALL
            assert isinstance(action, Action) and action in obs.legal_actions
            game.apply(action)
        policy.on_hand_end(game.hand_result(0), memory)
    assert memory["experiment"]["sampled_trials"] > 0
    policy.new_half(AgentConfig(), memory)
    assert memory["experiment"]["sampled_trials"] == 0
    assert memory["compute_seconds"] == 0
