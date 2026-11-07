from pathlib import Path
from dataclasses import replace
import json
import pytest
from game import Game,make_deal,AgentConfig,Action
from batch02_policy import ResearchPolicy,Settings,public_game

MODEL=Path(__file__).resolve().parents[1]/'experiments/batch02_action_model.json'


@pytest.mark.parametrize('settings',[Settings('A',alpha=.5,shrink=64),Settings('B',action_values=True)])
def test_research_policy_legality_and_public_reconstruction(settings):
    agent=ResearchPolicy(settings,MODEL);mem={};agent.new_half(AgentConfig(num_hands=30),mem)
    for i in range(30):
        g=Game(make_deal('batch02-unit',i),i%2,i)
        while not g.is_terminal:
            seat=g.to_act;obs=g.observation(seat)
            replica=public_game(obs)
            # Sizes, street and stacks agree regardless of invented hidden cards.
            test=replica.observation(0)
            for key in ('pot','street','to_call','my_stack','opp_stack','raise_to','legal_actions'):
                assert getattr(test,key)==getattr(obs,key)
            action=agent.choose_action(obs,mem)
            assert action in obs.legal_actions
            g.apply(action)
        agent.on_hand_end(g.hand_result(0),mem)
    assert mem['research']['min_ess_fraction']>=settings.ess_floor


def test_board_texture_and_model_uses_only_visible_state():
    from action_model import texture,ActionModel,context
    assert texture((0,4,9))==1
    assert texture((0,1,4))==3
    model=ActionModel(MODEL)
    for q in (0,.5,1):
        p=model.probabilities(context(1,(0,4,9),1,.25,2),q)
        assert sum(p)==pytest.approx(1)
        assert all(0<x<1 for x in p)
