"""Parameterized research opponents; no access to champion internals or deals.

Decision rules are independent of Starfish's betting policy. The numerical
rollout/evaluator infrastructure is shared, so this is not solver diversity.
"""
from dataclasses import asdict, dataclass
from math import exp
from random import Random
from time import perf_counter

from game import Action
from range_equity import Rollouts, summarize_weighted


@dataclass(frozen=True)
class OpponentConfig:
    name: str
    family: str
    call_margin: float = 0.03
    value_threshold: float = 0.62
    reraise_extra: float = 0.06
    bluff_rate: float = 0.05
    pot_probability: float = 0.5
    size_pressure: float = 0.03
    button_discount: float = 0.015
    river_shift: float = 0.0
    range_aware: bool = False
    range_cutoff: float = 0.70
    range_width: float = 0.12
    range_bluff: float = 0.12
    samples: tuple = (32, 40, 48, 64)
    compute_seconds: float = 2.0
    salt: int = 8191

    def to_dict(self):
        return asdict(self)


class Opponent:
    def __init__(self, config):
        self.config = config

    def new_half(self, config, memory):
        memory.clear()
        memory.update(hand=-1, cache={}, seen=0, raises=[2.0]*4,
                      passive=[6.0]*4, elapsed=0.0, config=config)

    def on_hand_end(self, result, memory):
        if result.hand_index == memory['hand']:
            memory['cache'].clear()

    def choose_action(self, obs, memory):
        started = perf_counter()
        action = self.decide(obs, memory)
        memory['elapsed'] += perf_counter() - started
        if not isinstance(action, Action) or action not in obs.legal_actions:
            raise ValueError('Research opponent returned an illegal action')
        return action

    def decide(self, obs, m):
        cfg = self.config
        if m['hand'] != obs.hand_index:
            m.update(hand=obs.hand_index, cache={}, seen=0)
        for event in obs.action_history[m['seen']:]:
            if not event.is_me:
                m['raises' if event.action in (Action.RAISE_HALF, Action.RAISE_POT)
                  else 'passive'][int(event.street)] += 1
        m['seen'] = len(obs.action_history)
        if len(obs.legal_actions) == 1:
            return obs.legal_actions[0]
        street = int(obs.street)
        seed = cfg.salt ^ (obs.hand_index * 2654435761)
        for card in (*obs.hole_cards, *obs.board):
            seed = ((seed ^ (card + 1)) * 16777619) & 0xffffffff
        rng = Random(seed ^ (len(obs.action_history) * 2246822519))
        key = (obs.hole_cards, obs.board)
        if key not in m['cache']:
            count = cfg.samples[street]
            pace = cfg.compute_seconds * max(.1, (obs.hand_index+1)/m['config'].num_hands)
            if m['elapsed'] > pace:
                count = max(8, count//2)
            batch = Rollouts(*key, seed, features=cfg.range_aware)
            batch.extend(count)
            m['cache'][key] = batch
        batch = m['cache'][key]
        estimate = batch.estimates()[0]
        raises_seen = [e for e in obs.action_history if not e.is_me and e.street == obs.street
                       and e.action in (Action.RAISE_HALF, Action.RAISE_POT)]
        if cfg.range_aware and raises_seen:
            # A logistic action likelihood with a bluff floor, not champion's
            # power-law weighting. Features never use unrevealed board cards.
            batch.estimates(range_mix=.01)  # materialize cached visible percentiles
            aggression = m['raises'][street] / (m['raises'][street]+m['passive'][street])
            cutoff = max(.25, min(.9, cfg.range_cutoff + .12*(raises_seen[-1].action == Action.RAISE_POT)
                                 - .5*(aggression-.25)))
            floor = min(.8, cfg.range_bluff + .4*aggression)
            weights = [floor+(1-floor)/(1+exp(-(q-cutoff)/cfg.range_width))
                       for q in batch.percentiles]
            estimate = summarize_weighted(batch.payoffs, weights)
        n = estimate.effective_samples
        equity = (estimate.equity*n+1)/(n+2)
        cost = min(obs.to_call, obs.my_stack)
        odds = cost / max(1, obs.pot+cost)
        margin = cfg.call_margin + cfg.size_pressure * cost/max(1,obs.pot)
        margin -= cfg.button_discount * obs.is_button * (street < 3)
        if cost == obs.my_stack or obs.opp_stack == 0:
            margin = min(0.0, margin)
        threshold = cfg.value_threshold + cfg.reraise_extra * bool(cost)
        threshold += cfg.river_shift * (street == 3)
        raises = [a for a in (Action.RAISE_HALF, Action.RAISE_POT) if a in obs.legal_actions]
        # Polar bluffs retain low showdown value; value hands use independent
        # thresholds and size mixing rather than copying champion decisions.
        bluff = equity < .48 and rng.random() < cfg.bluff_rate
        if raises and (equity >= threshold or bluff):
            desired = Action.RAISE_POT if rng.random() < cfg.pot_probability else Action.RAISE_HALF
            return desired if desired in raises else raises[0]
        if cost == 0 or equity >= odds+margin:
            return Action.CHECK_CALL
        return Action.FOLD if Action.FOLD in obs.legal_actions else Action.CHECK_CALL
