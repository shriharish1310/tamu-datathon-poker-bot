"""Official-image Batch04 harness. Research files are only external RO mounts."""
import argparse,hashlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.adversarial_batch import save,RUNTIME
PLAN=json.loads((ROOT/'experiments/BATCH04_PLAN.json').read_text())
OUT=ROOT/'reports/batch04'

def run(cmd,**kwargs):
    result=subprocess.run(cmd,text=True,**kwargs)
    if result.returncode:
        if result.stdout:print(result.stdout)
        if result.stderr:print(result.stderr,file=sys.stderr)
        raise RuntimeError(f'Command failed ({result.returncode}): {cmd}')
    return result

def docker(*args,**kwargs):return run(['docker',*map(str,args)],**kwargs)

def stage(commit,name):
    target=OUT/'packages'/name;target.mkdir(parents=True,exist_ok=True)
    names=(*RUNTIME,'.dockerignore','docker/Dockerfile.base','docker/Dockerfile.agent',
        'tools/check_build.sh','tools/smoke_test.py','tools/check_container_reliability.py')
    hashes={}
    for f in names:
        b=subprocess.check_output(['git','show',f'{commit}:{f}'],cwd=ROOT)
        path=target/f;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b);hashes[f]=hashlib.sha256(b).hexdigest()
    save(OUT/(name+'-source.json'),dict(commit=commit,files=hashes))
    return target

def build(commit,name):
    target=stage(commit,name);tag='starfish-b04-'+name
    docker('build','-f',target/'docker/Dockerfile.agent','-t',tag,target)
    image=subprocess.check_output(['docker','image','inspect','-f','{{.Id}}',tag],text=True).strip()
    save(OUT/(name+'-image.json'),dict(image=image,commit=commit))
    return image

def restrictions(name,network='none',port=5008):
    return ['run','-d','--name',name,'--label','starfish.batch04=true','--network',network,
        '--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','256','--cpus','1','--memory','4g','-e',f'PORT={port}']

def mounts():
    return ['-v',f'{ROOT / "tools/batch04_server.py"}:/research/server.py:ro',
            '-v',f'{ROOT / "tools/batch04_client.py"}:/research/client.py:ro',
            '-v',f'{ROOT / "experiments/batch04_observations.json.gz"}:/research/observations.json.gz:ro']

def client(bot,image,*args):
    return docker('run','--rm','--user','0','--network','container:'+bot,'--read-only',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=512m',*mounts(),'-v',f'{OUT.resolve()}:/out',
        '--entrypoint','python',image,'/research/client.py',*args,capture_output=True)

def cleanup(names):
    for name in names:
        # Exact nonce-owned names only; never touch unrelated user containers.
        labels=subprocess.run(['docker','inspect','-f','{{json .Config.Labels}}',name],capture_output=True,text=True)
        if labels.returncode==0 and json.loads(labels.stdout).get('starfish.batch04')=='true':
            subprocess.run(['docker','rm','-f',name],capture_output=True)

def profile():
    image=build(PLAN['baseline'],'baseline')
    for mode in ('audit','profile'):
        name='b04-'+mode+'-'+uuid.uuid4().hex[:10]
        try:
            before=time.monotonic()
            docker(*restrictions(name),*mounts(),'-e','B04_MODE='+mode,'--entrypoint','python',image,'/research/server.py',capture_output=True)
            client(name,image,'--replay','--output','/out/'+mode+'-replay.json')
            data=json.loads((OUT/(mode+'-replay.json')).read_text());data['container_total_seconds']=time.monotonic()-before
            data['image']=image;save(OUT/(mode+'-replay.json'),data)
            (OUT/(mode+'-container.log')).write_text(subprocess.check_output(['docker','logs',name],stderr=subprocess.STDOUT,text=True))
        finally:
            logs=subprocess.run(['docker','logs',name],capture_output=True,text=True)
            (OUT/(mode+'-container.log')).write_text(logs.stdout+'\n'+logs.stderr)
            cleanup([name])

