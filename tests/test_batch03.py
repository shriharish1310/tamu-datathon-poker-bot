"""Scientific compatibility checks for the preflop-only replacement."""
from itertools import permutations
from pathlib import Path
import asyncio
import pytest
import advanced_policy
import batch03_policy as research
from game import AgentConfig
from preflop_model import canonical,features
from range_equity import Rollouts

MODEL=Path(__file__).resolve().parents[1]/'experiments/batch03_preflop_weights.json'


def test_readonly_audit_reads_wrapped_strategy_memory(monkeypatch):
    import batch03_audit_server as audit
    from reliability import CORE_KEY
    monkeypatch.setattr(audit.agent,'MEMORY',{CORE_KEY:{'compute_seconds':1.25,'decisions':7,
        'experiment':{'sampled_trials':24}}})
    result=asyncio.run(audit.metrics())
    assert result['core_wall_seconds']==1.25 and result['decisions']==7
    assert result['experiment']['sampled_trials']==24


def test_suit_grouping_and_feature_invariance():
    hand=(0,4,9,22,35)
    for p in permutations(range(4)):
        renamed=tuple((c&~3)+p[c&3] for c in hand)
        assert canonical(renamed)==canonical(hand)
        assert features(renamed)==features(hand)
    assert features((0,0,4,8,12)) is None


def test_postflop_and_conditioned_routes_are_original_stream(monkeypatch):
    monkeypatch.setattr(advanced_policy,'Rollouts',Rollouts)
    policy=research.ObservedPolicy(True,MODEL);memory={};policy.new_half(AgentConfig(num_hands=2),memory)
    for board in ((),(1,5,10),(1,5,10,23),(1,5,10,23,34)):
        a=Rollouts((0,4,9,22,35),board,489);a.extend(24)
        b=research.HybridRollouts((0,4,9,22,35),board,489);b.extend(24)
        if not board:
            b.estimates(range_mix=0.)
            assert len(b.payoffs)==0
        for mix in (.35,.9):
            assert b.estimates(range_mix=mix,range_power=3.)==a.estimates(range_mix=mix,range_power=3.)
        assert b.payoffs==a.payoffs
    assert memory['batch03']['model_states']==1
    assert memory['batch03']['ood_mc_routes']==0


def test_ood_route_is_bounded_and_observable(monkeypatch):
    monkeypatch.setattr(advanced_policy,'Rollouts',Rollouts)
    policy=research.ObservedPolicy(True,MODEL);memory={};policy.new_half(AgentConfig(num_hands=1),memory)
    monkeypatch.setitem(research.MODEL,'support',[0.,0.])
    a=research.HybridRollouts((0,4,9,22,35),(),101);a.extend(12)
    answer=a.estimates()[0]
    assert answer.samples==12 and len(a.payoffs)==12
    assert memory['batch03']['ood_mc_routes']==1
