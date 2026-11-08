"""Exact policy traces conditional on identical external clock inputs.

Run in fresh official-image processes. This is deliberately NOT a timing run.
Natural wall clocks are nondeterministic inputs to champion's pacing; testing
identical observations alone would not establish policy equivalence.
"""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'/app')
import strategy,advanced_policy,range_equity
from game import AgentConfig,Observation,HandResult,Action
from evaluator import warmup

def digest(value):
    return hashlib.sha256(repr(value).encode()).hexdigest()

def run(mode):
    warmup();memory={};records=[];estimates=[]
    original=range_equity.Rollouts.estimates
    def capture(self,**kwargs):
        result=original(self,**kwargs)
        estimates.append((kwargs,tuple((e.equity,e.stderr,e.samples,e.effective_samples,e.current_category) for e in result)))
        return result
    range_equity.Rollouts.estimates=capture
    # The two timer reads have identical values, so the tested input budget is
    # not accidentally perturbed by test instrumentation or CPU scheduling.
    advanced_policy.perf_counter=lambda:0.
    trace=json.loads(gzip.decompress(Path('/research/observations.json.gz').read_bytes()))
    index=0
    for path,body in trace['requests']:
        if path=='/new-half':strategy.new_half(AgentConfig.from_dict(body['config']),memory);continue
        for result in body.get('hand_results',body.get('results',[])):
            strategy.on_hand_end(HandResult.from_dict(result),memory)
        if path!='/act':continue
        obs=Observation.from_dict(body['observation']);allowance=memory['config'].time_bank_seconds*.25
        boundary=allowance*max(.1,(obs.hand_index+1)/memory['config'].num_hands)
        if mode=='full':budget=0.
        elif mode=='half':budget=100.
        else:budget=boundary+(0.,-1e-12,1e-12)[index%3]
        memory['compute_seconds']=budget;estimates.clear()
        action=strategy.choose_action(obs,memory)
        if action not in obs.legal_actions:raise RuntimeError('Illegal replay action')
        sizes={a.name:v for a,v in obs.raise_to.items()}
        amount=(obs.raise_to[action]-obs.my_bet if action in (Action.RAISE_HALF,Action.RAISE_POT)
                else min(obs.to_call,obs.my_stack) if action==Action.CHECK_CALL else 0)
        # Full cached payoff stream, feature state, weighting queries and RNG
        # state detect differences that action agreement alone would miss.
        states=[]
        for key,value in memory['cache'].items():
            states.append((key,tuple(value.payoffs),value.rng.getstate(),tuple(value.strengths),
                           value.total,value.squares,tuple(value.percentiles or ())))
        records.append(dict(index=index,hand=obs.hand_index,street=int(obs.street),clock_budget=budget,
            action=action.name,bet_amount=amount,legal_raise_to=sizes,equity_digest=digest(estimates),
            rollout_and_rng_digest=digest(states),actual_total_samples=memory['experiment']['sampled_trials']))
        index+=1
    return dict(mode=mode,decisions=index,records=records,
        scope='Exact equivalence conditional on identical recorded observations and clock-budget inputs. Not a claim of identical natural-clock trajectories.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['full','half','boundary'],required=True);p.add_argument('--output',required=True)
    args=p.parse_args();Path(args.output).write_text(json.dumps(run(args.mode),indent=2)+'\n')
