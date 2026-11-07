"""Research pool legality, information boundary and reproducibility checks."""
import json
from pathlib import Path

import pytest
from game import Action, AgentConfig, Game, make_deal
from opponent_policy import Opponent, OpponentConfig


@pytest.mark.parametrize('aware',[False,True])
def test_observation_only_opponent_is_legal_and_resets(aware):
    agent=Opponent(OpponentConfig('test','test',range_aware=aware,bluff_rate=.6))
    memory={};agent.new_half(AgentConfig(num_hands=40),memory)
    first=None
    for i in range(40):
        g=Game(make_deal('research-unit',i),i%2,i)
        while not g.is_terminal:
            obs=g.observation(g.to_act)
            action=agent.choose_action(obs,memory)
            assert isinstance(action,Action) and action in obs.legal_actions
            if first is None: first=action
            g.apply(action)
        agent.on_hand_end(g.hand_result(0),memory)
    agent.new_half(AgentConfig(num_hands=40),memory)
    assert memory['elapsed']==0 and memory['cache']=={}
    g=Game(make_deal('research-unit',0),0,0)
    assert agent.choose_action(g.observation(g.to_act),memory)==first


def test_development_and_holdout_configs_disjoint():
    root=Path(__file__).resolve().parents[1]/'experiments'
    dev=json.loads((root/'opponents-development.json').read_text())
    held=json.loads((root/'opponents-heldout.json').read_text())
    assert len(dev)==24 and len(held)==12
    assert {d['name'] for d in dev}.isdisjoint(d['name'] for d in held)
    assert {d['salt'] for d in dev}.isdisjoint(d['salt'] for d in held)
    assert len({d['family'] for d in dev})==6
