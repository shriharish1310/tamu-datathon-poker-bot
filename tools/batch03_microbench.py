"""Identical fixed work across platforms, without wall-clock sample pacing."""
import json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evaluator import warmup
from range_equity import Rollouts
from preflop_model import features,predict
from tools.adversarial_batch import save

def main():
    warmup();model=json.loads((ROOT/'experiments/batch03_preflop_weights.json').read_text())
    rng=random.Random('b03-micro-only');states=[rng.sample(range(36),10) for _ in range(400)]
    rows=[]
    for repeat in range(3):
        order=['model',0,1,2,3]
        if repeat%2:order.reverse()
        for mode in order:
            checksum=0.;cpu=time.process_time();wall=time.perf_counter()
            for i,cards in enumerate(states):
                if mode=='model':checksum+=predict(features(cards[:5]),model)
                else:
                    n=(24,32,40,64)[mode]
                    batch=Rollouts(cards[:5],cards[5:5+(0,3,4,5)[mode]],19317+i);batch.extend(n)
                    checksum+=batch.estimates(range_mix=.65 if i%2 else 0,range_power=3)[0].equity
            rows.append(dict(repeat=repeat,mode=mode,states=len(states),samples=0 if mode=='model' else n*len(states),
                        wall_seconds=time.perf_counter()-wall,cpu_seconds=time.process_time()-cpu,checksum=checksum))
    save(ROOT/'reports/batch03/microbench.json',rows)
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
