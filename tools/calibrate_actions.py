"""Fit action likelihoods using Batch01 development logs, including folded cards."""
import json
from collections import defaultdict
from math import log
from pathlib import Path
from random import Random
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from action_model import ActionModel,context,keys
from game import Game,Action,make_deal
from evaluator import warmup
from range_equity import visible_strength


def main():
    start=perf_counter();warmup()
    counts={name:defaultdict(lambda:[0]*4) for name in ('general','broad','fine')}
    cases=[];ntrain=0
    for path in sorted((ROOT/'reports/adversarial-batch-01/http').glob('*.json')):
        if path.name.count('.')!=1:continue
        data=json.loads(path.read_text());seed=data['match_seed']
        for half in (1,2):
            hero=half-1;opp=1-hero;raises=[2.]*4;passive=[6.]*4
            for hand in data['logs'][f'half{half}']:
                idx=hand['deal_index'];deal=make_deal(seed,idx);g=Game(deal,idx%2,idx)
                for record in hand['actions']:
                    action=Action[record['action']]
                    if g.to_act==opp:
                        obs=g.observation(opp);s=int(obs.street)
                        aggression=raises[s]/(raises[s]+passive[s])
                        previous=[e for e in obs.action_history if not e.is_me and e.street==obs.street
                                  and e.action in (Action.RAISE_HALF,Action.RAISE_POT)]
                        facing=int(previous[-1].action)-1 if previous and obs.to_call else 0
                        ctx=context(s,obs.board,obs.raises_this_street,aggression,facing)
                        actual=visible_strength(obs.hole_cards,obs.board)
                        # Rank relative to the observer's legal opponent space.
                        unseen=[c for c in range(36) if c not in deal.hole_cards[hero]+obs.board]
                        rng=Random(f'calibration:{path.stem}:{half}:{idx}:{len(g.history)}')
                        scores=[visible_strength(tuple(rng.sample(unseen,5)),obs.board) for _ in range(24)]
                        q=sum((v<actual)+.5*(v==actual) for v in scores)/len(scores)
                        if seed.endswith('01'):
                            for name,k in zip(('general','broad','fine'),keys(ctx,q)):counts[name][k][int(action)]+=1
                            ntrain+=1
                        else:cases.append((ctx,q,int(action),tuple(int(a) for a in obs.legal_actions)))
                        (raises if action in (Action.RAISE_HALF,Action.RAISE_POT) else passive)[s]+=1
                    g.apply(action)
    target=ROOT/'experiments/batch02_action_model.json'
    target.write_text(json.dumps({**{k:dict(v) for k,v in counts.items()},'train_decisions':ntrain,
        'training_seed':'adv-dev-http-01','calibration_check_seed':'adv-dev-http-02',
        'selection_bias':'All simulated decisions including folds; no showdown filtering. Occupancy is champion versus six development opponents.'},indent=2)+'\n')
    model=ActionModel(target);results={}
    for shrink in (16,32,64):
        loss=baseline=0.0
        for ctx,q,action,legal in cases:
            p=model.probabilities(ctx,q,shrink);den=sum(p[a] for a in legal)
            loss-=log(max(1e-12,p[action]/den))
            k=keys(ctx,q)[0];g=model.data['general'].get(k,[1]*4)
            baseline-=log((g[action]+1)/sum(g[a]+1 for a in legal))
        results[str(shrink)]={'log_loss':loss/len(cases),'context_only_log_loss':baseline/len(cases)}
    report={'train_decisions':ntrain,'check_decisions':len(cases),'results':results,'seconds':perf_counter()-start,
            'heldout_opponent_configs_used':False,'final_holdout_used':False}
    (ROOT/'reports/batch02').mkdir(parents=True,exist_ok=True)
    (ROOT/'reports/batch02/calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
