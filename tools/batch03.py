"""Sequential, resumable Batch03 official matches and passive CPU telemetry."""
import argparse,hashlib,importlib.metadata,json,os,platform,statistics,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.adversarial_batch import RUNTIME,COMMIT,save,FLAGS,ENV
from tools.evaluate_suite import read_official
from tools.benchmark_strategy import paired_summary
PLAN=json.loads((ROOT/'experiments/BATCH03_PLAN.json').read_text())
OUT=ROOT/'reports/batch03'


def sha(folder):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}


def init():
    base={name:subprocess.check_output(['git','show',f'{COMMIT}:{name}'],cwd=ROOT) for name in RUNTIME}
    expected=json.loads((ROOT/'experiments/CHAMPION.json').read_text())['sha256']
    assert {n:hashlib.sha256(b).hexdigest() for n,b in base.items()}==expected
    packages={}
    for name in ('raw','observed','hybrid'):
        data=base.copy()
        data['batch03_audit_server.py']=(ROOT/'batch03_audit_server.py').read_bytes().replace(b'\r\n',b'\n')
        if name!='raw':
            data.update({f:(ROOT/f).read_bytes().replace(b'\r\n',b'\n') for f in ('batch03_policy.py','preflop_model.py')})
            data['strategy.py']=(f'from batch03_policy import ObservedPolicy\n_policy=ObservedPolicy(hybrid={name=="hybrid"})\n'
                'new_half=_policy.new_half\nchoose_action=_policy.choose_action\non_hand_end=_policy.on_hand_end\n').encode()
        if name=='hybrid':data['preflop_weights.json']=(ROOT/'experiments/batch03_preflop_weights.json').read_bytes().replace(b'\r\n',b'\n')
        folder=OUT/'packages'/name;folder.mkdir(parents=True,exist_ok=True)
        for f,b in data.items():
            p=folder/f
            if p.exists() and p.read_bytes()!=b:raise RuntimeError('Frozen package differs '+str(p))
            p.write_bytes(b)
        packages[name]=folder
    opponents={}
    for cfg in json.loads((ROOT/'experiments/batch03_opponents.json').read_text()):
        folder=OUT/'opponents'/cfg['name'];folder.mkdir(parents=True,exist_ok=True);data=base.copy()
        data['opponent_policy.py']=subprocess.check_output(['git','show','b725121:opponent_policy.py'],cwd=ROOT)
        data['strategy.py']=(f'from opponent_policy import Opponent, OpponentConfig\n_policy=Opponent(OpponentConfig(**{cfg!r}))\n'
            'new_half=_policy.new_half\nchoose_action=_policy.choose_action\non_hand_end=_policy.on_hand_end\n').encode()
        for f,b in data.items():
            p=folder/f
            if p.exists() and p.read_bytes()!=b:raise RuntimeError('Frozen opponent differs '+str(p))
            p.write_bytes(b)
        opponents[cfg['name']]=folder
    opponents['champion']=packages['raw']
    lock={'plan':PLAN,'packages':{n:str(p.relative_to(ROOT)) for n,p in packages.items()},
          'opponents':{n:str(p.relative_to(ROOT)) for n,p in opponents.items()},
          'hashes':{str(p.relative_to(ROOT)):sha(p) for p in set(packages.values())|set(opponents.values())}}
    # Normalize path separators for cross-platform package verification.
    lock=json.loads(json.dumps(lock).replace('\\\\','/'))
    path=OUT/'LOCK.json'
    if path.exists() and json.loads(path.read_text())!=lock:raise RuntimeError('Existing lock differs')
    save(path,lock)
    versions={}
    for name in ('fastapi','uvicorn','httpx','numpy','scikit-learn','psutil','pydantic','starlette','h11','uvloop','httptools'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    save(OUT/'environment.json',dict(platform=platform.platform(),python=sys.version,cpu=platform.processor(),
        logical_cpus=os.cpu_count(),dependencies=versions,source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))


def cpu_snapshot():
    import psutil
    processes={}
    for p in psutil.process_iter(['pid','name','cpu_times','create_time']):
        try:
            info=p.info;t=info['cpu_times'];processes[(p.pid,info['create_time'])]=(info['name'],t.user+t.system)
        except (psutil.NoSuchProcess,psutil.AccessDenied,TypeError):pass
    c=psutil.cpu_times()
    return time.monotonic(),sum(c),c.idle+getattr(c,'iowait',0),processes


def cpu_interval(a,b,excluded=()):
    duration=b[0]-a[0];busy=((b[1]-a[1])-(b[2]-a[2]))/max(.001,duration)
    procs=[]
    for key,(name,seconds) in b[3].items():
        if key in a[3]:
            delta=(seconds-a[3][key][1])/max(.001,duration)
            if delta>.005:procs.append(dict(pid=key[0],name=name,cores=delta,experiment=key[0] in excluded))
    procs.sort(key=lambda x:x['cores'],reverse=True)
    return dict(seconds=duration,busy_cores=max(0,busy),background_process_cores=sum(p['cores'] for p in procs if not p['experiment'] and p['name'] not in ('System Idle Process','Idle')),
                top_processes=procs[:12])


def play(profile,opponent,seed,deals,phase,lock):
    import psutil
    if datetime.now(timezone.utc)>=datetime.fromisoformat(PLAN['ends_utc']):raise RuntimeError('Batch budget exhausted')
    for name,hashes in lock['hashes'].items():
        if sha(ROOT/name)!=hashes:raise RuntimeError('Package hash changed '+name)
    path=OUT/phase/f'{profile}_{opponent}_{seed}.json';path.parent.mkdir(parents=True,exist_ok=True)
    telemetry=path.with_suffix('.cpu.json')
    if not path.exists():
        a=cpu_snapshot();time.sleep(PLAN['runtime']['idle_preflight_seconds']);b=cpu_snapshot()
        preflight=cpu_interval(a,b,[os.getpid()]);samples=[]
        cmd=[sys.executable,'tools/run_local_match.py','--agent-dir',str(ROOT/lock['packages'][profile]),
            '--opponent-dir',str(ROOT/lock['opponents'][opponent]),'--seed',seed,'--deals',str(deals),
            '--logs','--require-opponent-diagnostics','--output',str(path)]
        cmd += ['--agent-module','batch03_audit_server','--collect-batch03-metrics']
        # Local busy-host evidence is preserved but never called an idle-host comparison.
        with path.with_suffix('.runner.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=ENV,creationflags=FLAGS)
            before=cpu_snapshot();began=time.monotonic()
            while proc.poll() is None:
                time.sleep(1);after=cpu_snapshot()
                own=[os.getpid()]+[p.pid for p in psutil.Process().children(recursive=True)]
                samples.append(cpu_interval(before,after,own));before=after
                if time.monotonic()-began>600:proc.kill();raise RuntimeError('Bounded match exceeded 600 seconds')
        save(telemetry,dict(preflight=preflight,samples=samples,command=cmd,returncode=proc.returncode,
             idle_preflight=preflight['background_process_cores']<PLAN['runtime']['max_background_core_equivalents'],
             caveat='Passive process counters cannot establish physical-host isolation; transient exited processes can be missed.'))
        if proc.returncode:raise RuntimeError('Match failed; evidence retained at '+str(path))
    r=read_official(path,seed,deals,opponent,4.)
    r.update(profile=profile,phase=phase)
    evidence=json.loads(path.with_suffix('.reliability.json').read_text())
    r['opponent_reliability_clean']=all(not any((h['opponent_diagnostics']['fault_events'],h['opponent_diagnostics']['fallback_decisions'],
        h['opponent_diagnostics']['disabled'],h['opponent_log_fault_events'])) for h in evidence['halves'])
    r['gate_passed']=all(r[k] for k in ('bot_valid','opponent_valid','reliability_clean','opponent_reliability_clean','runtime_target_met'))
    r['metrics']=[]
    r['original_counters']=[h['batch03_metrics'] for h in evidence['halves']]
    for half in (1,2):
        for line in path.with_suffix(f'.half{half}.agent1.log').read_text().splitlines():
            if line.startswith('BATCH03_METRICS '):r['metrics'].append(json.loads(line[16:]))
    if profile!='raw' and len(r['metrics'])!=2:raise RuntimeError('Missing runtime telemetry')
    r['cpu']=json.loads(telemetry.read_text())
    print(phase,profile,opponent,seed,r['points'],round(r['mean_bb_per_deal'],5),r['max_time_seconds'],
          'idle',r['cpu']['idle_preflight'],flush=True)
    return r


def run(phase):
    lock=json.loads((OUT/'LOCK.json').read_text());rows=[];selection=None
    if phase=='confirm':
        screen=json.loads((OUT/'screen-summary.json').read_text())['matches']
        a=[r for r in screen if r['profile']=='raw'];b=[r for r in screen if r['profile']=='hybrid']
        promising=all(r['gate_passed'] for r in b) and sum(r['points'] for r in b)>=sum(r['points'] for r in a) and sum(r['mean_bb_per_deal'] for r in b)>sum(r['mean_bb_per_deal'] for r in a)
        selection=dict(promising=promising,rule=PLAN['promising'])
        save(OUT/'confirmation-lock.json',selection)
        if not promising:
            save(OUT/'confirm-summary.json',dict(status='not_justified',selection=selection,matches=[]));return
    spec=PLAN[phase]
    if phase=='runtime':
        jobs=[(p,spec['opponent'],seed) for seed,order in zip(spec['seeds'],spec['order']) for p in order]
    else:
        jobs=[(p,opp,seed) for i,seed in enumerate(spec['seeds']) for j,opp in enumerate(spec['opponents'])
              for p in (spec['profiles'] if (i+j)%2==0 else spec['profiles'][::-1])]
    for profile,opponent,seed in jobs:
        rows.append(play(profile,opponent,seed,spec['deals'],phase,lock))
        save(OUT/(phase+'-summary.json'),dict(status='running',matches=rows,selection=selection))
    deltas=[]
    for r in rows:
        if r['profile']!='hybrid':continue
        parts=[]
        for half in (1,2):
            a=json.loads((OUT/phase/f'hybrid_{r["opponent"]}_{r["seed"]}.half{half}.json').read_text())['nets_agent1']
            b=json.loads((OUT/phase/f'raw_{r["opponent"]}_{r["seed"]}.half{half}.json').read_text())['nets_agent1']
            parts.append([x-y for x,y in zip(a,b)])
        result=paired_summary(*parts)
        deltas.append(dict(opponent=r['opponent'],seed=r['seed'],mean=result['mean_bb_per_paired_deal'],ci=result['ci95_bb']))
    save(OUT/(phase+'-summary.json'),dict(status='complete',matches=rows,selection=selection,paired_deltas=deltas))


if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='init':init()
    else:run(mode)
