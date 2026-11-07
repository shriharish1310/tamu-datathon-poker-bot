"""Cross-check Monte Carlo sampling and scoring against the official evaluator."""

import random
import unittest
from itertools import combinations
from unittest.mock import patch

from equity import _pair_masks, _score_masks, _triple_masks, estimate_equity
from evaluator import cards_from_str, get_table, omaha_score, score_five


class EquityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = get_table()

    def test_mask_scores_match_official_on_full_and_partial_boards(self):
        rng = random.Random(112)
        for _ in range(100):
            cards = rng.sample(range(36), 10)
            hole, board = cards[:5], cards[5:]
            pairs = _pair_masks(tuple(1 << c for c in hole))
            for count in (3, 4, 5):
                visible = board[:count]
                optimized = _score_masks(pairs, _triple_masks(tuple(1 << c for c in visible)), self.table)
                reference = max(score_five(h + b) for h in combinations(hole, 2)
                                for b in combinations(visible, 3))
                self.assertEqual(optimized, reference)
            self.assertEqual(optimized, omaha_score(hole, board))

    def test_reference_sampling_matches_and_has_no_card_collisions(self):
        hole = cards_from_str("AsKs6c7d8h")
        for board in ([], cards_from_str("QsJhTc"),
                      cards_from_str("QsJhTc6h"), cards_from_str("QsJhTc6h7h")):
            known = set(hole + board)
            deck = [c for c in range(36) if c not in known]
            rng = random.Random(19)
            payoffs = []
            for _ in range(40):
                draw = rng.sample(deck, 10 - len(board))
                self.assertEqual(len(set(draw)), len(draw))
                self.assertFalse(known.intersection(draw))
                opponent, runout = draw[:5], board + draw[5:]
                hero_score = omaha_score(hole, runout)
                opponent_score = omaha_score(opponent, runout)
                payoffs.append(1 if hero_score > opponent_score else 0.5 if hero_score == opponent_score else 0)
            actual = estimate_equity(hole, board, samples=40, seed=19)
            self.assertEqual(actual.equity, sum(payoffs) / 40)
            self.assertEqual(actual.samples, 40)
            self.assertGreaterEqual(actual.stderr, 0)
            self.assertEqual(actual.current_category is None, not board)

    def test_royal_flush_is_unbeatable_and_uses_only_known_category(self):
        result = estimate_equity(cards_from_str("AsKs6d7d8d"),
                                 cards_from_str("QsJsTs6h7h"), samples=64)
        self.assertEqual(result.equity, 1)
        self.assertEqual(result.current_category, 8)

    def test_real_tied_full_houses_split_equity(self):
        hole = cards_from_str("KcKd6c7d8c")
        board = cards_from_str("AcAdAh9sTc")
        villain = cards_from_str("KhKs6d7c8d")
        self.assertEqual(omaha_score(hole, board), omaha_score(villain, board))
        with patch("equity.Random") as rng:
            rng.return_value.sample.return_value = [1 << card for card in villain]
            result = estimate_equity(hole, board, samples=3)
        self.assertEqual(result.equity, 0.5)
        self.assertEqual(result.stderr, 0)

    def test_repeatable_and_does_not_mutate_global_rng(self):
        hole = cards_from_str("AsKs6c7d8h")
        state = random.getstate()
        first = estimate_equity(hole, [], samples=32, seed=5)
        self.assertEqual(first, estimate_equity(hole, [], samples=32, seed=5))
        self.assertEqual(state, random.getstate())

    def test_rejects_invalid_observations(self):
        valid = [0, 1, 2, 3, 4]
        for hole, board, samples in ((valid, [4, 5, 6], 2), (valid, [5], 2),
                                      (valid[:-1], [], 2), (valid, [], 0),
                                      ([0, 1, 2, 3, 36], [], 2), (valid, [], True)):
            with self.assertRaises(ValueError):
                estimate_equity(hole, board, samples=samples)


if __name__ == "__main__":
    unittest.main()
