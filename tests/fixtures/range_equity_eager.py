"""Incremental importance-weighted equity with visible-information range features.

Range likelihoods are explicit heuristics, not learned or equilibrium ranges.
Future runout cards affect showdown payoffs ONLY, never an action likelihood.
"""
from dataclasses import dataclass
from math import sqrt
from random import Random

from equity import _pair_masks, _score_masks, _triple_masks
from evaluator import get_table, category_of


@dataclass(frozen=True)
class WeightedEstimate:
    equity: float
    stderr: float
    samples: int
    effective_samples: float
    current_category: int | None


def visible_strength(hole, board, made_score=None):
    """Ordering proxy from known cards, with a small nut-flush-draw bonus.

    Preflop pairs and connectivity are features, not calibrated probabilities.
    Extra copies of a rank receive no made-hand bonus: Omaha uses two hole cards.
    """
    ranks = [0] * 9
    suits = [0] * 4
    for card in hole:
        ranks[card >> 2] += 1
        suits[card & 3] += 1
    if not board:
        score = sum((r / 8) * 0.12 for r, count in enumerate(ranks) if count)
        score += sum(0.18 + r * 0.025 for r, count in enumerate(ranks) if count >= 2)
        score += sum(0.12 for count in suits if count >= 2)
        score -= sum(0.08 * (count - 2) for count in ranks if count > 2)
        score += 0.05 * sum(bool(ranks[r] and ranks[r + 1]) for r in range(8))
        return score
    if made_score is None:
        made_score = _score_masks(_pair_masks(tuple(1 << c for c in hole)),
                                 _triple_masks(tuple(1 << c for c in board)), get_table())
    strength = made_score / (1 << 20)
    if len(board) < 5:
        public_suits = [0] * 4
        for card in board:
            public_suits[card & 3] += 1
        for suit in range(4):
            if public_suits[suit] == 2 and suits[suit] >= 2:
                strength += 0.55 if (32 + suit) in hole else 0.30
    return strength


def midrank_percentiles(values):
    """Tie-aware empirical ranks; independent of rollout payoffs/runouts."""
    ordered = sorted(range(len(values)), key=values.__getitem__)
    answer = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        q = (start + end) / (2 * len(ordered))
        for index in ordered[start:end]:
            answer[index] = q
        start = end
    return answer


def summarize_weighted(payoffs, weights, category=None):
    n = len(payoffs)
    if not n or len(weights) != n or any(w <= 0 for w in weights):
        raise ValueError("Need equally sized payoffs and positive weights")
    total = sum(weights)
    mean = sum(w * x for w, x in zip(weights, payoffs)) / total
    ess = total * total / sum(w * w for w in weights)
    # Self-normalized importance-sampling Monte Carlo error; excludes range-model
    # uncertainty. Empirical ranks and adaptive sampling make this approximate.
    variance = sum(w * w * (x - mean) ** 2 for w, x in zip(weights, payoffs))
    stderr = sqrt(n / (n - 1) * variance / total**2) if n > 1 else 0.5
    return WeightedEstimate(mean, stderr, n, ess, category)


class Rollouts:
    """Cache an extensible sample stream for a fixed private hand and board."""
    def __init__(self, hole, board, seed, *, features=True):
        self.hole, self.board = tuple(hole), tuple(board)
        known = self.hole + self.board
        if (len(self.hole) != 5 or len(self.board) not in (0, 3, 4, 5)
                or len(set(known)) != len(known)
                or any(type(c) is not int or not 0 <= c < 36 for c in known)):
            raise ValueError("Invalid Omaha cards")
        self.table = get_table()
        self.hero_masks = _pair_masks(tuple(1 << c for c in self.hole))
        self.board_bits = tuple(1 << c for c in self.board)
        self.visible_masks = _triple_masks(self.board_bits)
        self.hero_score = (_score_masks(self.hero_masks, self.visible_masks, self.table)
                           if self.board else None)
        self.category = category_of(self.hero_score) if self.board else None
        self.unseen = tuple(c for c in range(36) if c not in known)
        self.rng = Random(seed)
        self.features = features
        self.payoffs, self.strengths = [], []
        self.percentiles = None

    def extend(self, total):
        if type(total) is not int or total < 1:
            raise ValueError("Sample count must be positive")
        if total <= len(self.payoffs):
            return
        for _ in range(total - len(self.payoffs)):
            drawn = self.rng.sample(self.unseen, 10 - len(self.board))
            opponent = drawn[:5]
            villain_masks = _pair_masks(tuple(1 << c for c in opponent))
            if len(self.board) == 5:
                board_masks, hero = self.visible_masks, self.hero_score
            else:
                board_masks = _triple_masks(self.board_bits + tuple(1 << c for c in drawn[5:]))
                hero = _score_masks(self.hero_masks, board_masks, self.table)
            villain = _score_masks(villain_masks, board_masks, self.table)
            self.payoffs.append(1.0 if hero > villain else (0.5 if hero == villain else 0.0))
            if self.features:
                visible = (villain if len(self.board) == 5 else
                           _score_masks(villain_masks, self.visible_masks, self.table) if self.board else None)
                self.strengths.append(visible_strength(opponent, self.board, visible))
        self.percentiles = None

    def estimates(self, *, range_mix=0.0, range_power=2.0, caller_power=0.0, fold_rate=0.2):
        if not self.payoffs:
            raise ValueError("Generate rollouts before estimating")
        if not 0 <= range_mix <= 1 or caller_power < 0:
            raise ValueError("Invalid range parameters")
        if range_mix or caller_power:
            if not self.features:
                raise ValueError("Range features were disabled")
            if self.percentiles is None:
                self.percentiles = midrank_percentiles(self.strengths)
            ranks = self.percentiles
        else:
            ranks = [0.5] * len(self.payoffs)
        weights = [(1 - range_mix + range_mix * q) ** range_power for q in ranks]
        current = summarize_weighted(self.payoffs, weights, self.category)
        if not caller_power:
            return current, current, current
        # A folding opponent's continuing range is narrower. Larger raises use a
        # stronger likelihood tilt. A positive rank floor retains weak calls.
        power = min(5.0, caller_power * fold_rate / max(0.05, 1 - fold_rate))
        callers = [summarize_weighted(self.payoffs,
                   [w * (0.05 + 0.95 * q) ** min(5.0, power * size) for w, q in zip(weights, ranks)],
                   self.category) for size in (1.0, 1.4)]
        return current, *callers