def prepare_opponents():
    configs=json.loads((ROOT/'experiments/batch03_opponents.json').read_text());images={}
    for name in ('bluffy_1','range_aware_2'):
        cfg=next(c for c in configs if c['name']==name);folder=stage(PLAN['baseline'],name)
        (folder/'opponent_policy.py').write_bytes(subprocess.check_output(['git','show','b725121:opponent_policy.py']))
        (folder/'strategy.py').write_text(f'from opponent_policy import Opponent,OpponentConfig\n_policy=Opponent(OpponentConfig(**{cfg!r}))\nnew_half=_policy.new_half\nchoose_action=_policy.choose_action\non_hand_end=_policy.on_hand_end\n')
        tag='starfish-b04-'+name;docker('build','-f',folder/'docker/Dockerfile.agent','-t',tag,folder)
        images[name]=subprocess.check_output(['docker','image','inspect','-f','{{.Id}}',tag],text=True).strip()
        save(OUT/(name+'-package.json'),dict(configuration=cfg,image=images[name],
            hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}))
    return images

def equivalent(images):
    result={'passed':True,'comparisons':[]}
    for mode in ('full','half','boundary'):
        paths={}
        for profile,image in images.items():
            path=OUT/f'{profile}-equivalence-{mode}.json';paths[profile]=path
            docker('run','--rm','--network','none','--read-only','--cpus','1','--memory','4g',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--user','0',*mounts(),
                '-v',f'{ROOT / "tools/batch04_equivalence.py"}:/research/equivalence.py:ro',
                '-v',f'{OUT.resolve()}:/out','--entrypoint','python',image,'/research/equivalence.py',
                '--mode',mode,'--output','/out/'+path.name)
        a=json.loads(paths['baseline'].read_text());b=json.loads(paths['candidate'].read_text())
        differences=[dict(index=x['index'],fields=[k for k in x if x[k]!=y[k]]) for x,y in zip(a['records'],b['records']) if x!=y]
        passed=a==b;result['passed'] &= passed
        result['comparisons'].append(dict(mode=mode,decisions=a['decisions'],passed=passed,differences=differences[:100],
            hashes={p:hashlib.sha256(path.read_bytes()).hexdigest() for p,path in paths.items()}))
    save(OUT/'equivalence.json',result)
    if not result['passed']:raise RuntimeError('Behavioral equivalence failed; do not begin match timing')

def cpu_sample():
    import psutil
    return psutil.cpu_percent(interval=3)

