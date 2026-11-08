"""Frozen public-opponent screen. External code executes only in restricted Docker.

One full match per repository is a compatibility/strength screen, not a ranking.
The submitted branch and all strategy files remain untouched.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/public-opponents'


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def run(args, *, cwd=None, timeout=180, log=None):
    with open(log, 'w') if log else open(os.devnull, 'w') as stream:
        p = subprocess.run(list(map(str, args)), cwd=cwd, timeout=timeout,
                           stdout=stream if log else subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
    if p.returncode:
        raise RuntimeError(f'command exit {p.returncode}: {args[0:3]}; ' + (p.stdout or '')[-1200:])
    return (p.stdout or '').strip()


def archive(commit, target):
    target.mkdir(parents=True, exist_ok=True)
    # Only our trusted, already-inspected git tree is extracted on the host.
    data = subprocess.check_output(['git', 'archive', commit], cwd=ROOT)
    import io, tarfile
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(target, filter='data')


def snapshot(row, dest):
    run(['git', 'init', dest])
    run(['git', '-C', dest, 'fetch', '--depth=1', 'https://github.com/' + row['repo'] + '.git', row['sha']], timeout=90)
    # Do not run hooks, submodules, setup scripts, or external Dockerfiles.
    run(['git', '-C', dest, '-c', 'core.hooksPath=/dev/null', 'checkout', '--detach', 'FETCH_HEAD'])
    shutil.rmtree(dest / '.git')
    for p in dest.rglob('*'):
        if p.is_symlink():
            resolved = p.resolve()
            if not resolved.is_relative_to(dest.resolve()):
                raise RuntimeError('external symlink in source: ' + str(p.relative_to(dest)))
    if (dest / 'agent.py').is_file():
        return dest
    preferred = [dest / 'pokerbot', dest / 'FiWBot']
    for p in preferred:
        if (p / 'agent.py').is_file():
            return p
    candidates = [p.parent for p in dest.rglob('agent.py')
                  if not any(x in p.parts for x in ('baseline-bots', 'tests', '.venv', 'venv'))]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(f'no unambiguous agent.py entry point: {len(candidates)} candidates')


def probe(port, wait):
    deadline = time.monotonic() + wait
    while True:
        try:
            c = http.client.HTTPConnection('127.0.0.1', port, timeout=.5)
            c.request('GET', '/')
            r = c.getresponse()
            b = r.read(100000)
            c.close()
            if r.status == 200:
                print(json.dumps(json.loads(b)))
                return
        except (OSError, ValueError, http.client.HTTPException):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('startup/health failed')
        time.sleep(.1)


def restrictions(name, network, port):
    return ['docker', 'run', '-d', '--name', name, '--network', network,
            '--cpus', '1', '--memory', '4g', '--pids-limit', '256',
            '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--user', '10001:10001', '-e', f'PORT={port}', '-e', 'PYTHONDONTWRITEBYTECODE=1']


def judge_cmd(image, network, output, *args):
    return ['docker', 'run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}', '--network', network, '--cpus', '1', '--memory', '4g',
            '--pids-limit', '256', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=512m',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '-v', f'{ROOT}:/judge:ro', '-v', f'{output}:/out',
            '--entrypoint', 'python', image, *args]


def play(row, opponent_image, candidate_image, output, lock):
    identities, diagnostics, halves = [], [], []
    for half in (1, 2):
        own = 'pub-own-' + uuid.uuid4().hex[:12]
        opp = 'pub-opp-' + uuid.uuid4().hex[:12]
        try:
            run([*restrictions(own, 'none', 5008), candidate_image])
            run([*restrictions(opp, 'container:' + own, 5009), opponent_image])
            network = 'container:' + own
            ids = []
            for port in (5008, 5009):
                raw = run(judge_cmd(candidate_image, network, output,
                                   '/judge/tools/public_opponents.py', 'probe', str(port), '15'), timeout=30)
                ids.append(json.loads(raw))
            identities.append(ids)
            dest = f'half{half}.json'
            run(judge_cmd(candidate_image, network, output, '/judge/judge_engine.py',
                          '--agent1', '5008', '--agent2', '5009', '--half', str(half),
                          '--deals', str(lock['deals']), '--seed', lock['seed'],
                          '--json', '/out/' + dest, '--logs'), timeout=360,
                log=output / f'half{half}-judge.log')
            halves.append(dest)
            diag = []
            for port in (5008, 5009):
                try:
                    raw = run(judge_cmd(candidate_image, network, output,
                                       '/judge/tools/public_opponents.py', 'probe', str(port), '1'), timeout=10)
                    diag.append(json.loads(raw).get('diagnostics'))
                except Exception:
                    diag.append(None)
            diagnostics.append(diag)
        finally:
            for name, label in ((own, 'starfish'), (opp, 'opponent')):
                subprocess.run(['docker', 'logs', name], stdout=open(output / f'half{half}-{label}.log', 'w'), stderr=subprocess.STDOUT)
                subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(judge_cmd(candidate_image, 'none', output, '/judge/judge_engine.py', 'combine',
                  *('/out/' + p for p in halves), '--json', '/out/match.json'), log=output / 'combined.log')
    match = json.loads((output / 'match.json').read_text())
    result = {**row, 'status': 'played', 'verdict': match['verdict'],
              'points': match['points']['agent1'], 'bb_per_deal': match['mean_bb_per_deal'],
              'ci': match['ci'], 'agent_stats': match['agent_stats'],
              'identities': identities, 'diagnostics': diagnostics}
    result['opponent_forfeit'] = any(s['forfeited'] for s in match['agent_stats']['agent2'])
    result['starfish_forfeit'] = any(s['forfeited'] for s in match['agent_stats']['agent1'])
    result['max_starfish_time'] = max(s['time_seconds'] for s in match['agent_stats']['agent1'])
    return result


def main(shard, count):
    OUT.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'experiments/PUBLIC_OPPONENTS_LOCK.json').read_text())
    candidate = OUT / 'candidate'
    archive(lock['starfish_sha'], candidate)
    run(['docker', 'build', '-t', 'public-starfish', '-f', candidate / 'docker/Dockerfile.agent', candidate],
        timeout=600, log=OUT / 'starfish-build.log')
    smoke = OUT / 'harness-smoke'
    smoke.mkdir(parents=True, exist_ok=True)
    smoke_result = play({'repo': 'harness-self-check', 'sha': lock['starfish_sha']},
                        'public-starfish', 'public-starfish', smoke.resolve(),
                        {**lock, 'deals': 3, 'seed': 'harness-smoke'})
    if smoke_result['opponent_forfeit'] or smoke_result['starfish_forfeit']:
        raise RuntimeError('harness smoke failed; no external matches started')
    save(smoke / 'result.json', smoke_result)
    results = []
    for i, row in enumerate(lock['opponents']):
        if i % count != shard:
            continue
        folder = OUT / f'{i:02d}-{row["repo"].replace("/", "--")}'
        folder.mkdir(parents=True, exist_ok=True)
        result = {**row, 'status': 'pending'}
        try:
            if not row['sha']:
                raise RuntimeError('repository could not be pinned')
            source = snapshot(row, folder / 'source')
            result['entry_subdirectory'] = str(source.relative_to(folder / 'source'))
            # Retain source fingerprints. Never execute imported Python on host.
            result['source_sha256'] = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in source.rglob('*.py') if p.is_file()}
            save(folder / 'source-manifest.json', result)
            if not (source / 'requirements.txt').is_file():
                raise RuntimeError('requirements.txt missing at selected entry point')
            result['status'] = 'build_failed'
            # Trusted organizer Dockerfile; opponent .dockerignore is respected.
            image = 'public-opponent-' + str(i)
            run(['docker', 'build', '-t', image, '-f', ROOT / 'docker/Dockerfile.agent', source],
                timeout=180, log=folder / 'build.log')
            result['status'] = 'runtime_failed'
            result = play(row, image, 'public-starfish', folder.resolve(), lock)
            result['entry_subdirectory'] = str(source.relative_to(folder / 'source'))
        except Exception as exc:
            result['error'] = f'{type(exc).__name__}: {exc}'
        save(folder / 'result.json', result)
        results.append(result)
        save(OUT / f'shard-{shard}.json', {'starfish_sha': lock['starfish_sha'], 'seed': lock['seed'], 'results': results})
        print(json.dumps({k: result.get(k) for k in ('repo', 'status', 'verdict', 'bb_per_deal', 'error')}), flush=True)
        # Save manifests/logs/results; discard source trees and per-opponent images.
        shutil.rmtree(folder / 'source', ignore_errors=True)
        subprocess.run(['docker', 'image', 'rm', '-f', 'public-opponent-' + str(i)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def summarize(directory):
    rows = []
    for p in Path(directory).rglob('shard-*.json'):
        rows.extend(json.loads(p.read_text())['results'])
    rows.sort(key=lambda x: x['repo'].lower())
    lock = json.loads((ROOT / 'experiments/PUBLIC_OPPONENTS_LOCK.json').read_text())
    present = {r['repo'] for r in rows}
    for r in lock['opponents']:
        if r['repo'] not in present:
            rows.append({**r, 'status': 'not_completed'})
    save(Path(directory) / 'PUBLIC_RESULTS.json', {'starfish_sha': lock['starfish_sha'],
         'deals': lock['deals'], 'seed': lock['seed'], 'results': rows})
    text = ['# Frozen Starfish versus public repositories', '',
            'One seed and one full duplicate match per compatible repository. This is a screen, not a reliable ranking.', '',
            '| Opponent | Status | Verdict | BB/paired deal | 95% CI | Starfish max charged half |',
            '|---|---|---|---:|---|---:|']
    for r in rows:
        name = r['repo']
        status = r['status']
        if r.get('opponent_forfeit'):
            status += ' (opponent forfeit; not a strategic win)'
        if r.get('starfish_forfeit'):
            status += ' (Starfish forfeit)'
        ci = r.get('ci')
        text.append(f'| [{name}](https://github.com/{name}/tree/{r["sha"]}) | {status} | '
                    f'{r.get("verdict", "—")} | {r.get("bb_per_deal", "—")} | '
                    f'{ci if ci else "—"} | {r.get("max_starfish_time", "—")} |')
    output = '\n'.join(text) + '\n'
    (Path(directory) / 'PUBLIC_RESULTS.md').write_text(output)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(output)
    print(output)


if __name__ == '__main__':
    if sys.argv[1] == 'probe':
        probe(int(sys.argv[2]), float(sys.argv[3]))
    elif sys.argv[1] == 'summarize':
        summarize(sys.argv[2])
    else:
        main(int(sys.argv[1]), int(sys.argv[2]))
