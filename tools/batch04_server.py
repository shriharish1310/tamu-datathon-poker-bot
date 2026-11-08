"""External audit/profile entrypoint; never included in submission artifacts."""
import cProfile,importlib.metadata,json,os,pstats,sys,time
from collections import Counter
from pathlib import Path
sys.path.insert(0,'/app')
MODE=os.environ.get('B04_MODE','audit')
PARSER_NAME=None
startup=cProfile.Profile();started=time.perf_counter();startup.enable() if MODE=='profile' else None
import agent
startup.disable();startup_seconds=time.perf_counter()-started
from reliability import CORE_KEY
if MODE=='protocol':
    # Protocol equivalence only, never timing: identical full-budget clock inputs.
    import advanced_policy
    advanced_policy.perf_counter=lambda:0.
profiler=cProfile.Profile();sample_hist=Counter()
if MODE=='profile':
    from range_equity import Rollouts
    original=Rollouts.extend
    def extend(self,n):
        before=len(self.payoffs);original(self,n)
        if len(self.payoffs)>before:sample_hist[f'{len(self.board)}:{len(self.payoffs)}']+=1
    Rollouts.extend=extend

def stats(profile):
    return [{'file':file,'line':line,'function':func,'primitive_calls':cc,'calls':nc,
             'exclusive_seconds':tt,'cumulative_seconds':ct}
            for (file,line,func),(cc,nc,tt,ct,_) in pstats.Stats(profile).stats.items()]

@agent.app.get('/batch04-metrics')
async def metrics():
    if MODE=='profile':profiler.disable()
    m=agent.MEMORY[CORE_KEY]
    result={'startup_import_seconds':startup_seconds,'core_seconds':m['compute_seconds'],
        'decisions':m['decisions'],'experiment':m['experiment'],'sample_hist':dict(sample_hist),
        'diagnostics':agent.diagnostics(agent.MEMORY),'python':sys.version,
        'versions':{n:importlib.metadata.version(n) for n in ('fastapi','uvicorn','starlette','pydantic','h11')},
        'cpuinfo':Path('/proc/cpuinfo').read_text().split('\n\n')[0],
        'cgroup_cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
        'cgroup_memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),
        'cgroup_cpu_stat':Path('/sys/fs/cgroup/cpu.stat').read_text(),
        'network_interfaces':[p.name for p in Path('/sys/class/net').iterdir()],
        'http_parser':PARSER_NAME}
    try:result['httptools']=importlib.metadata.version('httptools')
    except importlib.metadata.PackageNotFoundError:result['httptools']=None
    if MODE=='profile':result.update(profile=stats(profiler),startup_profile=stats(startup))
    return result

if __name__=='__main__':
    import uvicorn
    config=uvicorn.Config(agent.app,host='0.0.0.0',port=int(os.environ.get('PORT','5008')),access_log=False)
    config.load()
    PARSER_NAME=str(config.http_protocol_class)
    print('B04_PARSER '+str(config.http_protocol_class),flush=True)
    if MODE=='profile':profiler.enable()
    uvicorn.Server(config).run()