def play(profile,image,opponent,opp_image,seed,index):
    from tools.evaluate_suite import read_official
    out=OUT/'matches'/f'{index:02}_{profile}_{opponent}_{seed}.json';out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise RuntimeError('Never overwrite a completed match')
    evidence={'schema':'bot-reliability-v1','status':'running','match_seed':seed,'num_deals':1000,'halves':[]}
    metrics=[];half_files=[];background=cpu_sample()
    for half in (1,2):
        bot='b04-'+uuid.uuid4().hex[:12];opp=bot+'-opp';started=[];identity=[];diag=None;opp_diag=None;failure=None
        try:
            began=time.monotonic()
            docker(*restrictions(bot),*mounts(),'--entrypoint','python',image,'/research/server.py',capture_output=True)
            identity.append(json.loads(client(bot,image,'--health').stdout));started.append(time.monotonic()-began)
            began=time.monotonic()
            docker(*restrictions(opp,'container:'+bot,5009),opp_image,capture_output=True)
            identity.append(json.loads(client(bot,image,'--health','--port','5009').stdout));started.append(time.monotonic()-began)
            half_file=out.with_suffix(f'.half{half}.json');half_files.append(half_file)
            launcher="import sys,runpy;sys.path.insert(0,'/app');runpy.run_path('/research/judge_engine.py',run_name='__main__')"
            cmd=['run','--rm','--user','0','--network','container:'+bot,'--cpus','1','--memory','4g','--read-only',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=512m','-v',f'{ROOT / "judge_engine.py"}:/research/judge_engine.py:ro',
                '-v',f'{OUT.resolve()}:/out','--entrypoint','python',image,'-c',launcher,
                '--agent1','http://127.0.0.1:5008','--agent2','http://127.0.0.1:5009',
                '--deals','1000','--seed',seed,'--half',str(half),'--logs','--json','/out/matches/'+half_file.name]
            with out.with_suffix(f'.half{half}.judge.log').open('w') as log:docker(*cmd,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            m=json.loads(client(bot,image).stdout);diag=m['diagnostics']
            opp_diag=json.loads(client(bot,image,'--health','--port','5009').stdout)['diagnostics']
            m.update(half=half,startup_readiness_upper_seconds=started)
            metrics.append(m)
        except Exception as exc:failure=repr(exc)
        finally:
            counts=[]
            for n,container in enumerate((bot,opp),1):
                log=subprocess.run(['docker','logs',container],capture_output=True,text=True)
                text=log.stdout+'\n'+log.stderr;out.with_suffix(f'.half{half}.agent{n}.log').write_text(text)
                counts.append(text.count('BOT_STRATEGY_FAULT'))
            cleanup([opp,bot])
        h=dict(half=half,diagnostics=diag,opponent_diagnostics=opp_diag,log_fault_events=counts[0],
               opponent_log_fault_events=counts[1],agents=identity)
        if failure:h['evidence_error']=failure
        evidence['halves'].append(h)
        save(out.with_suffix('.reliability.json'),evidence)
        if failure:raise RuntimeError(failure)
    run([sys.executable,'judge_engine.py','combine',*map(str,half_files),'--json',str(out)],cwd=ROOT,capture_output=True)
    evidence['status']='complete';save(out.with_suffix('.reliability.json'),evidence)
    r=read_official(out,seed,1000,opponent,4.)
    r['opponent_reliability_clean']=all(not any((h['opponent_diagnostics']['fault_events'],h['opponent_diagnostics']['fallback_decisions'],h['opponent_diagnostics']['disabled'],h['opponent_log_fault_events'])) for h in evidence['halves'])
    r.update(profile=profile,metrics=metrics,idle_host_cpu_percent=background,match_index=index)
    save(out.with_suffix('.metrics.json'),r)
    print('MATCH',index,profile,opponent,seed,r['points'],r['mean_bb_per_deal'],r['max_time_seconds'],flush=True)
    return r

def bench():
    candidate=json.loads((ROOT/'experiments/BATCH04_CANDIDATE.json').read_text())['commit']
    baseline=build(PLAN['baseline'],'baseline')
    source=OUT/'candidate-source'
    run(['git','worktree','add','--detach',str(source),candidate],cwd=ROOT)
    with (OUT/'candidate-tests.log').open('w') as log:
        run([sys.executable,'-m','pytest','-q'],cwd=source,stdout=log,stderr=subprocess.STDOUT)
    # Official script, exact commit, unmodified official Docker recipe.
    with (OUT/'candidate-official-build.log').open('w') as log:
        run(['bash','tools/check_build.sh'],cwd=source,stdout=log,stderr=subprocess.STDOUT)
    run([sys.executable,'tools/check_container_reliability.py','--output',str(OUT/'candidate-container-reliability.json')],cwd=source)
    candidate_image=subprocess.check_output(['docker','image','inspect','-f','{{.Id}}','poker-agent-check:latest'],text=True).strip()
    save(OUT/'candidate-image.json',dict(commit=candidate,image=candidate_image))
    images={'baseline':baseline,'candidate':candidate_image}
    equivalent(images)
    opponents=prepare_opponents();rows=[];ledger=[]
    for pair in PLAN['paired_repeats']:
        for profile in pair['order']:
            index=len(ledger)+1
            assert index<=PLAN['max_full_official_matches']
            ledger.append(dict(index=index,profile=profile,seed=pair['seed'],opponent=pair['opponent'],status='started'))
            save(OUT/'match-ledger.json',ledger)
            row=play(profile,images[profile],pair['opponent'],opponents[pair['opponent']],pair['seed'],index)
            rows.append(row);ledger[-1]['status']='complete';save(OUT/'match-ledger.json',ledger)
            save(OUT/'benchmark.json',dict(status='running',matches=rows))
    save(OUT/'benchmark.json',dict(status='complete',matches=rows,images=images,candidate_commit=candidate))

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    mode=sys.argv[1]
    if mode=='profile':profile()
    elif mode=='bench':bench()
    else:raise ValueError(mode)
