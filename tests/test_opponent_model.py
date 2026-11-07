"""Regression tests for observations, delayed results, and selective bluffs."""

from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import strategy
from equity import EquityEstimate
from evaluator import cards_from_str
from game import Action, AgentConfig, Deal, Game, Street, make_deal


def _memory():
    memory = {}
    strategy.new_half(AgentConfig(), memory)
    return memory


def _mock_equity(monkeypatch, equity):
    monkeypatch.setattr(
        strategy, "estimate_equity",
        lambda *args, **kwargs: EquityEstimate(equity, 0.01, 64, None),
    )


def _river_game(deal=None):
    # Seat zero is out of position and acts first on the river.
    game = Game(deal or make_deal("opponent-model-river", 0), button_seat=1)
    while game.street != Street.RIVER:
        game.apply(Action.CHECK_CALL)
    assert game.to_act == 0
    return game


def _posterior(memory):
    return {key: list(memory[key]) for key in ("folds", "continues", "raises", "passive")}


@pytest.mark.parametrize("response", [Action.FOLD, Action.CHECK_CALL])
def test_terminal_response_enters_both_posteriors_only_when_delivered(monkeypatch, response):
    _mock_equity(monkeypatch, 1.0)
    game, memory = _river_game(), _memory()
    action = strategy.choose_action(game.observation(0), memory)
    assert action in strategy.RAISES
    game.apply(action)
    before = _posterior(memory)
    game.apply(response)
    assert game.is_terminal
    assert _posterior(memory) == before  # unseen terminal response is not known yet

    strategy.on_hand_end(game.hand_result(0), memory)
    expected = deepcopy(before)
    expected["passive"][int(Street.RIVER)] += 1
    key = "folds" if response == Action.FOLD else "continues"
    expected[key][int(Street.RIVER)] += 1
    assert _posterior(memory) == expected
    assert memory["last_action"] is None

    # Processing the next observation cannot count the previous response again.
    next_game = Game(make_deal("opponent-model-river", 1), button_seat=0, hand_index=1)
    strategy.choose_action(next_game.observation(0), memory)
    assert _posterior(memory) == expected


def test_repeated_history_does_not_double_count_opponent_response(monkeypatch):
    _mock_equity(monkeypatch, 1.0)
    memory = _memory()
    game = Game(make_deal("opponent-history", 0), button_seat=0)
    action = strategy.choose_action(game.observation(0), memory)
    assert action in strategy.RAISES
    game.apply(action)
    game.apply(Action.CHECK_CALL)
    game.apply(Action.CHECK_CALL)  # opponent's first action on the flop is a check
    obs = game.observation(0)
    _mock_equity(monkeypatch, 0.2)
    strategy.choose_action(obs, memory)
    first = _posterior(memory)
    assert first["continues"][int(Street.PREFLOP)] == 9.0
    assert first["passive"][int(Street.PREFLOP)] == 7.0
    assert first["passive"][int(Street.FLOP)] == 7.0
    strategy.choose_action(obs, memory)
    assert _posterior(memory) == first


def test_new_half_erases_learned_opponent_state_and_pending_action(monkeypatch):
    _mock_equity(monkeypatch, 1.0)
    memory, game = _memory(), _river_game()
    game.apply(strategy.choose_action(game.observation(0), memory))
    game.apply(Action.FOLD)
    strategy.on_hand_end(game.hand_result(0), memory)
    memory["old_half_marker"] = "must disappear"
    config = AgentConfig(num_hands=250, time_bank_seconds=3.0)
    strategy.new_half(config, memory)
    fresh = {}
    strategy.new_half(config, fresh)
    assert memory == fresh


@pytest.mark.parametrize(
    "has_blocker,folds,continues,expected",
    [
        (True, 42.0, 8.0, Action.RAISE_HALF),
        (False, 42.0, 8.0, Action.CHECK_CALL),
        (True, 2.0, 80.0, Action.CHECK_CALL),
        (True, 3.0, 8.0, Action.CHECK_CALL),
    ],
)
def test_weak_river_bluff_needs_blocker_and_observed_folds(
    monkeypatch, has_blocker, folds, continues, expected
):
    # An ace of spades blocks the best flush, but one spade cannot make an
    # Omaha flush. The mocked low equity excludes ordinary value betting.
    hole = tuple(cards_from_str("As6c7d8h9c" if has_blocker else "Ah6c7d8h9c"))
    deal = Deal(
        (hole, tuple(cards_from_str("AdAc8s9hJh"))),
        tuple(cards_from_str("KsQsTs6d7h")),
    )
    obs = _river_game(deal).observation(0)
    memory = _memory()
    memory["folds"][int(Street.RIVER)] = folds
    memory["continues"][int(Street.RIVER)] = continues
    _mock_equity(monkeypatch, 0.2)
    monkeypatch.setattr(strategy, "_seed", lambda observation: 3)
    # Exercise the low random draw deterministically while leaving real game
    # betting amounts, legal actions, and card-removal constraints intact.
    assert strategy.choose_action(obs, memory) == expected
