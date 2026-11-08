"""Independent rule, sampling, state-isolation, and strategy regression checks."""
import itertools
import random
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import agent
from evaluator import cards_from_str, omaha_score, score_five
from game import Action, AgentConfig, Game, make_deal


def test_all_five_card_lookup_scores_match_referee():
    # Exhaustively check every legal 5-card hand, including the short-deck wheel.
    for cards in itertools.combinations(range(36), 5):
        index = sum(5 ** (c >> 2) for c in cards)
        flush = int(len({c & 3 for c in cards}) == 1)
        assert agent._SCORE[flush, index] == score_five(cards)


def test_omaha_evaluator_matches_referee():
    rng = random.Random(4571)
    for _ in range(2000):
        cards = rng.sample(range(36), 10)
        hole, board = cards[:5], cards[5:]
        assert agent._fast_score(np.array(hole, dtype=np.int32), np.array(board, dtype=np.int32), agent._SCORE) == omaha_score(hole, board)


def test_exactly_two_hole_cards_required():
    hole = np.array(cards_from_str('Th 7s 7d 8c 9c'), dtype=np.int32)
    board = np.array(cards_from_str('Ah Kh Qh Jh 6c'), dtype=np.int32)
    assert agent._fast_score(hole, board, agent._SCORE) >> 20 == 3  # straight, not flush


def test_samples_are_legal_and_river_results_exact():
    hole = np.array([0, 5, 10, 15, 20], dtype=np.int32)
    board = np.array([24, 29, 34, 3, 9], dtype=np.int32)
    other, scores, results = agent._sample(hole, board, 300, 1, np.uint64(987), agent._SCORE, agent._PREFLOP)
    mine = omaha_score(hole.tolist(), board.tolist())
    for h, strength, outcome in zip(other, scores, results):
        assert len(set(h)) == 5
        assert not set(h).intersection(set(hole) | set(board))
        theirs = omaha_score(h.tolist(), board.tolist())
        assert strength[3] == theirs
        assert outcome == (1.0 if mine > theirs else 0.5 if mine == theirs else 0.0)


def test_preflop_data_is_complete_and_suit_invariant():
    assert agent._DATA.is_file(), 'Run tools/train_preflop.py before shipping'
    assert agent._PREFLOP.shape == (376992,)
    assert 0.49 < agent._PREFLOP.mean() < 0.51
    assert agent._PREFLOP.std() > 0.02
    rng = random.Random(135)
    for _ in range(200):
        hole = rng.sample(range(36), 5)
        value = agent._PREFLOP[agent._index(np.array(hole, dtype=np.int32))]
        for perm in itertools.permutations(range(4)):
            changed = np.array([(c & ~3) | perm[c & 3] for c in hole], dtype=np.int32)
            assert agent._PREFLOP[agent._index(changed)] == value


def test_half_reset_reproduces_decisions_without_fallbacks():
    def run(memory):
        agent.new_half(AgentConfig(), memory)
        actions = []
        for hand in range(50):
            game = Game(make_deal('isolation', hand), hand % 2, hand)
            while not game.is_terminal:
                obs = game.observation(game.to_act)
                if game.to_act == 0:
                    action = agent.choose_action(obs, memory)
                    actions.append(action)
                else:
                    action = Action.RAISE_POT if Action.RAISE_POT in obs.legal_actions else Action.CHECK_CALL
                assert action in obs.legal_actions
                game.apply(action)
            agent.on_hand_end(game.hand_result(0), memory)
        assert memory['fallback_count'] == 0
        return actions
    memory = {}
    assert run(memory) == run(memory)


def test_unbeatable_river_hand_value_bets():
    from dataclasses import replace
    from game import Street
    memory = {}
    agent.new_half(AgentConfig(), memory)
    obs = Game(make_deal('nuts', 0), 0).observation(0)
    obs = replace(obs, street=Street.RIVER,
                  hole_cards=tuple(cards_from_str('Ah Kh 6c 7d 8s')),
                  board=tuple(cards_from_str('Qh Jh Th 9c 6d')),
                  pot=20, to_call=0, my_bet=0, opp_bet=0,
                  my_stack=70, opp_stack=70,
                  legal_actions=(Action.CHECK_CALL, Action.RAISE_HALF, Action.RAISE_POT),
                  raise_to={Action.RAISE_HALF: 10, Action.RAISE_POT: 20})
    assert agent.choose_action(obs, memory) == Action.RAISE_POT
    assert memory['fallback_count'] == 0


def test_forced_terminal_call_does_not_imply_passivity():
    from dataclasses import replace
    from game import HandResult
    memory = {}
    agent.new_half(AgentConfig(), memory)
    obs = Game(make_deal('cap', 0), 0).observation(0)
    obs = replace(obs, raises_this_street=3)
    memory['last_obs'] = obs
    memory['last_action'] = Action.RAISE_POT
    before = memory['counts'].copy()
    result = HandResult(hand_index=0, my_net=0, pot=160, went_to_showdown=True,
                        board=(), opp_hole=None, winner='split')
    agent.on_hand_end(result, memory)
    assert np.array_equal(before, memory['counts'])
