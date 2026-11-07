"""Fast, adaptive baseline for the official short-deck PLO5 tournament.

Equity is Monte Carlo versus random legal holdings, NOT solved range equity.
Action-based adjustments and bet thresholds below are explicit heuristics.
All learned state lives in memory and is reset for each duplicate half.
"""

from __future__ import annotations

from collections import Counter
from time import perf_counter

from equity import estimate_equity
from game import Action, AgentConfig, HandResult, Observation, Street

RAISES = (Action.RAISE_HALF, Action.RAISE_POT)


def new_half(config: AgentConfig, memory: dict) -> None:
    memory.clear()
    memory.update(
        config=config, hands_played=0, hand_index=-1, history_seen=0,
        cache={}, last_action=None, last_street=0,
        # Beta priors: avoid drastic exploitation after one unusual hand.
        folds=[2.0] * 4, continues=[8.0] * 4,
        raises=[2.0] * 4, passive=[6.0] * 4,
        compute_seconds=0.0, decisions=0,
    )


def _observe(obs: Observation, memory: dict) -> None:
    if memory["hand_index"] != obs.hand_index:
        memory.update(hand_index=obs.hand_index, history_seen=0,
                      cache={}, last_action=None)
    history = obs.action_history
    for i in range(memory["history_seen"], len(history)):
        event = history[i]
        if event.is_me:
            continue
        street = int(event.street)
        memory["raises" if event.action in RAISES else "passive"][street] += 1
        if i and history[i - 1].is_me and history[i - 1].action in RAISES:
            key = "folds" if event.action == Action.FOLD else "continues"
            memory[key][street] += 1
    memory["history_seen"] = len(history)


def _seed(obs: Observation) -> int:
    """Stable private-card-dependent seed; never depends on hidden test deals."""
    value = 2166136261 ^ obs.hand_index
    for card in (*obs.hole_cards, *obs.board):
        value = ((value ^ (card + 1)) * 16777619) & 0xFFFFFFFF
    return value


def _draw_and_blocker(obs: Observation) -> tuple[bool, bool]:
    """Nut-flush draw and nut-flush blocker under the two-hole-card rule."""
    suits = Counter(card & 3 for card in obs.board)
    hole_suits = Counter(card & 3 for card in obs.hole_cards)
    aces = {card & 3 for card in obs.hole_cards if card >> 2 == 8}
    draw = len(obs.board) in (3, 4) and any(
        suits[suit] == 2 and hole_suits[suit] >= 2 for suit in aces
    )
    blocker = any(suits[suit] >= 3 for suit in aces)
    return draw, blocker


def _decide(obs: Observation, memory: dict) -> Action:
    _observe(obs, memory)
    legal = obs.legal_actions
    if len(legal) == 1:
        return legal[0]
    street = int(obs.street)
    seed = _seed(obs)
    cache_key = (obs.hole_cards, obs.board)
    estimate = memory["cache"].get(cache_key)
    if estimate is None:
        samples = (24, 32, 40, 64)[street]
        config = memory["config"]
        # Reserve most of the bank for HTTP/serialization and slower judge CPUs.
        allowance = max(0.0, config.time_bank_seconds * 0.35)
        expected_spent = allowance * max(0.1, (obs.hand_index + 1) / max(1, config.num_hands))
        if memory["compute_seconds"] > expected_spent:
            samples = max(8, samples // 2)
        estimate = estimate_equity(obs.hole_cards, obs.board, samples=samples, seed=seed)
        memory["cache"][cache_key] = estimate

    # Small-sample shrinkage avoids treating an 8/8 rollout as certainty.
    equity = (estimate.equity * estimate.samples + 2.0) / (estimate.samples + 4.0)
    fold_rate = memory["folds"][street] / (memory["folds"][street] + memory["continues"][street])
    aggression = memory["raises"][street] / (memory["raises"][street] + memory["passive"][street])
    # A bet from a passive opponent is stronger evidence than a habitual raise.
    range_penalty = max(0.0, 0.60 - aggression) * (0.17 if street else 0.10)
    if obs.to_call:
        equity -= range_penalty
        equity -= min(0.08, max(0, obs.raises_this_street - 1) * 0.025) * (1 - aggression)
    equity = max(0.0, min(1.0, equity))
    cost = min(obs.to_call, obs.my_stack)
    pot_odds = cost / max(1, obs.pot + cost)
    realization_margin = (0.045, 0.035, 0.020, 0.0)[street]
    if not obs.is_button and street != int(Street.RIVER):
        realization_margin += 0.015
    if obs.opp_stack == 0 or cost == obs.my_stack:
        realization_margin = 0.0  # no future betting when the call is all-in

    raises = [action for action in RAISES if action in legal]
    # Additional mixing is private-card-dependent and reproducible for evaluation.
    mix = (((seed ^ (len(obs.action_history) * 2246822519)) * 3266489917) & 0xFFFFFFFF) / 2**32
    if raises:
        # Equity against callers is usually below unconditional equity.
        threshold = (0.57 if not obs.to_call else 0.64) + 0.04 * fold_rate
        if not obs.to_call and memory["continues"][street] > 18 and fold_rate < 0.12:
            threshold = 0.53  # thin value against demonstrated calling stations
        if equity > threshold + 0.12 * estimate.stderr:
            if Action.RAISE_POT in raises and (equity > 0.70 or fold_rate < 0.20):
                return Action.RAISE_POT
            return Action.RAISE_HALF if Action.RAISE_HALF in raises else raises[0]

        draw, blocker = _draw_and_blocker(obs)
        # Bluff only with observed fold evidence; do not invent fold equity.
        preferred = Action.RAISE_HALF if Action.RAISE_HALF in raises else raises[0]
        risk = obs.raise_to[preferred] - obs.my_bet
        break_even_fold = risk / max(1, obs.pot + risk)
        observations = memory["folds"][street] + memory["continues"][street] - 10
        credible_folds = observations >= 12 and fold_rate > break_even_fold + 0.08
        semibluff = draw and equity >= 0.30 and street < int(Street.RIVER)
        river_bluff = blocker and equity < 0.40 and street == int(Street.RIVER)
        steal = street == int(Street.PREFLOP) and obs.is_button and obs.raises_this_street == 0
        if credible_folds and (semibluff or river_bluff or steal) and mix < 0.35:
            return preferred

    if cost == 0 or equity >= pot_odds + realization_margin:
        return Action.CHECK_CALL
    return Action.FOLD if Action.FOLD in legal else Action.CHECK_CALL


def choose_action(obs: Observation, memory: dict) -> Action:
    started = perf_counter()
    action = _decide(obs, memory)
    # Final guard keeps rule changes from turning a strategic mistake into forfeit.
    if action not in obs.legal_actions:
        action = Action.CHECK_CALL if Action.CHECK_CALL in obs.legal_actions else obs.legal_actions[0]
    memory["last_action"] = action
    memory["last_street"] = int(obs.street)
    memory["decisions"] += 1
    memory["compute_seconds"] += perf_counter() - started
    return action


def on_hand_end(result: HandResult, memory: dict) -> None:
    # Terminal responses do not appear in a subsequent observation.
    if result.hand_index == memory["hand_index"] and memory["last_action"] in RAISES:
        street = memory["last_street"]
        if result.went_to_showdown:
            memory["continues"][street] += 1
            memory["passive"][street] += 1
        elif result.winner == "me":
            memory["folds"][street] += 1
            memory["passive"][street] += 1
    memory["hands_played"] += 1
    if result.hand_index == memory["hand_index"]:
        memory["last_action"] = None
        memory["cache"].clear()
