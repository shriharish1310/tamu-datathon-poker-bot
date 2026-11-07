"""Controlled Starfish ablations; baseline remains a frozen, separate policy."""
from time import perf_counter

import baseline_strategy as base
from equity import estimate_equity
from game import Action, Street
from policy_config import PolicyConfig, PROFILES
from range_equity import Rollouts


def position_margin(obs, mode):
    street = int(obs.street)
    if street == 3 or mode == "none":
        return 0.0
    if street == 0:
        if mode == "no_preflop":
            return 0.0
        if mode == "street_order":
            return 0.015 if obs.is_button else 0.0
    return 0.015 if not obs.is_button else 0.0


def range_parameters(obs, aggression, blend):
    """Condition on an actual observed raise, never mistake posted blinds for one."""
    raises = [ev for ev in obs.action_history if not ev.is_me and ev.action in base.RAISES
              and ev.street == obs.street]
    if not raises or not blend:
        return 0.0, 2.0
    last = raises[-1]
    power = 3.0 if last.action == Action.RAISE_POT else 2.0
    selectivity = max(0.0, 0.65 - aggression) / 0.65
    mix = min(0.90, blend * selectivity * (1.15 if last.action == Action.RAISE_POT else 1.0))
    return mix, power


class Policy:
    def __init__(self, settings: PolicyConfig):
        self.settings = settings

    def new_half(self, config, memory):
        base.new_half(config, memory)
        memory["experiment"] = dict(extra_samples=0, refinements=0, weighted_decisions=0,
                                    caller_decisions=0, sampled_states=0, sampled_trials=0)

    def on_hand_end(self, result, memory):
        base.on_hand_end(result, memory)

    def choose_action(self, obs, memory):
        started = perf_counter()
        action = self.decide(obs, memory)
        if not isinstance(action, Action) or action not in obs.legal_actions:
            raise ValueError(f"Illegal experimental decision: {action!r}")
        memory["last_action"], memory["last_street"] = action, int(obs.street)
        memory["decisions"] += 1
        memory["compute_seconds"] += perf_counter() - started
        return action

    def decide(self, obs, memory):
        base._observe(obs, memory)
        legal, settings = obs.legal_actions, self.settings
        if len(legal) == 1:
            return legal[0]
        street, seed = int(obs.street), base._seed(obs)
        fold_rate = memory["folds"][street] / (memory["folds"][street] + memory["continues"][street])
        aggression = memory["raises"][street] / (memory["raises"][street] + memory["passive"][street])
        mix, power = range_parameters(obs, aggression, settings.range_blend)
        config = memory["config"]
        allowance = config.time_bank_seconds * settings.compute_fraction
        expected_spent = allowance * max(0.1, (obs.hand_index + 1) / max(1, config.num_hands))
        under_budget = memory["compute_seconds"] <= expected_spent
        samples = settings.samples[street] if under_budget else max(8, settings.samples[street] // 2)
        extended = bool(settings.range_blend or settings.caller_power or settings.adaptive_max)
        key = (obs.hole_cards, obs.board)
        cached = memory["cache"].get(key)
        if cached is None:
            if extended:
                cached = Rollouts(obs.hole_cards, obs.board, seed,
                                  features=bool(settings.range_blend or settings.caller_power))
                cached.extend(samples)
            else:
                cached = estimate_equity(obs.hole_cards, obs.board, samples=samples, seed=seed)
            memory["cache"][key] = cached
            memory["experiment"]["sampled_states"] += 1
            memory["experiment"]["sampled_trials"] += samples
        raises = [action for action in base.RAISES if action in legal]
        cost = min(obs.to_call, obs.my_stack)
        pot_odds = cost / max(1, obs.pot + cost)
        margin = (0.045, 0.035, 0.020, 0.0)[street] + position_margin(obs, settings.position)
        if obs.opp_stack == 0 or cost == obs.my_stack:
            margin = 0.0
        threshold = (0.57 if not obs.to_call else 0.64) + 0.04 * fold_rate
        if not obs.to_call and memory["continues"][street] > 18 and fold_rate < 0.12:
            threshold = 0.53
        penalty = 0.0
        if obs.to_call and not settings.range_blend:
            penalty = max(0.0, 0.60 - aggression) * (0.17 if street else 0.10)
            penalty += min(0.08, max(0, obs.raises_this_street - 1) * 0.025) * (1 - aggression)

        def evaluate():
            estimates = (cached.estimates(range_mix=mix, range_power=power,
                                         caller_power=settings.caller_power, fold_rate=fold_rate)
                         if extended else (cached,) * 3)
            values = []
            for estimate in estimates:
                n = getattr(estimate, "effective_samples", estimate.samples)
                equity = (estimate.equity * n + 2.0) / (n + 4.0)
                values.append(max(0.0, min(1.0, equity - penalty)))
            return estimates, values

        estimates, values = evaluate()
        if settings.adaptive_max and under_budget:
            distances = [(abs(values[0] - pot_odds - margin), estimates[0].stderr)] if cost else []
            if raises:
                distances += [(abs(values[i] - threshold - 0.12 * estimates[i].stderr), estimates[i].stderr)
                              for i in (1, 2)]
            if any(distance < settings.boundary_sigma * error for distance, error in distances):
                target = min(settings.adaptive_max, max(2 * len(cached.payoffs), 64))
                extra = target - len(cached.payoffs)
                if extra > 0:
                    cached.extend(target)
                    memory["experiment"]["refinements"] += 1
                    memory["experiment"]["extra_samples"] += extra
                    memory["experiment"]["sampled_trials"] += extra
                    estimates, values = evaluate()
        memory["experiment"]["weighted_decisions"] += bool(mix)
        memory["experiment"]["caller_decisions"] += bool(settings.caller_power and raises)
        equity = values[0]
        if raises:
            half_good = values[1] > threshold + 0.12 * estimates[1].stderr
            pot_good = values[2] > threshold + 0.12 * estimates[2].stderr
            if pot_good and Action.RAISE_POT in raises and (values[2] > 0.70 or fold_rate < 0.20):
                return Action.RAISE_POT
            if half_good and Action.RAISE_HALF in raises:
                return Action.RAISE_HALF
            if pot_good and Action.RAISE_HALF not in raises and Action.RAISE_POT in raises:
                return Action.RAISE_POT
            draw, blocker = base._draw_and_blocker(obs)
            preferred = Action.RAISE_HALF if Action.RAISE_HALF in raises else raises[0]
            risk = obs.raise_to[preferred] - obs.my_bet
            observations = memory["folds"][street] + memory["continues"][street] - 10
            credible = observations >= 12 and fold_rate > risk / max(1, obs.pot + risk) + 0.08
            semibluff = draw and equity >= 0.30 and street < 3
            river_bluff = blocker and equity < 0.40 and street == 3
            steal = street == 0 and obs.is_button and obs.raises_this_street == 0
            mix_random = (((seed ^ (len(obs.action_history) * 2246822519)) * 3266489917) & 0xFFFFFFFF) / 2**32
            if credible and (semibluff or river_bluff or steal) and mix_random < 0.35:
                return preferred
        if cost == 0 or equity >= pot_odds + margin:
            return Action.CHECK_CALL
        return Action.FOLD if Action.FOLD in legal else Action.CHECK_CALL


def build_policy(name):
    return base if name == "baseline" else Policy(PROFILES[name])
