"""Resumable development pool search. Held-out configurations are never loaded.

Direct screens use official scoring but do not enforce the HTTP time bank.
Each child is a fresh process; HTTP validation restarts both bots every half.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opponent_policy import Opponent, OpponentConfig
from tools.experiment_grid import match
from tools.evaluate_suite import read_official
from game import make_deal
from evaluator import warmup

COMMIT = 'fd5c428475eee98edb7c38bd1e7fc0870ddbf42d'
FREEZE = ROOT/'reports/champion-fd5c428'
OUT = ROOT/'reports/adversarial-batch-01'
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
RUNTIME = ('agent.py','strategy.py','reliability.py','advanced_policy.py','baseline_strategy.py',
           'range_equity.py','policy_config.py','equity.py','evaluator.py','game.py','requirements.txt')
ENV = {**os.environ, 'PYTHONUTF8':'1', 'PYTHONDONTWRITEBYTECODE':'1'}


def save(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


def fingerprint():
    names = (*RUNTIME, 'opponent_policy.py','tools/adversarial_batch.py','tools/experiment_grid.py',
             'tools/run_local_match.py','tools/evaluate_suite.py','judge_engine.py')
    return {name:hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in names}


def initialize():
    FREEZE.mkdir(parents=True,exist_ok=True)
    hashes = {}
    for name in RUNTIME:
        blob = subprocess.check_output(['git','show',f'{COMMIT}:{name}'],cwd=ROOT)
        path = FREEZE/name
        if path.exists() and path.read_bytes()!=blob:
            raise RuntimeError('Frozen champion changed: '+name)
        path.write_bytes(blob)
        hashes[name] = hashlib.sha256(blob).hexdigest()
    lock = {'commit':COMMIT,'profile':'range_130_budget25','sha256':hashes,
            'configuration':json.loads((ROOT/'experiments/RELEASE_LOCK.json').read_text())['configuration']}
    save(ROOT/'experiments/CHAMPION.json',lock)
    base = [
        OpponentConfig('tight','tight',call_margin=.15,value_threshold=.72,bluff_rate=.01,pot_probability=.7),
        OpponentConfig('loose','loose',call_margin=-.13,value_threshold=.55,bluff_rate=.03,pot_probability=.25),
        OpponentConfig('aggressive','aggressive',call_margin=-.02,value_threshold=.46,reraise_extra=.01,bluff_rate=.18,pot_probability=.8),
        OpponentConfig('selective','selective',call_margin=.07,value_threshold=.74,reraise_extra=.04,bluff_rate=.0,pot_probability=.9,river_shift=.04),
        OpponentConfig('bluffy','bluffy',call_margin=.01,value_threshold=.63,bluff_rate=.42,pot_probability=.85),
        OpponentConfig('range_aware','range_aware',call_margin=.015,value_threshold=.57,reraise_extra=.06,bluff_rate=.07,range_aware=True),
    ]
    def vary(b, rng, name):
        return replace(b,name=name,call_margin=b.call_margin+rng.uniform(-.07,.07),
            value_threshold=b.value_threshold+rng.uniform(-.08,.08),
            reraise_extra=rng.uniform(0,.12),bluff_rate=max(0,min(.65,b.bluff_rate+rng.uniform(-.06,.12))),
            pot_probability=rng.uniform(.2,1),size_pressure=rng.uniform(0,.15),
            range_cutoff=rng.uniform(.55,.85),range_width=rng.uniform(.08,.2),
            range_bluff=rng.uniform(.04,.25),salt=rng.randrange(2**30))
    dev, held = [], []
    rng, private = random.Random(44107),random.Random(88319)
    for b in base:
        dev.append(replace(b,name=b.family+'_0').to_dict())
        dev.extend(vary(b,rng,b.family+'_'+str(i)).to_dict() for i in range(1,4))
        held.extend(vary(b,private,b.family+'_held_'+str(i)).to_dict() for i in range(2))
    for name,data in [('opponents-development.json',dev),('opponents-heldout.json',held)]:
        path=ROOT/'experiments'/name
        if path.exists() and json.loads(path.read_text())!=data:
            raise RuntimeError('Existing opponent lock differs')
        save(path,data)
    save(ROOT/'experiments/BATCH01_PLAN.json',{
        'deadline':'2026-11-08T04:00:00-06:00','development_stop':'2026-11-08T00:00:00-06:00',
        'deadline_timezone_assumption':'America/Chicago from user environment',
        'screen':{'configurations':24,'deals':300,'seed':'adv-dev-screen-01'},
        'confirmation':{'one_per_family':True,'deals':1000,'seeds':['adv-dev-confirm-01','adv-dev-confirm-02']},
        'http':{'one_per_family':True,'deals':1000,'seeds':['adv-dev-http-01','adv-dev-http-02']},
        'heldout_configuration_count':12,'heldout_used':False,
        'selection':'minimize champion points then champion BB/deal on screen; confirmation is development',
        'decision':'Pool characterization only; no champion replacement or final holdout use.'})


def check_time():
    if datetime.now(timezone.utc)>=datetime.fromisoformat('2026-11-08T06:00:00+00:00'):
        raise RuntimeError('Development cutoff reached; preserve checkpoint and enter validation window')


def load_champion():
    # Frozen modules must precede the editable workspace on the import path.
    for name in ('strategy','advanced_policy','baseline_strategy','range_equity','policy_config','equity'):
        sys.modules.pop(name,None)
    sys.path.insert(0,str(FREEZE))
    import strategy
    return strategy


def package(config):
    target=OUT/'opponents'/config['name']
    files={name:(FREEZE/name).read_bytes() for name in RUNTIME}
    files['opponent_policy.py']=(ROOT/'opponent_policy.py').read_bytes()
    files['strategy.py']=('from opponent_policy import Opponent, OpponentConfig\n'
        f'_policy=Opponent(OpponentConfig(**{config!r}))\nnew_half=_policy.new_half\n'
        'choose_action=_policy.choose_action\non_hand_end=_policy.on_hand_end\n').encode()
    target.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        p=target/name
        if p.exists() and p.read_bytes()!=data:
            raise RuntimeError('Opponent package changed: '+str(p))
        p.write_bytes(data)
    save(target/'config.json',config)
    return target


def direct(config, seed, deals, phase):
    result=OUT/phase/(config['name']+'_'+seed+'.json')
    if not result.exists():
        check_time()
        result.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run([sys.executable,__file__,'worker','--name',config['name'],'--seed',seed,
            '--deals',str(deals),'--result',str(result)],cwd=ROOT,env=ENV,check=True,timeout=180,creationflags=FLAGS)
    return json.loads(result.read_text())


def run():
    configs=json.loads((ROOT/'experiments/opponents-development.json').read_text())
    sources=fingerprint()
    manifest=OUT/'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text())!=sources:
        raise RuntimeError('Batch sources changed; use a new batch')
    save(manifest,sources)
    rows=[]
    for cfg in configs:
        if fingerprint()!=sources: raise RuntimeError('Source changed during batch')
        row=direct(cfg,'adv-dev-screen-01',300,'screen')
        rows.append(row)
        print('SCREEN',cfg['name'],row['points'],round(row['mean_bb_per_paired_deal'],4),flush=True)
    selected=[]
    for family in dict.fromkeys(c['family'] for c in configs):
        names={c['name'] for c in configs if c['family']==family}
        worst=min((r for r in rows if r['opponent'] in names),key=lambda r:(r['points'],r['mean_bb_per_paired_deal']))
        selected.append(next(c for c in configs if c['name']==worst['opponent']))
    save(OUT/'selected.json',selected)
    confirmation=[]
    for cfg in selected:
        for seed in ['adv-dev-confirm-01','adv-dev-confirm-02']:
            if fingerprint()!=sources: raise RuntimeError('Source changed during batch')
            r=direct(cfg,seed,1000,'confirmation'); confirmation.append(r)
            print('CONFIRM',cfg['name'],r['points'],round(r['mean_bb_per_paired_deal'],4),flush=True)
    save(OUT/'direct-summary.json',{'screen':rows,'confirmation':confirmation})
    official=[]
    for seed in ['adv-dev-http-01','adv-dev-http-02']:
        for cfg in selected:
            check_time()
            if fingerprint()!=sources: raise RuntimeError('Source changed during batch')
            report=OUT/'http'/(cfg['name']+'_'+seed+'.json')
            report.parent.mkdir(parents=True,exist_ok=True)
            if not report.exists():
                with report.with_suffix('.runner.log').open('w',encoding='utf-8') as log:
                    subprocess.run([sys.executable,'tools/run_local_match.py','--agent-dir',str(FREEZE),
                        '--opponent-dir',str(package(cfg)),'--deals','1000','--seed',seed,'--logs','--require-opponent-diagnostics',
                        '--output',str(report)],cwd=ROOT,env=ENV,stdout=log,stderr=subprocess.STDOUT,
                        check=True,timeout=660,creationflags=FLAGS)
            r=read_official(report,seed,1000,cfg['name'],4.0)
            # Require opponent internal reliability as well as official validity.
            evidence=json.loads(report.with_suffix('.reliability.json').read_text())
            opponent_clean=all(h['opponent_diagnostics']['fault_events']==0
                and h['opponent_diagnostics']['fallback_decisions']==0
                and not h['opponent_diagnostics']['disabled'] and h['opponent_log_fault_events']==0
                for h in evidence['halves'])
            r['opponent_reliability_clean']=opponent_clean
            r['family']=cfg['family']; official.append(r)
            gates=r['bot_valid'] and r['opponent_valid'] and r['runtime_target_met'] and r['reliability_clean'] and opponent_clean
            save(OUT/'leaderboard.json',{'status':'running' if gates else 'stopped_gate','champion_commit':COMMIT,
                'decision':'retain champion; no candidate upgrade tested','matches':official,'heldout_used':False})
            print('HTTP',cfg['name'],seed,r['verdict'],r['mean_bb_per_deal'],r['ci'],r['max_time_seconds'],flush=True)
            if not gates: raise RuntimeError('Release gate failed; retain evidence')
    save(OUT/'leaderboard.json',{'status':'complete','champion_commit':COMMIT,
         'decision':'retain champion; no candidate upgrade tested','matches':official,'heldout_used':False})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['init','run','worker'])
    p.add_argument('--name'); p.add_argument('--seed'); p.add_argument('--deals',type=int);p.add_argument('--result',type=Path)
    a=p.parse_args()
    if a.mode=='init': initialize()
    elif a.mode=='run': run()
    else:
        cfg=next(c for c in json.loads((ROOT/'experiments/opponents-development.json').read_text()) if c['name']==a.name)
        champion=load_champion(); warmup()
        r=match(champion,Opponent(OpponentConfig(**cfg)),[make_deal(a.seed,i) for i in range(a.deals)])
        save(a.result,{**r,'opponent':a.name,'config':cfg,'seed':a.seed,'deals':a.deals})


if __name__=='__main__': main()
