"""Locked, sequential final evaluation. Never edits candidate or opponent policy."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import batch04 as harness
from tools.adversarial_batch import save, RUNTIME

OUT = ROOT / 'reports/final-generalization'
LOCK_PATH = ROOT / 'experiments/FINAL_GENERALIZATION_LOCK.json'
LOCK_COMMIT = 'a16e68f9139a638743c9d085a48bd68b54f7e51e'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def inputs():
    locked = blob(LOCK_COMMIT, 'experiments/FINAL_GENERALIZATION_LOCK.json')
    if LOCK_PATH.read_bytes().replace(b'\r\n', b'\n') != locked:
        raise RuntimeError('Pre-open lock changed')
    plan = json.loads(locked)
    raw = (ROOT / plan['opponents_path']).read_bytes().replace(b'\r\n', b'\n')
    if sha(raw) != plan['opponents_canonical_sha256']:
        raise RuntimeError('Held-out opponent configurations changed')
    configs = json.loads(raw)
    assert len(configs) == len({c['name'] for c in configs}) == 12
    assert len(set(plan['seeds'])) == 3
    assert plan['max_full_match_slots'] == 36
    assert plan['paired_deals_per_match'] == 1000
    if (ROOT / 'judge_engine.py').read_bytes().replace(b'\r\n', b'\n') != blob(plan['candidate'], 'judge_engine.py'):
        raise RuntimeError('Official judge changed')
    schedule = []
    for round_index, seed in enumerate(plan['seeds']):
        for offset in range(12):
            config = configs[(4 * round_index + offset) % 12]
            schedule.append(dict(index=len(schedule)+1, opponent=config['name'], seed=seed))
    assert len({(s['opponent'], s['seed']) for s in schedule}) == 36
    return plan, configs, schedule


def candidate_image(plan):
    source = OUT / 'candidate-source'
    harness.run(['git', 'worktree', 'add', '--detach', str(source), plan['candidate']], cwd=ROOT)
    harness.run([sys.executable, '-m', 'pip', 'install', '-r', str(source/'requirements-dev.txt')])
    with (OUT/'candidate-tests.log').open('w') as log:
        harness.run([sys.executable, '-m', 'pytest', '-q'], cwd=source, stdout=log, stderr=subprocess.STDOUT)
    with (OUT/'candidate-official-build.log').open('w') as log:
        harness.run(['bash', 'tools/check_build.sh'], cwd=source, stdout=log, stderr=subprocess.STDOUT)
    harness.run([sys.executable, 'tools/check_container_reliability.py', '--output',
                 str(OUT/'candidate-container-reliability.json')], cwd=source)
    image = subprocess.check_output(['docker', 'image', 'inspect', '-f', '{{.Id}}',
                                    'poker-agent-check:latest'], text=True).strip()
    package_code = "import pathlib,json;print(json.dumps({'files':sorted(p.name for p in pathlib.Path('/app').iterdir())}))"
    result = harness.docker('run', '--rm', '--network', 'none', '--read-only', '--entrypoint',
                            'python', image, '-c', package_code, capture_output=True)
    if json.loads(result.stdout)['files'] != sorted(RUNTIME):
        raise RuntimeError('Unexpected files in candidate image')
    save(OUT/'candidate-image.json', dict(commit=plan['candidate'], image=image,
        files={f:sha(blob(plan['candidate'], f)) for f in RUNTIME}))
    return image


def opponent_images(plan, configs):
    images = {}
    for cfg in configs:
        name = cfg['name']
        folder = harness.stage(plan['opponent_runtime_commit'], name)
        (folder/'opponent_policy.py').write_bytes(blob(plan['opponent_policy_commit'], 'opponent_policy.py'))
        (folder/'strategy.py').write_text(
            f'from opponent_policy import Opponent,OpponentConfig\n_policy=Opponent(OpponentConfig(**{cfg!r}))\n'
            'new_half=_policy.new_half\nchoose_action=_policy.choose_action\non_hand_end=_policy.on_hand_end\n')
        tag = 'starfish-final-' + name
        harness.docker('build', '-f', folder/'docker/Dockerfile.agent', '-t', tag, folder)
        images[name] = subprocess.check_output(['docker', 'image', 'inspect', '-f', '{{.Id}}', tag], text=True).strip()
        save(OUT/(name+'-package.json'), dict(configuration=cfg, image=images[name],
            hashes={p.name:sha(p.read_bytes()) for p in folder.iterdir() if p.is_file()}))
    return images


def main():
    plan, configs, schedule = inputs()
    if '--check' in sys.argv:
        print(json.dumps(dict(lock_commit=LOCK_COMMIT, candidate=plan['candidate'],
            configurations=len(configs), slots=len(schedule), schedule=schedule), indent=2))
        return
    if OUT.exists():
        raise RuntimeError('Output exists: preserve earlier evidence; never silently restart a final evaluation')
    OUT.mkdir(parents=True)
    harness.OUT = OUT
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), lock_commit=LOCK_COMMIT,
        research_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        plan=plan, schedule=schedule, source_sha256={f:sha((ROOT/f).read_bytes()) for f in (
            'tools/final_generalization.py','tools/batch04.py','tools/batch04_server.py',
            'tools/batch04_client.py','judge_engine.py','tools/evaluate_suite.py')})
    save(OUT/'manifest.json', manifest)
    image = candidate_image(plan)
    judge_image = harness.build(plan['fallback'], 'judge')
    opponents = opponent_images(plan, configs)
    rows, ledger = [], []
    for slot in schedule:
        ledger.append(dict(**slot, status='started', started_utc=datetime.now(timezone.utc).isoformat()))
        save(OUT/'match-ledger.json', ledger)
        try:
            row = harness.play('candidate', image, slot['opponent'], opponents[slot['opponent']],
                               slot['seed'], slot['index'], judge_image)
        except Exception as exc:
            ledger[-1].update(status='failed', error=repr(exc))
            save(OUT/'match-ledger.json', ledger)
            save(OUT/'benchmark.json', dict(status='incomplete', matches=rows, candidate_commit=plan['candidate']))
            raise
        rows.append(row)
        ledger[-1].update(status='complete', completed_utc=datetime.now(timezone.utc).isoformat())
        save(OUT/'match-ledger.json', ledger)
        save(OUT/'benchmark.json', dict(status='running', matches=rows, candidate_commit=plan['candidate']))
    save(OUT/'benchmark.json', dict(status='complete', matches=rows, candidate_commit=plan['candidate'],
        candidate_image=image, judge_image=judge_image, opponent_images=opponents,
        completed_utc=datetime.now(timezone.utc).isoformat()))


if __name__ == '__main__':
    main()
