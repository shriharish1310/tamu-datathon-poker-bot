"""Recheck speed on fixed pilot data/weights without fitting another model."""
import hashlib,json,math,statistics,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.learned_equity_pilot import features,predict
from range_equity import Rollouts
from evaluator import warmup


def main():
    folder=ROOT/'reports/batch02/equity-pilot';warmup()
    test=[r for r in json.loads((folder/'labels.json').read_text()) if r['split']=='check']
    weights=json.loads((folder/'model.json').read_text());timings=[];predictions={}
    for repeat in range(3):
        timing={}
        for method in (('model','simulation') if repeat%2==0 else ('simulation','model')):
            start=perf_counter();p=[]
            for i,r in enumerate(test):
                if method=='model':p.append(predict(features(r['hole'],r['board']),weights))
                else:
                    batch=Rollouts(r['hole'],r['board'],9821+i);batch.extend((24,32,40,64)[i%4]);p.append(batch.estimates()[0].equity)
            timing[method+'_us']=(perf_counter()-start)*1e6/len(test)
            if method in predictions:assert p==predictions[method]
            predictions[method]=p
        timings.append(timing)
    path=folder/'summary.json';report=json.loads(path.read_text())
    report['inference_repeats']=timings
    report['scalar_feature_and_inference_us']=statistics.median(r['model_us'] for r in timings)
    report['simulation_us']=statistics.median(r['simulation_us'] for r in timings)
    report['speed_ratio']=report['simulation_us']/report['scalar_feature_and_inference_us']
    report['model_config']={'features':len(test[0]['x']),'hidden_units':32,'activation':'ReLU',
        'optimizer':'Adam','learning_rate':.003,'alpha':.01,'max_iter':120,'early_stopping':True,'random_state':871}
    # Champion also shrinks equity toward 0.5. Preserve this more relevant
    # uniform-equity control in addition to the unshrunk estimator comparison.
    shrunk=[(p*(24,32,40,64)[i%4]+2)/((24,32,40,64)[i%4]+4) for i,p in enumerate(predictions['simulation'])]
    def rmse(p,indices):
        return math.sqrt(statistics.mean((p[i]-test[i]['label'])**2 for i in indices))
    report['champion_uniform_shrinkage']={'rmse':rmse(shrunk,range(len(test))),
        'by_street':{str(s):rmse(shrunk,range(s,len(test),4)) for s in range(4)},
        'scope':'Uniform equity with champion prior shrinkage at full 24/32/40/64 samples; excludes range conditioning and runtime sample halving.'}
    report['source_hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ('tools/learned_equity_pilot.py','tools/benchmark_equity_checkpoint.py','range_equity.py','equity.py','evaluator.py','game.py')}
    report['checkpoint_hashes']={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('model.json','labels.json')}
    report['timing_note']='Median of three alternating-order passes over identical 1000 states. Model and label bytes unchanged. Separate simulator runs varied from 76 to 123 hands/s on this host.'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'timings':timings,'speed_ratio':report['speed_ratio']},indent=2))

if __name__=='__main__':main()
