"""Independent A (calibrated ranges) and B (one-response action values).

B uses a conservative continuation proxy, not a full-game solution. Random
opponent/runout samples are shared across alternatives. No simulation seed or
hidden opponent cards from the real deal enter this module.
"""
from dataclasses import dataclass
import json
from math import sqrt
from pathlib import Path
import sys
from time import perf_counter

import baseline_strategy as base
from advanced_policy import Policy,range_parameters
from action_model import ActionModel,context
from game import Action,Game,Deal
from policy_config import PolicyConfig
from range_equity import Rollouts,summarize_weighted


@dataclass(frozen=True)
class Settings:
    name:str
    alpha:float=0
    shrink:int=32
    action_values:bool=False
    uncertainty:float=1.0
    risk_penalty:float=.02
    ess_floor:float=.45


def opponent_context(obs,memory,prospective=None):
    s=int(obs.street);a=memory['raises'][s]/(memory['raises'][s]+memory['passive'][s])
    if prospective is not None:
        return context(s,obs.board,obs.raises_this_street+int(prospective in base.RAISES),a,
                       int(prospective)-1 if prospective in base.RAISES else 0)
    history=list(obs.action_history)
    indices=[i for i,e in enumerate(history) if not e.is_me and e.street==obs.street and e.action in base.RAISES]
    if not indices:return None,None
    i=indices[-1];event=history[i];prior=history[:i]
    # Match calibration's pre-action tendency; exclude the action being scored.
    a=max(0,memory['raises'][s]-1)/max(1,memory['raises'][s]+memory['passive'][s]-1)
    count=sum(e.street==obs.street and e.action in base.RAISES for e in prior)
    previous=[e for e in prior if e.is_me and e.street==obs.street and e.action in base.RAISES]
    facing=int(previous[-1].action)-1 if previous else 0
    return context(s,obs.board,count,a,facing),int(event.action)


class CalibratedRollouts(Rollouts):
    def current_weights(self,mix,power):
        # Materialize only visible opponent strengths, never sampled runouts.
        super().estimates(range_mix=.001)
        original=[(1-mix+mix*q)**power for q in self.percentiles]
        ctx,action=opponent_context(self.obs,self.memory)
        if not self.cfg.alpha or ctx is None:return original
        raw=[self.model.probabilities(ctx,q,self.cfg.shrink)[action] for q in self.percentiles]
        so=sum(original)/len(original);sr=sum(raw)/len(raw)
        w=[(1-self.cfg.alpha)*x/so+self.cfg.alpha*y/sr for x,y in zip(original,raw)]
        n=len(w);ess=sum(w)**2/sum(x*x for x in w)
        while ess<self.cfg.ess_floor*n:
            w=[.5+.5*x for x in w];ess=sum(w)**2/sum(x*x for x in w)
            self.memory['research']['ess_shrink_events']+=1
        d=self.memory['research'];d['weighted_queries']+=1
        d['min_ess_fraction']=min(d['min_ess_fraction'],ess/n)
        return w

    def estimates(self,*,range_mix=0,range_power=2,caller_power=0,fold_rate=.2):
        if not self.cfg.alpha or opponent_context(self.obs,self.memory)[0] is None:
            return super().estimates(range_mix=range_mix,range_power=range_power,caller_power=caller_power,fold_rate=fold_rate)
        value=summarize_weighted(self.payoffs,self.current_weights(range_mix,range_power),self.category)
        return (value,)*3


def public_game(obs):
    """Rebuild public betting state with arbitrary legal hidden cards.

    Dummy cards are never evaluated for action values. The official Game is
    used only for legal sizes, stacks, response availability and street closure.
    """
    unseen=[c for c in range(36) if c not in obs.hole_cards+obs.board]
    board=obs.board+tuple(unseen[5:10-len(obs.board)])
    g=Game(Deal((obs.hole_cards,tuple(unseen[:5])),board),0 if obs.is_button else 1,obs.hand_index)
    for e in obs.action_history:g.apply(e.action)
    assert g.to_act==0 and g.pot==obs.pot and g.stacks[0]==obs.my_stack
    return g


