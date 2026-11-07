"""Locked A/B protocol: official HTTP only, matched deals, fresh halves."""
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from batch02_policy import Settings
from tools.adversarial_batch import RUNTIME,FREEZE,save,ENV,FLAGS
from tools.evaluate_suite import read_official
from tools.benchmark_strategy import paired_summary

OUT=ROOT/'reports/batch02'
PROFILES=[Settings('A25s32',alpha=.25,shrink=32),Settings('A50s16',alpha=.5,shrink=16),
          Settings('A50s64',alpha=.5,shrink=64),
          Settings('Bz075',action_values=True,uncertainty=.75,risk_penalty=.01),
          Settings('Bz125',action_values=True,uncertainty=1.25,risk_penalty=.03)]
END=datetime.fromisoformat('2026-11-08T00:50:36+00:00')


def freeze(cfg):
    target=OUT/'packages'/cfg.name;target.mkdir(parents=True,exist_ok=True)
    data={name:(FREEZE/name).read_bytes() for name in RUNTIME}
    data.update({name:(ROOT/name).read_bytes() for name in ('batch02_policy.py','action_model.py')})
    data['batch02_action_model.json']=(ROOT/'experiments/batch02_action_model.json').read_bytes()
    data['strategy.py']=(f'from batch02_policy import ResearchPolicy,Settings\n_policy=ResearchPolicy(Settings(**{asdict(cfg)!r}))\n'
        'new_half=_policy.new_half\nchoose_action=_policy.choose_action\non_hand_end=_policy.on_hand_end\n').encode()
    for name,blob in data.items():
        p=target/name
        if p.exists() and p.read_bytes()!=blob:raise ValueError('Frozen package changed: '+str(p))
        p.write_bytes(blob)
    save(target/'config.json',asdict(cfg));return target


def sha(folder):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}


def init():
    selected=json.loads((ROOT/'reports/adversarial-batch-01/selected.json').read_text())
    opponents={c['name']:str(ROOT/'reports/adversarial-batch-01/opponents'/c['name']) for c in selected}
    opponents['champion']=str(FREEZE)
    packages={'champion':str(FREEZE),**{c.name:str(freeze(c)) for c in PROFILES}}
    lock={'started_utc':'2026-11-07T23:20:36+00:00','ends_utc':END.isoformat(),
        'deadline_status':'Organizer deadline/timezone unverified; user 04:00 is a planning assumption only.',
        'configs':{c.name:asdict(c) for c in PROFILES},'packages':packages,'opponents':opponents,
        'hashes':{path:sha(Path(path)) for path in set(packages.values())|set(opponents.values())},
        'screen':{'seeds':['b02-screen-17'],'deals':400,'opponents':['range_aware_2','champion'],'matches':12},
        'confirm':{'seeds':['b02-confirm-29','b02-confirm-61'],'deals':1000,'opponents':[c['name'] for c in selected],
                   'matches_per_profile':12,'profiles':'champion plus best A and best B; combination only if both screen gains positive'},
        'selection':'Highest equally weighted official points, then mean BB/deal. Best A/B representatives confirmed even if screen inconclusive.',
        'holdouts_used':False}
    p=OUT/'LOCK.json'
    if p.exists() and json.loads(p.read_text())!=lock:raise ValueError('Existing protocol lock differs')
    save(p,lock)
    # Published plan omits machine-specific paths, keeping portable identities.
    public={k:v for k,v in lock.items() if k not in ('packages','opponents','hashes')}
    public['source_hashes']={Path(path).name:h for path,h in lock['hashes'].items()}
    save(ROOT/'experiments/BATCH02_PLAN.json',public)


def check(lock):
    if datetime.now(timezone.utc)>=END:raise RuntimeError('90-minute budget exhausted; retain checkpoints')
    for path,h in lock['hashes'].items():
        if sha(Path(path))!=h:raise RuntimeError('Frozen source changed: '+path)


