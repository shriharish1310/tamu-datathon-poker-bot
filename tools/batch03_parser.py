"""Six predeclared exact-champion runs isolating Uvicorn's HTTP parser."""
import json,subprocess
from pathlib import Path
from tools import batch03 as batch
from tools.adversarial_batch import save

def main():
    # auto_envvar_prefix=UVICORN in the installed Uvicorn CLI; no callback edits.
    specs=[('h11','b03-runtime-13'),('httptools','b03-runtime-13'),
           ('httptools','b03-runtime-37'),('h11','b03-runtime-37'),
           ('h11','b03-runtime-73'),('httptools','b03-runtime-73')]
    root=batch.ROOT/'reports/batch03-parser';root.mkdir(parents=True,exist_ok=True)
    save(root/'PLAN.json',dict(jobs=specs,python='3.10.11',deals=1000,opponent='bluffy_1',
        hypothesis='Optional parser dependency differs between Windows and Linux; isolate parser on one otherwise idle Linux host.',
        frozen_policy='fd5c428',no_strategy_or_model_selection=True))
    (root/'cpu-hardware.txt').write_text(subprocess.check_output(['lscpu'],text=True))
    rows=[]
    for parser,seed in specs:
        batch.OUT=root/parser
        batch.ENV['UVICORN_HTTP']=parser
        batch.init()
        lock=json.loads((batch.OUT/'LOCK.json').read_text())
        row=batch.play('raw','bluffy_1',seed,1000,'runtime',lock)
        row['forced_http_parser']=parser;rows.append(row)
        save(root/'summary.json',dict(status='running',matches=rows))
    save(root/'summary.json',dict(status='complete',matches=rows))

if __name__=='__main__':main()
