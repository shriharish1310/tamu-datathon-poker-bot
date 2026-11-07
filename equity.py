"""Deterministic, dependency-free equity estimates for the official PLO5 game.

Equity is the expected showdown pot share versus a uniformly sampled legal
opponent hand. It is not an estimate against an opponent's betting range.
The official evaluator supplies all short-deck ranking rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import sqrt
from random import Random
from typing import Sequence

from evaluator import NUM_CARDS, category_of, get_table


@dataclass(frozen=True, slots=True)
class EquityEstimate:
    equity: float
    stderr: float
    samples: int
    current_category: int | None


def _pair_masks(bits: Sequence[int]) -> tuple[int, ...]:
    """All ten ways to select exactly two of five private cards."""
    a, b, c, d, e = bits
    return (a | b, a | c, a | d, a | e, b | c,
            b | d, b | e, c | d, c | e, d | e)


def _triple_masks(bits: Sequence[int]) -> tuple[int, ...]:
    """All ways to select exactly three public cards, including partial boards."""
    if len(bits) == 5:
        a, b, c, d, e = bits
        return (a | b | c, a | b | d, a | b | e, a | c | d,
                a | c | e, a | d | e, b | c | d, b | c | e,
                b | d | e, c | d | e)
    return tuple(a | b | c for a, b, c in combinations(bits, 3))


def _score_masks(
    hole_masks: Sequence[int], board_masks: Sequence[int], table: dict[int, int]
) -> int:
    """Score a legal Omaha hand; callers guarantee disjoint private/public cards."""
    best = 0
    for hm in hole_masks:
        for bm in board_masks:
            score = table[hm | bm]
            if score > best:
                best = score
    return best


def estimate_equity(
    hole: Sequence[int],
    board: Sequence[int],
    *,
    samples: int = 32,
    seed: int = 0,
) -> EquityEstimate:
    """Estimate win probability plus half the tie probability.

    Each independent trial draws the opponent's five cards and the remaining
    board together, without replacement from unseen cards. A local RNG makes
    calls repeatable without touching Python's global random state. ``stderr``
    is the empirical Monte Carlo standard error, not a strategy confidence
    bound; it excludes uncertainty about an opponent's range. With one sample
    its conservative fallback is 0.5. ``current_category`` uses only the visible
    board and is ``None`` before the flop.

    The official lookup table should be warmed at application startup so its
    one-time construction is outside the competition's action time budget.
    """
    hole = tuple(hole)
    board = tuple(board)
    if len(hole) != 5 or len(board) not in (0, 3, 4, 5):
        raise ValueError("need five hole cards and a board of length 0, 3, 4 or 5")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise ValueError("samples must be a positive integer")
    known = hole + board
    if any(isinstance(card, bool) or not isinstance(card, int)
           or not 0 <= card < NUM_CARDS for card in known):
        raise ValueError("cards must be integers from 0 to 35")
    if len(set(known)) != len(known):
        raise ValueError("hole and board cards must be distinct")

    table = get_table()
    hero_masks = _pair_masks(tuple(1 << card for card in hole))
    board_bits = tuple(1 << card for card in board)
    visible_masks = _triple_masks(board_bits)
    current_score = _score_masks(hero_masks, visible_masks, table) if board else None
    current_category = category_of(current_score) if current_score is not None else None
    known_set = set(known)
    unseen_bits = tuple(1 << card for card in range(NUM_CARDS) if card not in known_set)
    draw_count = 10 - len(board)
    sample = Random(seed).sample
    total = 0.0
    squares = 0.0

    for _ in range(samples):
        drawn = sample(unseen_bits, draw_count)
        if len(board) == 5:
            board_masks = visible_masks
            hero_score = current_score
        else:
            board_masks = _triple_masks(board_bits + tuple(drawn[5:]))
            hero_score = _score_masks(hero_masks, board_masks, table)
        villain_score = _score_masks(_pair_masks(drawn[:5]), board_masks, table)
        result = 1.0 if hero_score > villain_score else (0.5 if hero_score == villain_score else 0.0)
        total += result
        squares += result * result

    equity = total / samples
    variance = max(0.0, squares - total * total / samples)
    stderr = sqrt(variance / (samples * (samples - 1))) if samples > 1 else 0.5
    return EquityEstimate(equity, stderr, samples, current_category)
