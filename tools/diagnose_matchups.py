"""Describe official logged outcomes without treating actions as independent.

Primary slices partition hands by last betting street, seat, largest opponent
raise and final pot. These are outcome associations, not causal decision EV.
Decision-context slices deduplicate a hand within each group but overlap across
groups. Small groups remain visible and are excluded from ranked findings.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game import BIG_BLIND, Action, Game, make_deal


def bucket(bb):
    return '<10BB' if bb<10 else '10-30BB' if bb<30 else '>=30BB'


def summarize(groups):
    out=[]
    for key,records in groups.items():
        deals={(r['seed'],r['deal']) for r in records}
        seeds={r['seed'] for r in records}
        total=sum(r['net'] for r in records)
        out.append({'group':list(key),'hands':len(records),'distinct_paired_deals':len(deals),
                    'seeds':len(seeds),'net_bb':total/BIG_BLIND,
                    'mean_bb_per_hand':total/(BIG_BLIND*len(records)),
                    'gross_loss_bb':-sum(min(0,r['net']) for r in records)/BIG_BLIND,
                    'losing_hands':sum(r['net']<0 for r in records),
                    'sufficient_for_description':len(records)>=200 and len(deals)>=100 and len(seeds)>=2})
    return sorted(out,key=lambda r:r['net_bb'])


def analyze(folder, leaderboard):
    groups=defaultdict(list);contexts=defaultdict(list);all_nets=defaultdict(int)
    for row in leaderboard['matches']:
        path=folder/'http'/Path(row['report']).name
        report=json.loads(path.read_text())
        seed=report['match_seed'];opponent=row['opponent']
        for half in (1,2):
            seat=half-1
            for hand in report['logs'][f'half{half}']:
                deal=hand['deal_index'];net=hand['nets'][seat]
                record={'seed':seed,'deal':deal,'net':net}
                position='button' if hand['button_seat']==seat else 'big_blind'
                actions=hand['actions'];last_street=actions[-1]['street'] if actions else 'PREFLOP'
                opp_sizes=[a['action'] for a in actions if a['seat']!=seat and a['action'].startswith('RAISE_')]
                size='pot' if 'RAISE_POT' in opp_sizes else 'half' if opp_sizes else 'none'
                dimensions={'last_betting_street':last_street,'position':position,
                            'largest_opponent_raise':size,'final_pot':bucket(hand['pot']/BIG_BLIND)}
                for dimension,value in dimensions.items():
                    groups[(opponent,dimension,value)].append(record)
                groups[(opponent,'joint',last_street,position,size,bucket(hand['pot']/BIG_BLIND))].append(record)
                all_nets[opponent]+=net
                # Reconstruct public decision contexts and verify the replay;
                # hidden cards never enter a running policy through this tool.
                game=Game(make_deal(seed,deal),hand['button_seat'],deal)
                seen=set()
                for a in actions:
                    assert game.to_act==a['seat'] and game.street.name==a['street']
                    if game.to_act==seat:
                        obs=game.observation(seat)
                        past=[e for e in obs.action_history if not e.is_me and e.street==obs.street
                              and e.action in (Action.RAISE_HALF,Action.RAISE_POT)]
                        facing=('free' if not obs.to_call else past[-1].action.name if past else 'blind_or_call')
                        seen.add((opponent,'decision_context',obs.street.name,position,facing,bucket(obs.pot/BIG_BLIND)))
                    game.apply(Action[a['action']])
                assert game.is_terminal and list(game.result().nets)==hand['nets']
                assert game.result().pot==hand['pot']
                for key in seen: contexts[key].append(record)
    slices=summarize(groups)
    # Each one-dimensional partition must conserve total match chips.
    for opponent,total in all_nets.items():
        for dimension in ('last_betting_street','position','largest_opponent_raise','final_pot'):
            actual=sum(r['net_bb'] for r in slices if r['group'][:2]==[opponent,dimension])*BIG_BLIND
            assert abs(actual-total)<1e-6
    return {'description':'Descriptive development outcomes; no causal EV or subgroup significance claims.',
            'minimum_description_support':{'hands':200,'distinct_paired_deals':100,'seeds':2},
            'partitioned_hand_outcomes':slices,'overlapping_decision_contexts':summarize(contexts),
            'total_net_chips':dict(all_nets)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    leaderboard=json.loads((a.folder/'leaderboard.json').read_text())
    result=analyze(a.folder,leaderboard)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Replayed official hands and verified partition totals:',result['total_net_chips'])


if __name__=='__main__':main()
