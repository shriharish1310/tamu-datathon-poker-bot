"""Official-image Batch04 harness. Research files are only external RO mounts."""
import argparse,hashlib,json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.adversarial_batch import save,RUNTIME
PLAN=json.loads((ROOT/'experiments/BATCH04_PLAN.json').read_text())
OUT=ROOT/'reports/batch04'

def run(cmd,**kwargs):
    return subprocess.run(cmd,check=True,text=True,**kwargs)

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
        finally:cleanup([name])

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    mode=sys.argv[1]
    if mode=='profile':profile()
    else:raise ValueError(mode)