class ResearchPolicy(Policy):
    def __init__(self,cfg,model_path=None):
        super().__init__(PolicyConfig(name=cfg.name,range_blend=1.3,compute_fraction=.25))
        self.cfg=cfg;self.model=ActionModel(model_path or Path(__file__).with_name('batch02_action_model.json'))

    def new_half(self,config,memory):
        super().new_half(config,memory)
        memory['research']=dict(weighted_queries=0,min_ess_fraction=1.0,ess_shrink_events=0,
            action_value_decisions=0,changed_decisions=0,pot_choices=0,target_flop_decisions=0,
            action_value_seconds=0.,action_budget_skips=0)

    def on_hand_end(self,result,memory):
        super().on_hand_end(result,memory)
        if result.hand_index==memory['config'].num_hands-1:
            print('RESEARCH_METRICS '+json.dumps(memory['research']),file=sys.stderr,flush=True)

    def decide(self,obs,memory):
        base._observe(obs,memory)
        if len(obs.legal_actions)==1:return obs.legal_actions[0]
        key=(obs.hole_cards,obs.board);cached=memory['cache'].get(key)
        if cached is None:
            n=self.settings.samples[int(obs.street)]
            pace=memory['config'].time_bank_seconds*.25*max(.1,(obs.hand_index+1)/memory['config'].num_hands)
            if memory['compute_seconds']>pace:n=max(8,n//2)
            cached=CalibratedRollouts(*key,base._seed(obs));cached.extend(n)
            memory['cache'][key]=cached
        cached.obs=obs;cached.memory=memory;cached.cfg=self.cfg;cached.model=self.model
        choice=super().decide(obs,memory)
        if int(obs.street)==1 and not obs.is_button and obs.to_call and obs.pot<10*obs.big_blind:
            memory['research']['target_flop_decisions']+=1
        if not self.cfg.action_values:return choice
        # Reserve a bounded share for action comparison; deviations are logged,
        # and the champion policy is an explicit budgeted branch, not a fallback.
        budget=.65*max(.1,(obs.hand_index+1)/memory['config'].num_hands)
        if memory['research']['action_value_seconds']>budget:
            memory['research']['action_budget_skips']+=1
            return choice
        started=perf_counter();answer=self.action_choice(obs,memory,cached)
        memory['research']['action_value_seconds']+=perf_counter()-started
        memory['research']['action_value_decisions']+=1
        memory['research']['changed_decisions']+=answer!=choice
        memory['research']['pot_choices']+=answer==Action.RAISE_POT
        return answer

    def action_choice(self,obs,memory,batch):
        s=int(obs.street);aggression=memory['raises'][s]/(memory['raises'][s]+memory['passive'][s])
        mix,power=range_parameters(obs,aggression,1.3)
        weights=batch.current_weights(mix,power);total=sum(weights)
        g=public_game(obs);values={Action.FOLD:0.0} if Action.FOLD in obs.legal_actions else {}
        for action in obs.legal_actions:
            if action==Action.FOLD:continue
            branch=g.clone();r=min(obs.to_call,obs.my_stack) if action==Action.CHECK_CALL else obs.raise_to[action]-obs.my_bet
            branch.apply(action)
            future=(.035,.025,.012,0)[s]*(1.25 if not obs.is_button else .75)
            if branch.is_terminal or branch.street!=obs.street:
                if min(obs.my_stack-r,obs.opp_stack)==0:future=0
                outcomes=[(p-future)*(obs.pot+r)-r for p in batch.payoffs]
            else:
                assert branch.to_act==1
                response_obs=branch.observation(1);legal=response_obs.legal_actions
                ctx=opponent_context(obs,memory,action)
                probs=[]
                for q in batch.percentiles:
                    p=self.model.probabilities(ctx,q,self.cfg.shrink)
                    den=sum(p[int(a)] for a in legal)
                    probs.append([p[j]/den if Action(j) in legal else 0.0 for j in range(4)])
                outcomes=[0.0]*len(weights)
                for response in legal:
                    j=int(response)
                    if response==Action.FOLD:pay=[float(obs.pot)]*len(weights)
                    else:
                        add=min(response_obs.to_call,response_obs.my_stack) if response==Action.CHECK_CALL else response_obs.raise_to[response]-response_obs.my_bet
                        pot=obs.pot+r+add
                        extra=0 if response==Action.CHECK_CALL else min(obs.my_stack-r,response_obs.my_bet+add-(obs.my_bet+r))
                        w=[x*p[j] for x,p in zip(weights,probs)]
                        if not sum(w):continue
                        est=summarize_weighted(batch.payoffs,[max(1e-12,x) for x in w])
                        f=0 if min(obs.my_stack-r-extra,obs.opp_stack-add)==0 else future
                        continue_value=(est.equity-self.cfg.uncertainty*est.stderr-f)*(pot+extra)-extra
                        if response in base.RAISES and continue_value<0:pay=[-float(r)]*len(weights)
                        else:pay=[(p-f)*(pot+extra)-r-extra for p in batch.payoffs]
                    for i,p in enumerate(probs):outcomes[i]+=p[j]*pay[i]
            mean=sum(w*x for w,x in zip(weights,outcomes))/total
            ess=total*total/sum(w*w for w in weights)
            var=sum(w*(x-mean)**2 for w,x in zip(weights,outcomes))/total
            lower=mean-self.cfg.uncertainty*sqrt(var/max(1,ess-1))
            if action in base.RAISES:lower-=self.cfg.risk_penalty*r
            values[action]=lower
        return max(values,key=lambda a:(values[a],-int(a)))