def play(profile,opponent,seed,deals,phase,lock):
    check(lock);path=OUT/phase/f'{profile}_{opponent}_{seed}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        with path.with_suffix('.runner.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'tools/run_local_match.py','--agent-dir',lock['packages'][profile],
                '--opponent-dir',lock['opponents'][opponent],'--deals',str(deals),'--seed',seed,
                '--logs','--require-opponent-diagnostics','--output',str(path)],cwd=ROOT,env=ENV,
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600,creationflags=FLAGS)
    r=read_official(path,seed,deals,opponent,4.0);r['profile']=profile;r['phase']=phase
    side=json.loads(path.with_suffix('.reliability.json').read_text())
    clean=all(h['opponent_diagnostics']['fault_events']==0 and h['opponent_diagnostics']['fallback_decisions']==0
              and not h['opponent_diagnostics']['disabled'] and h['opponent_log_fault_events']==0 for h in side['halves'])
    r['opponent_reliability_clean']=clean
    r['gate_passed']=all(r[k] for k in ('bot_valid','opponent_valid','runtime_target_met','reliability_clean','opponent_reliability_clean'))
    metrics=[]
    for half in (1,2):
        for line in path.with_suffix(f'.half{half}.agent1.log').read_text().splitlines():
            if line.startswith('RESEARCH_METRICS '):metrics.append(json.loads(line[17:]))
    r['research_metrics']=metrics
    print(phase,profile,opponent,seed,r['verdict'],round(r['mean_bb_per_deal'],4),r['ci'],r['max_time_seconds'],r['gate_passed'],flush=True)
    return r


def deltas(rows,phase):
    output=[]
    for r in rows:
        if r['profile']=='champion':continue
        ref=next(x for x in rows if x['profile']=='champion' and x['opponent']==r['opponent'] and x['seed']==r['seed'])
        pairs=[]
        for half in (1,2):
            p=OUT/phase/f'{r["profile"]}_{r["opponent"]}_{r["seed"]}.half{half}.json'
            b=OUT/phase/f'champion_{r["opponent"]}_{r["seed"]}.half{half}.json'
            x=json.loads(p.read_text())['nets_agent1'];y=json.loads(b.read_text())['nets_agent1']
            pairs.append([a-b for a,b in zip(x,y)])
        result=paired_summary(*pairs)
        output.append({'profile':r['profile'],'opponent':r['opponent'],'seed':r['seed'],
                       'delta_bb_per_deal':result['mean_bb_per_paired_deal'],'ci':result['ci95_bb']})
    return output


def run(phase):
    lock=json.loads((OUT/'LOCK.json').read_text());check(lock)
    profiles=list(lock['packages']);selection=None
    if phase=='confirm':
        screen=json.loads((OUT/'screen-summary.json').read_text())['matches']
        def rank(name):
            group=[r for r in screen if r['profile']==name]
            return (all(r['gate_passed'] for r in group),sum(r['points'] for r in group),sum(r['mean_bb_per_deal'] for r in group))
        a=max((c.name for c in PROFILES if c.name.startswith('A')),key=rank)
        b=max((c.name for c in PROFILES if c.name.startswith('B')),key=rank)
        profiles=['champion',a,b];baseline=rank('champion')
        # Predefined combination rule requires no point regression and positive
        # profit delta for BOTH independent changes on the same screening pool.
        good=lambda name:rank(name)[0] and rank(name)[1]>=baseline[1] and rank(name)[2]>baseline[2]
        if good(a) and good(b):
            ac=next(c for c in PROFILES if c.name==a);bc=next(c for c in PROFILES if c.name==b)
            combo=Settings('AB',alpha=ac.alpha,shrink=ac.shrink,action_values=True,uncertainty=bc.uncertainty,risk_penalty=bc.risk_penalty)
            folder=freeze(combo);lock['packages']['AB']=str(folder);lock['hashes'][str(folder)]=sha(folder)
            profiles.append('AB')
        selection={'profiles':profiles,'screen_rank':{n:rank(n) for n in list(json.loads((OUT/'LOCK.json').read_text())['packages'])},
                   'combination_justified':'AB' in profiles}
        save(OUT/'confirmation-lock.json',{'selection':selection,'lock':lock})
    rows=[];spec=lock[phase]
    for seed in spec['seeds']:
        for opponent in spec['opponents']:
            for profile in profiles:
                r=play(profile,opponent,seed,spec['deals'],phase,lock);rows.append(r)
                save(OUT/f'{phase}-summary.json',{'status':'running','matches':rows,'selection':selection})
    save(OUT/f'{phase}-summary.json',{'status':'complete','matches':rows,'selection':selection,'paired_deltas':deltas(rows,phase)})


if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='init':init()
    else:run(mode)
