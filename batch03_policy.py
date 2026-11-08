"""Research-only observability and uniform-preflop replacement.

The frozen Policy.decide and all postflop numerical code are imported unchanged.
Virtual sample counts retain champion's shrinkage formula; telemetry always
reports actual simulated trials separately. Positive range weights always use
the original seeded Monte Carlo stream, including when a later raise appears.
"""
from collections import Counter
import json
from math import sqrt
from pathlib import Path
import sys
from time import perf_counter, process_time

import advanced_policy
from advanced_policy import Policy
from policy_config import PolicyConfig
from range_equity import Rollouts, WeightedEstimate
from preflop_model import features, predict

ACTIVE = None
MODEL = None
LOAD_SECONDS = 0.


class ObservedRollouts(Rollouts):
    def extend(self, total):
        before = len(self.payoffs)
        super().extend(total)
        added = len(self.payoffs) - before
        if added and ACTIVE is not None:
            street = {0:0,3:1,4:2,5:3}[len(self.board)]
            ACTIVE['actual_trials'][street] += added
            ACTIVE['sample_hist'][f'{street}:{len(self.payoffs)}'] += 1

    def estimates(self, **kwargs):
        if ACTIVE is not None:
            ACTIVE['range_queries']['uniform' if not kwargs.get('range_mix') else 'conditioned'] += 1
        return super().estimates(**kwargs)


class HybridRollouts(ObservedRollouts):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.virtual_samples = 0
        self.model_estimate = None

    def extend(self, total):
        if self.board:
            return super().extend(total)
        self.virtual_samples = max(total, self.virtual_samples)
        if self.payoffs:
            return super().extend(total)

    def estimates(self, **kwargs):
        if self.board or kwargs.get('range_mix') or kwargs.get('caller_power'):
            if not self.board:
                ObservedRollouts.extend(self, self.virtual_samples)
                ACTIVE['preflop_conditioned_queries'] += 1
            return super().estimates(**kwargs)
        ACTIVE['model_queries'] += 1
        if self.model_estimate is None:
            started = perf_counter()
            p = predict(features(self.hole), MODEL)
            ACTIVE['inference_seconds'] += perf_counter() - started
            if p is None or not MODEL['support'][0] <= p <= MODEL['support'][1]:
                ACTIVE['ood_mc_routes'] += 1
                ObservedRollouts.extend(self, self.virtual_samples)
                return super().estimates(**kwargs)
            n = self.virtual_samples
            # Preserve conservative uncertainty in the unchanged value gate.
            uncertainty = max(MODEL['residual_sigma'], sqrt(p * (1-p) / max(1,n-1)))
            self.model_estimate = WeightedEstimate(p, uncertainty, n, float(n), None)
            ACTIVE['model_states'] += 1
            ACTIVE['virtual_sample_hist'][str(n)] += 1
        return (self.model_estimate,) * 3


class ObservedPolicy(Policy):
    def __init__(self, hybrid=False, model_path=None):
        global MODEL, LOAD_SECONDS
        settings = PolicyConfig(name='range_130_budget25',range_blend=1.3,compute_fraction=.25)
        super().__init__(settings)
        self.hybrid = hybrid
        if hybrid:
            started = perf_counter()
            MODEL = json.loads(Path(model_path or Path(__file__).with_name('preflop_weights.json')).read_text())
            LOAD_SECONDS = perf_counter() - started
        advanced_policy.Rollouts = HybridRollouts if hybrid else ObservedRollouts

    def new_half(self, config, memory):
        global ACTIVE
        super().new_half(config, memory)
        ACTIVE = memory['batch03'] = dict(actual_trials=[0]*4, sample_hist=Counter(),
            virtual_sample_hist=Counter(), range_queries=Counter(), model_queries=0,
            model_states=0, preflop_conditioned_queries=0, ood_mc_routes=0,
            inference_seconds=0., core_cpu_seconds=0., decision_streets=[0]*4,
            model_load_seconds=LOAD_SECONDS)

    def choose_action(self, obs, memory):
        started = process_time()
        result = super().choose_action(obs, memory)
        ACTIVE['core_cpu_seconds'] += process_time() - started
        ACTIVE['decision_streets'][int(obs.street)] += 1
        return result

    def on_hand_end(self, result, memory):
        super().on_hand_end(result, memory)
        if memory['hands_played'] == memory['config'].num_hands:
            report = {**ACTIVE, 'core_wall_seconds':memory['compute_seconds'],
                      'decisions':memory['decisions'], 'configured_samples':self.settings.samples,
                      'instrumentation':'counters + process_time around decision; unchanged wall pacing can react to overhead'}
            print('BATCH03_METRICS '+json.dumps(report),file=sys.stderr,flush=True)
