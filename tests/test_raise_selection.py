from dataclasses import replace
import numpy as np
import agent
from game import Action,AgentConfig,Game,Street,make_deal


def test_best_qualifying_raise_is_not_charged_a_second_margin(monkeypatch):
    memory={};agent.new_half(AgentConfig(),memory)
    obs=Game(make_deal('raise-margin',0),0).observation(0)
    obs=replace(obs,street=Street.RIVER,pot=20,to_call=0,my_bet=0,opp_bet=0,
                my_stack=15,opp_stack=15,is_button=True,
                legal_actions=(Action.CHECK_CALL,Action.RAISE_HALF,Action.RAISE_POT),
                raise_to={Action.RAISE_HALF:10,Action.RAISE_POT:15})
    # Equity .525: checking is worth 10.5, half-pot 11.0, capped pot 11.25.
    # Both raises clear the .36 margin versus checking; pot has greater value.
    outcomes=np.array([1.]*52+[.5]+[0.]*47)
    monkeypatch.setattr(agent,'_rates',lambda *args:np.array([0.,1.,0.]))
    monkeypatch.setattr(agent,'_simulation',lambda *args:dict(scores=np.zeros((100,4)),outcomes=outcomes))
    monkeypatch.setattr(agent,'_range_weights',lambda *args:(np.full(100,.01),np.zeros(100)))
    assert agent.choose_action(obs,memory)==Action.RAISE_POT
    assert memory['fallback_count']==0
