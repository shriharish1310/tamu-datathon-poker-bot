"""Bounded canonical-grouped preflop estimator experiment; no held-out opponents."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name] = '1'
import hashlib,json,math,random,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from preflop_model import canonical,features,predict
from range_equity import Rollouts
from evaluator import warmup
from tools.adversarial_batch import save
OUT=ROOT/'reports/batch03/estimator'
RANGES=[(0.,2.),(.35,2.),(.65,2.),(.65,3.),(.9,3.)]


def metrics(pred,rows,range_index=0):
    import numpy as np
    p=np.array(pred);y=np.array([r['labels'][range_index]['equity'] for r in rows]);bins=[]
    for b in range(10):
        ids=np.minimum(9,(p*10).astype(int))==b
        if ids.sum():bins.append(dict(lo=b/10,n=int(ids.sum()),prediction=float(p[ids].mean()),label=float(y[ids].mean())))
    boundaries={}
    for threshold in (.25,.31,.37,.50,.58,.65,.70):
        # Call/value thresholds are diagnostic probes; no outcome-based action labels.
        se=np.array([r['labels'][range_index]['stderr'] for r in rows])
        certain=abs(y-threshold)>1.96*se
        near=abs(y-threshold)<.05
        boundaries[str(threshold)]={'label_certain_n':int(certain.sum()),
            'certain_disagreement_rate':float(np.mean((p[certain]>=threshold)!=(y[certain]>=threshold))) if certain.any() else None,
            'near_n':int(near.sum()),'near_mae':float(np.mean(abs(p[near]-y[near]))) if near.any() else None}
    return dict(n=len(rows),rmse=float(np.sqrt(np.mean((p-y)**2))),mae=float(np.mean(abs(p-y))),
                bias=float(np.mean(p-y)),calibration=bins,boundaries=boundaries)


def main():
    import numpy as np
    from sklearn.neural_network import MLPRegressor
    from sklearn.ensemble import ExtraTreesRegressor
    OUT.mkdir(parents=True,exist_ok=True);started=perf_counter();warmup()
    rng=random.Random('b03-canonical-partition-839');seen=set();rows=[]
    targets=[('train',6000,256),('selection',1000,1024),('test',1000,2048)]
    label_start=perf_counter()
    for split,n,samples in targets:
        for i in range(n):
            if perf_counter()-started>900:raise RuntimeError('15 minute label/fit budget exhausted')
            while True:
                hole=canonical(rng.sample(range(36),5))
                if hole not in seen:break
            seen.add(hole)
            batch=Rollouts(hole,(),rng.randrange(2**32));batch.extend(samples)
            labels=[]
            for mix,power in RANGES:
                e=batch.estimates(range_mix=mix,range_power=power)[0]
                labels.append(dict(equity=e.equity,stderr=e.stderr,ess=e.effective_samples))
            rows.append(dict(split=split,hole=hole,labels=labels,samples=samples))
            if (i+1)%1000==0:print('labels',split,i+1,round(perf_counter()-label_start,2),flush=True)
        save(OUT/'labels.json',rows)
    generation_seconds=perf_counter()-label_start
    train=[r for r in rows if r['split']=='train'];selection=[r for r in rows if r['split']=='selection']
    test=[r for r in rows if r['split']=='test']
    assert len({tuple(r['hole']) for r in rows})==len(rows)
    x=np.array([features(r['hole']) for r in train]);y=[r['labels'][0]['equity'] for r in train]
    models={};selection_reports={}
    for name,estimator in [
        ('MLP32',MLPRegressor(hidden_layer_sizes=(32,),alpha=.03,learning_rate_init=.002,
             max_iter=200,early_stopping=True,n_iter_no_change=15,random_state=3107)),
        ('ExtraTrees12_depth10',ExtraTreesRegressor(n_estimators=12,max_depth=10,min_samples_leaf=5,
             max_features=1.,n_jobs=1,random_state=3107))]:
        start=perf_counter();estimator.fit(x,y);fit_seconds=perf_counter()-start
        if name=='MLP32':
            model=dict(kind='mlp',w1=estimator.coefs_[0].T.tolist(),b1=estimator.intercepts_[0].tolist(),
                       w2=estimator.coefs_[1][:,0].tolist(),b2=float(estimator.intercepts_[1][0]))
        else:
            model=dict(kind='trees',trees=[dict(left=e.tree_.children_left.tolist(),right=e.tree_.children_right.tolist(),
                feature=e.tree_.feature.tolist(),threshold=e.tree_.threshold.tolist(),value=e.tree_.value[:,0,0].tolist()) for e in estimator.estimators_])
        check=np.clip(estimator.predict(np.array([features(r['hole']) for r in selection])),0,1)
        scalar=[predict(features(r['hole']),model) for r in selection]
        assert max(abs(a-b) for a,b in zip(check,scalar))<1e-10
        report=metrics(scalar,selection)
        noise=np.mean([r['labels'][0]['stderr']**2 for r in selection])
        model.update(residual_sigma=max(.025,math.sqrt(max(0,report['rmse']**2-noise))),
                     support=[max(0,min(scalar)-.05),min(1,max(scalar)+.05)],name=name,
                     scope='Uniform legal-opponent preflop equity only; never apply to positive range weights')
        save(OUT/(name+'.json'),model);models[name]=model
        selection_reports[name]={**report,'fit_seconds':fit_seconds,'residual_sigma':model['residual_sigma']}
    winner=min(selection_reports,key=lambda n:selection_reports[n]['rmse'])
    # Selection lock precedes estimator-test metrics. No tuning after this point.
    save(OUT/'selection-lock.json',dict(selected=winner,selection=selection_reports,groups_disjoint=True,
         model_hashes={n:hashlib.sha256((OUT/(n+'.json')).read_bytes()).hexdigest() for n in models}))
    save(ROOT/'experiments/batch03_preflop_weights.json',models[winner])
    predicted={n:[predict(features(r['hole']),m) for r in test] for n,m in models.items()}
    simulation={n:[] for n in (12,24)}
    for i,r in enumerate(test):
        batch=Rollouts(r['hole'],(),99300+i);batch.extend(24)
        # Both sample budgets use the same random prefix; comparisons reuse samples across ranges.
        prefix=Rollouts(r['hole'],(),99300+i);prefix.extend(12)
        for n,obj in ((12,prefix),(24,batch)):
            simulation[n].append([obj.estimates(range_mix=m,range_power=p)[0].equity for m,p in RANGES])
    by_range={}
    for j,(mix,power) in enumerate(RANGES):
        entry={'mix':mix,'power':power,'mean_label_se':float(np.mean([r['labels'][j]['stderr'] for r in test])),
               'mean_label_ess':float(np.mean([r['labels'][j]['ess'] for r in test]))}
        for n in (12,24):entry['MC'+str(n)]=metrics([p[j] for p in simulation[n]],test,j)
        for name in models:
            # Nonuniform route deliberately keeps champion MC24, not the uniform model.
            p=predicted[name] if not mix else [p[j] for p in simulation[24]]
            entry[name+'_hybrid']=metrics(p,test,j)
            entry[name+'_hybrid']['route']='model' if not mix else 'unchanged_MC24'
        by_range[f'{mix}:{power}']=entry
    timings=[]
    for repeat in range(3):
        order=list(models)+['MC24'];order=order if repeat%2==0 else order[::-1]
        for name in order:
            start=perf_counter()
            for i,r in enumerate(test):
                if name=='MC24':
                    b=Rollouts(r['hole'],(),99300+i);b.extend(24);b.estimates()
                else:predict(features(r['hole']),models[name])
            timings.append(dict(repeat=repeat,name=name,microseconds_per_state=(perf_counter()-start)*1e6/len(test)))
    report=dict(selected=winner,selection=selection_reports,by_range=by_range,timings=timings,
        canonical_groups={s:n for s,n,_ in targets},label_seconds=generation_seconds,
        label_rollouts=sum(n*k for _,n,k in targets),total_seconds=perf_counter()-started,
        uncertainty='Monte Carlo label SE is approximate for weighted empirical-rank ratios; excludes heuristic range misspecification.',
        support='Uniform component only. Conditioned test accuracy equals retained MC, not learned range accuracy.',holdouts_used=False)
    save(OUT/'summary.json',report)
    print('SELECTED',winner,'elapsed',report['total_seconds'],flush=True)


if __name__=='__main__':main()
