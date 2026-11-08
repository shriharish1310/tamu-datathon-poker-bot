"""Build a protocol replay from already-consumed official hand logs."""
import gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game,make_deal,AgentConfig,Action

def main():
    source=ROOT/'reports/batch03/runtime/raw_bluffy_1_b03-runtime-13.json'
    report=json.loads(source.read_text());requests=[['/new-half',{'config':AgentConfig(num_hands=1000).to_dict()}]]
    pending=[];decisions=0
    for hand in report['logs']['half1']:
        i=hand['deal_index'];g=Game(make_deal(report['match_seed'],i),hand['button_seat'],i)
        for event in hand['actions']:
            if g.to_act==0:
                requests.append(['/act',{'observation':g.observation(0).to_dict(),'hand_results':pending}])
                pending=[];decisions+=1
            g.apply(Action[event['action']])
        assert g.is_terminal and list(g.result().nets)==hand['nets']
        pending.append(g.hand_result(0).to_dict())
    requests.append(['/hand-end',{'results':pending}])
    payload={'seed':report['match_seed'],'opponent':'bluffy_1','half':1,'decisions':decisions,
             'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'requests':requests}
    path=ROOT/'experiments/batch04_observations.json.gz'
    path.write_bytes(gzip.compress(json.dumps(payload,separators=(',',':')).encode(),mtime=0))
    print('Trace',decisions,'decisions',len(requests),'requests',path.stat().st_size,'bytes')

if __name__=='__main__':main()
