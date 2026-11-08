"""Bounded CPU feasibility pilot; no policy promotion or tournament holdout use.

Official Monte Carlo labels estimate equity against uniform legal holdings.
This model does not replace action-conditioned range equity. Pure-Python
inference timing includes feature extraction and is compared with simulation.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import json,math,random,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evaluator import warmup,get_table
from equity import estimate_equity,_score_masks,_pair_masks,_triple_masks
from range_equity import Rollouts


def features(hole,board):
    street={0:0,3:1,4:2,5:3}[len(board)]
    hr=[0]*9;br=[0]*9;hs=[0]*4;bs=[0]*4;aces=[0]*4
    for c in hole:hr[c>>2]+=1;hs[c&3]+=1;aces[c&3]|=int(c>>2==8)
    for c in board:br[c>>2]+=1;bs[c&3]+=1
    suits=sorted(zip(bs,hs,aces),reverse=True)
    score=(_score_masks(_pair_masks(tuple(1<<c for c in hole)),
                        _triple_masks(tuple(1<<c for c in board)),get_table())/(1<<24) if board else 0)
    return [float(street==s) for s in range(4)]+[x/5 for x in hr+br]+[
        v/d for b,h,a in suits for v,d in ((b,5),(h,5),(a,1))]+[score,
        sum(c>=2 for c in hr)/2,max(hs)/5,sum(bool(hr[r] and hr[r+1]) for r in range(8))/8]


def predict(x,weights):
    hidden=[max(0,b+sum(v*w for v,w in zip(x,col))) for b,col in zip(weights['b1'],weights['w1'])]
    return max(0,min(1,weights['b2']+sum(v*w for v,w in zip(hidden,weights['w2']))))


def main():
    import numpy as np
    from sklearn.neural_network import MLPRegressor
    folder=ROOT/'reports/batch02/equity-pilot';folder.mkdir(parents=True,exist_ok=True)
    started=perf_counter();warmup()
    from tools.experiment_grid import match
    from opponent_policy import Opponent,OpponentConfig
    from game import make_deal
    import strategy as champion
    cfg=next(c for c in json.loads((ROOT/'reports/adversarial-batch-01/selected.json').read_text()) if c['name']=='range_aware_2')
    timed=perf_counter()
    sim=match(champion,Opponent(OpponentConfig(**cfg)),[make_deal('b02-throughput-only',i) for i in range(300)])
    elapsed=perf_counter()-timed
    throughput={'played_hands':600,'seconds':elapsed,'hands_per_second':600/elapsed,
                'decisions_per_second':sum(sum(h['decisions']) for h in sim['halves'])/elapsed,
                'scope':'Direct official game, champion vs frozen range-aware configuration; excludes HTTP and process startup.'}
    generation=perf_counter();rows=[];seen=set()
    for split,n,samples in [('train',4000,96),('check',1000,512)]:
        rng=random.Random('b02-equity-pilot-'+split)
        for i in range(n):
            if perf_counter()-started>480:raise RuntimeError('Eight-minute pilot budget exhausted')
            while True:
                cards=rng.sample(range(36),10);hole=tuple(sorted(cards[:5]));board=tuple(cards[5:5+(0,3,4,5)[i%4]])
                key=(hole,tuple(sorted(board)))
                if key not in seen:break
            seen.add(key)
            est=estimate_equity(hole,board,samples=samples,seed=rng.randrange(2**32))
            rows.append({'split':split,'hole':hole,'board':board,'x':features(hole,board),
                         'label':est.equity,'label_stderr':est.stderr,'samples':samples})
        print('LABELS',split,n,'seconds',round(perf_counter()-generation,2),flush=True)
        (folder/'labels-checkpoint.json').write_text(json.dumps(rows)+'\n')
    label_seconds=perf_counter()-generation
    (folder/'labels.json').write_text(json.dumps(rows)+'\n')
    train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='check']
    model=MLPRegressor(hidden_layer_sizes=(32,),activation='relu',solver='adam',alpha=.01,
        learning_rate_init=.003,max_iter=120,early_stopping=True,n_iter_no_change=10,random_state=871)
    fit=perf_counter();model.fit(np.array([r['x'] for r in train]),[r['label'] for r in train]);fit_seconds=perf_counter()-fit
    weights={'w1':model.coefs_[0].T.tolist(),'b1':model.intercepts_[0].tolist(),
             'w2':model.coefs_[1][:,0].tolist(),'b2':float(model.intercepts_[1][0])}
    (folder/'model.json').write_text(json.dumps(weights)+'\n')
    # Verify exported scalar inference against sklearn before speed comparisons.
    check=np.clip(model.predict(np.array([r['x'] for r in test])),0,1)
    scalar=np.array([predict(r['x'],weights) for r in test]);assert np.max(abs(check-scalar))<1e-10
    start=perf_counter();pred=[predict(features(r['hole'],r['board']),weights) for r in test]
    inference=perf_counter()-start
    start=perf_counter();mc=[]
    for i,r in enumerate(test):
        batch=Rollouts(r['hole'],r['board'],9821+i)
        batch.extend((24,32,40,64)[i%4])
        mc.append(batch.estimates()[0].equity)
    simulation=perf_counter()-start;labels=np.array([r['label'] for r in test])
    def metrics(p):
        p=np.array(p);bins=[]
        bins_index=np.minimum(9,(p*10).astype(int))
        for b in range(10):
            lo=b/10
            ids=bins_index==b
            if ids.sum():bins.append({'lo':float(lo),'n':int(ids.sum()),'prediction':float(p[ids].mean()),'label':float(labels[ids].mean())})
        assert sum(b['n'] for b in bins)==len(p)
        return {'rmse':float(np.sqrt(np.mean((p-labels)**2))),'mae':float(np.mean(abs(p-labels))),
                'bias':float(np.mean(p-labels)),'calibration_bins':bins}
    by_street={}
    for street in range(4):
        ids=np.arange(len(test))%4==street
        by_street[str(street)]={'n':int(ids.sum()),'model_rmse':float(np.sqrt(np.mean((np.array(pred)[ids]-labels[ids])**2))),
                              'simulation_rmse':float(np.sqrt(np.mean((np.array(mc)[ids]-labels[ids])**2)))}
    report={'scope':'Uniform-opponent equity feasibility only; no match-performance claim',
        'simulator_throughput':throughput,'train_states':4000,'check_states':1000,'train_samples':96,'check_samples':512,
        'label_seconds':label_seconds,'label_rollouts_per_second':(4000*96+1000*512)/label_seconds,
        'fit_seconds':fit_seconds,'iterations':model.n_iter_,'export_bytes':(folder/'model.json').stat().st_size,
        'scalar_feature_and_inference_us':inference*1000,'simulation_us':simulation*1000,
        'speed_ratio':simulation/inference,'model':metrics(pred),'simulation':metrics(mc),'by_street':by_street,
        'mean_check_label_stderr':sum(r['label_stderr'] for r in test)/len(test),
        'total_seconds':perf_counter()-started,'holdouts_used':False,'expensive_training_launched':False,
        'next_gate':'No deployment without matched official match tests and range-conditioning compatibility.'}
    (folder/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
