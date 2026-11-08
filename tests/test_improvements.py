"""Behavioral checks for cautious interpretation of checks and slow plays."""
from dataclasses import replace
import numpy as np
import agent
from game import Action, AgentConfig, Game, ObservedAction, Street, make_deal


def test_slow_play_evidence_reduces_confidence_in_weak_checks():
    memory = {}
    agent.new_half(AgentConfig(),memory)
    prior = agent._check_information(memory,Street.RIVER)
    assert 0 < prior < 1
    memory['check_evidence'][3] = [25,100]
    weak = agent._check_information(memory,Street.RIVER)
    memory['check_evidence'][3] = [80,100]
    strong = agent._check_information(memory,Street.RIVER)
    assert 0 <= strong < prior < weak <= 1


def test_trapper_keeps_more_strong_hands_after_checking():
    memory = {}
    agent.new_half(AgentConfig(),memory)
    memory['counts'][3,0,1] = 60
    memory['counts'][3,0,2] = 40
    base = Game(make_deal('check',0),0).observation(0)
    obs = replace(base,street=Street.RIVER,action_history=(ObservedAction(Street.RIVER,False,Action.CHECK_CALL,0,0),))
    scores = np.tile(np.arange(100,dtype=float)[:,None],(1,4))
    memory['check_evidence'][3] = [25,100]
    weak,_ = agent._range_weights(obs,memory,scores)
    memory['check_evidence'][3] = [80,100]
    trapper,_ = agent._range_weights(obs,memory,scores)
    assert trapper[-20:].sum() > weak[-20:].sum()
    assert np.isclose(trapper.sum(),1) and np.isclose(weak.sum(),1)


def test_learning_requires_revealed_cards_and_matching_hand():
    memory={}
    agent.new_half(AgentConfig(),memory)
    game=Game(make_deal('learning',0),0,0)
    while not game.is_terminal:
        if game.to_act == 0:
            obs=game.observation(0)
            memory['last_obs']=obs
            if obs.board:
                agent._simulation(obs,memory)
        game.apply(Action.CHECK_CALL)
    result=game.hand_result(0)
    agent._learn_checks(replace(result,opp_hole=None),memory)
    assert not memory['check_evidence'].any()
    agent._learn_checks(replace(result,hand_index=99),memory)
    assert not memory['check_evidence'].any()
    agent._learn_checks(result,memory)
    assert memory['check_evidence'][:,1].sum() > 0
    assert np.all(memory['check_evidence'][:,0] <= memory['check_evidence'][:,1])
    assert np.all(memory['check_evidence'][:,1] <= 1)


def test_check_learning_resets_each_half():
    memory={}
    agent.new_half(AgentConfig(),memory)
    memory['check_evidence'][:]=99
    agent.new_half(AgentConfig(),memory)
    assert not memory['check_evidence'].any()
