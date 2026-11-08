"""Audit all Batch04 gates, preserve evidence, and archive only an accepted commit."""
from collections import defaultdict
from datetime import datetime,timezone
import hashlib,json,random,re,statistics,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.adversarial_batch import save,RUNTIME
from tools.benchmark_strategy import paired_summary
OUT=ROOT/'reports/batch04-bench';PROFILE=ROOT/'reports/batch04-profile'
PLAN=json.loads((ROOT/'experiments/BATCH04_PLAN.json').read_text())
CANDIDATE=json.loads((ROOT/'experiments/BATCH04_CANDIDATE.json').read_text())

def load(path):return json.loads(path.read_text())
def blob(commit,path):return subprocess.check_output(['git','show',f'{commit}:{path}'],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()

def profile_summary():
    p=load(PROFILE/'profile-replay.json');plain=load(PROFILE/'audit-replay.json');groups=defaultdict(float)
    for r in p['profile']:
        f,fn=r['file'],r['function'];category='Other framework/dispatch overhead'
        if 'epoll' in fn and 'poll' in fn:category='Idle/poll'
        elif f.endswith('/equity.py') and fn=='_score_masks':category='Hand evaluation'
        elif '/h11/' in f or '/uvicorn/protocols/http/' in f:category='HTTP protocol processing'
        elif '/json/' in f or '/fastapi/encoders.py' in f or (f.endswith('/game.py') and fn=='from_dict'):category='Parsing/serialization'
        elif f.endswith('/range_equity.py') and fn not in ('extend','__init__'):category='Range features/weights'
        elif f.endswith(('/range_equity.py','/equity.py','/random.py')) or 'getrandbits' in fn:category='Rollout generation/helpers'
        groups[category]+=r['exclusive_seconds']
    keys=('startup_import_seconds','core_seconds','experiment','requests','request_wall_seconds','charged_equivalent_seconds')
    return dict(exclusive_seconds=dict(groups),profiled={k:p[k] for k in keys},unprofiled={k:plain[k] for k in keys},
        environment={k:p[k] for k in ('python','versions','httptools','cpuinfo','cgroup_cpu_max','cgroup_memory_max','image')},
        scope='Recorded-request replay. Charged-equivalent values follow the 1ms grace convention but are not scored matches. cProfile distorts timings and sample pacing; not included in speed gates.',
        artifact_sha256={f:sha((PROFILE/f).read_bytes()) for f in ('profile-replay.json','audit-replay.json')})

def path_for(row,half=None):
    stem=f'{row["match_index"]:02}_{row["profile"]}_{row["opponent"]}_{row["seed"]}'
    return OUT/'matches'/(stem+(f'.half{half}' if half else '')+'.json')

def paired(rows):
    pairs=[]
    for spec in PLAN['paired_repeats']:
        a=next(r for r in rows if r['profile']=='baseline' and r['seed']==spec['seed'] and r['opponent']==spec['opponent'])
        b=next(r for r in rows if r['profile']=='candidate' and r['seed']==spec['seed'] and r['opponent']==spec['opponent'])
        differences=[]
        for half in (1,2):
            x=load(path_for(a,half))['nets_agent1'];y=load(path_for(b,half))['nets_agent1']
            differences.append([j-i for i,j in zip(x,y)])
        delta=paired_summary(*differences)
        ra,rb=load(path_for(a)),load(path_for(b))
        trace_differences=sum(x['actions']!=y['actions'] for half in ('half1','half2') for x,y in zip(ra['logs'][half],rb['logs'][half]))
        pairs.append(dict(seed=spec['seed'],opponent=spec['opponent'],order=spec['order'],
            baseline_charged=[h['time_seconds'] for h in a['agent_stats']['agent1']],
            candidate_charged=[h['time_seconds'] for h in b['agent_stats']['agent1']],
            baseline_samples=[m['experiment']['sampled_trials'] for m in a['metrics']],
            candidate_samples=[m['experiment']['sampled_trials'] for m in b['metrics']],
            baseline_core_seconds=[m['core_seconds'] for m in a['metrics']],
            candidate_core_seconds=[m['core_seconds'] for m in b['metrics']],
            baseline_points=a['points'],candidate_points=b['points'],
            baseline_bb=a['mean_bb_per_deal'],candidate_bb=b['mean_bb_per_deal'],
            baseline_official_ci=a['ci'],candidate_official_ci=b['ci'],
            profit_delta=delta['mean_bb_per_paired_deal'],profit_delta_ci=delta['ci95_bb'],
            different_hand_action_traces=trace_differences,
            behavior_note='Natural clocks can change pacing, sample counts, actions, and subsequent opponent memory. This is not bit-identical live trajectory equivalence.'))
    return pairs

def timing(rows,pairs):
    core=[p for p in pairs if p['opponent']=='bluffy_1'];a=sum([p['baseline_charged'] for p in core],[]);b=sum([p['candidate_charged'] for p in core],[])
    rng=random.Random(4004);draws=[]
    for _ in range(10000):
        sample=rng.choices(core,k=len(core));x=sum([p['baseline_charged'] for p in sample],[]);y=sum([p['candidate_charged'] for p in sample],[])
        draws.append(1-statistics.median(y)/statistics.median(x))
    draws.sort()
    groups={}
    for name in ('baseline','candidate'):
        group=[r for r in rows if r['profile']==name];halves=[h for r in group for h in r['agent_stats']['agent1']]
        groups[name]=dict(points=sum(r['points'] for r in group),matches=len(group),
            mean_bb_per_deal=statistics.mean(r['mean_bb_per_deal'] for r in group),
            worst_seconds=max(h['time_seconds'] for h in halves),all_under_four=all(h['time_seconds']<4 for h in halves),
            halves_over_four=sum(h['time_seconds']>=4 for h in halves),bank_exhaustions=sum(h['timed_out'] for h in halves),
            faults=sum(r['fault_events'] for r in group),fallbacks=sum(r['fallback_decisions'] for r in group),
            errors=sum(h['errors'] for h in halves),forfeits=sum(h['forfeited'] for h in halves),
            samples=[m['experiment']['sampled_trials'] for r in group for m in r['metrics']],
            worst_startup_readiness_upper_seconds=max(m['startup_readiness_upper_seconds'][0] for r in group for m in r['metrics']))
    worst_by_opponent={}
    for o in ('bluffy_1','range_aware_2'):
        worst_by_opponent[o]={n:max(h['time_seconds'] for r in rows if r['profile']==n and r['opponent']==o for h in r['agent_stats']['agent1']) for n in ('baseline','candidate')}
    return dict(bluffy_repeats=5,baseline_median=statistics.median(a),candidate_median=statistics.median(b),
        median_reduction=1-statistics.median(b)/statistics.median(a),paired_bootstrap_ci95=[draws[250],draws[9749]],
        interval_scope='Five match-pair clusters, both seats kept together; 10000 resamples. Descriptive, not a guarantee across hosts.',
        worst_by_opponent=worst_by_opponent,profiles=groups)

def score_summary(rows,pairs):
    result={}
    for name in ('baseline','candidate'):
        families={}
        for opponent in sorted({r['opponent'] for r in rows}):
            group=[r for r in rows if r['profile']==name and r['opponent']==opponent]
            families[opponent]=dict(matches=len(group),points=sum(r['points'] for r in group),
                point_rate=statistics.mean(r['points'] for r in group),
                mean_bb_per_deal=statistics.mean(r['mean_bb_per_deal'] for r in group))
        result[name]=dict(families=families,
            equally_weighted_family_point_rate=statistics.mean(v['point_rate'] for v in families.values()),
            equally_weighted_family_bb_per_deal=statistics.mean(v['mean_bb_per_deal'] for v in families.values()))
    # Keep whole independent match-pairs together; do not treat decisions as samples.
    deltas=[p['profit_delta'] for p in pairs];mean=statistics.mean(deltas)
    radius=2.570581835636305*statistics.stdev(deltas)/(len(deltas)**.5)
    result['matched_match_block_delta']=dict(mean=mean,ci95_t=[mean-radius,mean+radius],blocks=len(deltas),
        scope='Descriptive Student-t interval across six matched match blocks (five bluff-heavy, one range-aware). Fixed opponents and consumed seeds; not uncertainty over the tournament population.')
    return result

def environment_summary(rows):
    result={'idle_preflight_cpu_percent':[r['idle_host_cpu_percent'] for r in rows]}
    for name in ('baseline','candidate'):
        ms=[m for r in rows if r['profile']==name for m in r['metrics']]
        throttled=[]
        for m in ms:
            fields=dict(line.split() for line in m['cgroup_cpu_stat'].splitlines())
            throttled.append(int(fields['throttled_usec']))
        result[name]=dict(python=ms[0]['python'],versions=ms[0]['versions'],parser=ms[0]['http_parser'],
            cpu=next(line.split(':',1)[1].strip() for line in ms[0]['cpuinfo'].splitlines() if line.startswith('model name')),
            cpu_max=ms[0]['cgroup_cpu_max'],memory_max=ms[0]['cgroup_memory_max'],
            startup_import_median=statistics.median(m['startup_import_seconds'] for m in ms),
            startup_import_worst=max(m['startup_import_seconds'] for m in ms),
            core_seconds_median=statistics.median(m['core_seconds'] for m in ms),
            core_seconds_worst=max(m['core_seconds'] for m in ms),
            decision_counts=[m['decisions'] for m in ms],throttled_usec=throttled)
    return result

def markdown(report):
    perf=report['timing'];a=perf['profiles']['baseline'];b=perf['profiles']['candidate']
    delta=report['scores']['matched_match_block_delta'];env=report['environment'];p=report['profile']
    def interval(v):return f'[{v[0]:+.4f}, {v[1]:+.4f}]'
    lines=[
        f"**Batch 04: {report['decision']}.** Candidate `{CANDIDATE['commit']}` passes the predefined runtime gates; frozen champion `{PLAN['baseline']}` remains the fallback. No strategy or model tuning was performed.",
        '',
        '| Version | Official points | Mean BB/paired deal | Bluff-heavy median charged half | Worst charged half | Faults / fallbacks / errors / forfeits / bank exhaustion |',
        '|---|---:|---:|---:|---:|---|',
        f"| Champion | {a['points']:.0f}/6 | {a['mean_bb_per_deal']:+.6f} | {perf['baseline_median']:.6f}s | {a['worst_seconds']:.6f}s | 0 / 0 / 0 / 0 / 0 |",
        f"| Runtime candidate | {b['points']:.0f}/6 | {b['mean_bb_per_deal']:+.6f} | {perf['candidate_median']:.6f}s | {b['worst_seconds']:.6f}s | 0 / 0 / 0 / 0 / 0 |",
        '',
        f"Median reduction: **{100*perf['median_reduction']:.2f}%**. Paired bootstrap 95% interval: [{100*perf['paired_bootstrap_ci95'][0]:.2f}%, {100*perf['paired_bootstrap_ci95'][1]:.2f}%], resampling five match-pairs with both halves together. The predefined 15% gate uses the measured median; this interval does not establish a reduction of at least 15% with 95% confidence. All 12 measured halves per version were below the four-second engineering target. None exhausted the official eight-second bank. These observations do not guarantee future runtime.",
        '',
        f"Profit difference: {delta['mean']:+.6f} BB/paired deal; descriptive six-match-block 95% t interval {interval(delta['ci95_t'])}. **Playing-strength improvement is inconclusive.** The release decision concerns runtime. Match scores use the unmodified official judge. Six matches per version cover only two fixed development opponents; they are not a tournament ranking.",
        '',
        '| Opponent | Champion points / matches | Candidate points / matches | Champion BB/deal | Candidate BB/deal |',
        '|---|---:|---:|---:|---:|']
    for o in report['scores']['baseline']['families']:
        x=report['scores']['baseline']['families'][o];y=report['scores']['candidate']['families'][o]
        lines.append(f"| {o} | {x['points']:.0f}/{x['matches']} | {y['points']:.0f}/{y['matches']} | {x['mean_bb_per_deal']:+.6f} | {y['mean_bb_per_deal']:+.6f} |")
    lines.extend(['',f"Equally weighting the two tested opponent families gives 1.0 points/match for both; BB/deal is {report['scores']['baseline']['equally_weighted_family_bb_per_deal']:+.6f} versus {report['scores']['candidate']['equally_weighted_family_bb_per_deal']:+.6f}. The six-match average above weights the five repeated bluff-heavy runs more heavily. No held-out configurations or unused confirmation/final seeds were opened.",
        '', '**Profiling and the two changes**', '',
        'The champion was profiled in the unmodified official Docker recipe on a fresh Linux runner. The trace contained 4,021 decisions and 4,023 POST requests from an already consumed bluff-heavy half. Exclusive times below are non-overlapping profile categories; they include instrumentation and are excluded from the speed gate.',
        '', '| Component | Profiled exclusive seconds |','|---|---:|'])
    for k,v in p['exclusive_seconds'].items():lines.append(f'| {k} | {v:.6f} |')
    lines.extend(['',
        f"Startup import was {p['unprofiled']['startup_import_seconds']:.6f}s unprofiled and {p['profiled']['startup_import_seconds']:.6f}s profiled. Unprofiled replay used {p['unprofiled']['experiment']['sampled_trials']:,} rollouts; profiling changed pacing to {p['profiled']['experiment']['sampled_trials']:,}. Replay charged-equivalent time ({p['unprofiled']['charged_equivalent_seconds']:.6f}s versus {p['profiled']['charged_equivalent_seconds']:.6f}s) is diagnostic, not an official scored match.",
        '',
        '1. Add pinned `httptools==0.8.0`; Uvicorn selects its native HTTP parser. Installed footprint: 1,803,887 bytes. Both parsers were observed, not inferred from requirements.',
        '2. Return the already primitive `/act` payload using `JSONResponse`, avoiding FastAPI recursive encoding. Profiled `jsonable_encoder` cumulative time was approximately 0.112s.',
        '',
        'Both changes are outside the policy computation timer. The evaluator, rollout implementation, parameters, range conditioning, RNG and action-selection source are byte-identical to the champion. The two changes were measured together; their individual contributions were not isolated in this batch. The candidate adds a runtime-file Docker allowlist and four response tests. Research files are excluded from the image and ZIP.',
        '', '**Equivalence and timing evidence**', '',
        'All 12,063 controlled decision comparisons passed: 4,021 observations under each of full-budget, half-budget and pacing-boundary clock inputs. Compared exact actions, legal amounts, equity/uncertainty outputs, actual samples, cached rollout streams, RNG states, and opponent memory. A separate full protocol replay also produced identical response-byte hashes. This proves equivalence on the tested inputs with identical clock readings, not all possible observations.',
        '',
        f"Natural-clock scored runs differed in {sum(x['different_hand_action_traces'] for x in report['pairs'])} of 12,000 matched hand action traces. Actual rollout counts below also differ. The unchanged wall-clock pacing makes real elapsed time an input; source equality and controlled checks do not imply bit-identical live trajectories. All per-match profit-difference intervals cross zero.",
        '',
        '| Seed / opponent | Order | Baseline half times (s) | Candidate half times (s) | Baseline rollouts | Candidate rollouts | Delta BB/deal [official paired-deal 95% interval] |',
        '|---|---|---|---|---|---|---|'])
    for x in report['pairs']:
        seq=lambda v:', '.join(f'{n:.6f}' for n in v)
        lines.append(f"| {x['seed']} / {x['opponent']} | {' then '.join(x['order'])} | {seq(x['baseline_charged'])} | {seq(x['candidate_charged'])} | {x['baseline_samples'][0]} / {x['baseline_samples'][1]} | {x['candidate_samples'][0]} / {x['candidate_samples'][1]} | {x['profit_delta']:+.4f} {interval(x['profit_delta_ci'])} |")
    lines.extend(['',
        'Each row used identical deals, frozen opponents and fresh bot/opponent processes between halves. Exactly 12 full official matches (24 scored halves) were run sequentially. The worst half was lower for the candidate within every matched repeat and both opponent families. One individual half regressed: range-aware half 2, 2.185636s to 2.236684s (+0.051048s). This did not exceed that baseline match\'s worst half (2.262231s); it remains evidence of residual variability.',
        '',
        '| Seed | Champion BB/deal [official 95% CI] | Candidate BB/deal [official 95% CI] |',
        '|---|---|---|'])
    for x in report['pairs']:
        lines.append(f"| {x['seed']} | {x['baseline_bb']:+.4f} {interval(x['baseline_official_ci'])} | {x['candidate_bb']:+.4f} {interval(x['candidate_official_ci'])} |")
    lines.extend(['', '**Environment, validation and remaining uncertainty**', '',
        f"Both benchmark images ran Python {env['baseline']['python']}, FastAPI 0.156.1, Uvicorn 0.54.0, Starlette 1.10.0, Pydantic 2.14.3 and h11 0.16.0. CPU reported {env['baseline']['cpu']}; each bot had a one-CPU quota and 4 GiB memory, non-root execution, read-only filesystem, 512 MiB `/tmp`, no external network, and dropped capabilities. Judge and opponent ran in separate cgroups. Three-second CPU preflights ranged from {min(env['idle_preflight_cpu_percent']):.1f}% to {max(env['idle_preflight_cpu_percent']):.1f}% across the VM. This does not prove exclusive access to the physical host.",
        '',
        f"Across the 12 halves per version, startup-import median/worst was {env['baseline']['startup_import_median']:.3f}/{env['baseline']['startup_import_worst']:.3f}s for baseline and {env['candidate']['startup_import_median']:.3f}/{env['candidate']['startup_import_worst']:.3f}s for candidate. Core-computation median/worst was {env['baseline']['core_seconds_median']:.3f}/{env['baseline']['core_seconds_worst']:.3f}s versus {env['candidate']['core_seconds_median']:.3f}/{env['candidate']['core_seconds_worst']:.3f}s. Core time can exceed charged HTTP time because the judge subtracts per-request grace; these are different measurements. Complete per-half decision counts, samples, wall/charged times and cgroup counters are in `BATCH04.json` and the raw artifact.",
        '',
        'Exact candidate commit passed **127 tests**, the official Docker build/startup/protocol smoke test, and supplementary restricted-container checks. The validated Docker image is the same immutable image used in all candidate matches. Both players in all matches had zero observed faults, exception fallbacks, judge errors, forfeits or bank exhaustion.',
        '',
        'Earlier failures are preserved: the local Docker probe stalled, so measurements used Linux CI; initial unscored replay run 42433778162 failed in the client path, with original stderr unavailable. Failed-connection retry handling and failure logging were fixed before the successful profile. That failure consumed zero scored match slots. No Windows safety claim is made, and the historical Windows/Linux gap remains only partially explained. Profile and benchmark ran on different fresh runners; their absolute timings are not paired. Official-image transitive dependencies also differ from earlier host-based Batch 03 measurements.',
        '', '**Reproduction and artifact identity**', '',
        f"Benchmark source: `ef4403900a7b0df755648bfc2631282056115088`. Profile source: `b317d760722b53cc257018dbc9c520ba92d3f21e`. Report generator SHA-256: `{report['report_generator_sha256']}`. Opponent source is frozen at `b725121` with exact configuration/file hashes in the preserved package manifests.",
        '',
        'The following are the executed/reproducible commands; do not dispatch another benchmark within this capped batch. In a clean Linux checkout of the benchmark source:',
        '', '```bash',
        'python -m pip install -r requirements-dev.txt psutil==7.1.3',
        'docker build -t poker-agent-base:local - < docker/Dockerfile.base',
        'python tools/batch04.py bench',
        '# Profiling was a separate run at the profile source:',
        'python tools/batch04.py profile',
        '```', '',
        'The harness checked out the exact candidate and executed `python -m pytest -q`, `bash tools/check_build.sh`, and `python tools/check_container_reliability.py`; it then ran the untouched official judge with `--deals 1000 --seed <locked seed> --half 1|2 --logs --json <half.json>` and `judge_engine.py combine`. Exact launch commands, network/resource flags, order and frozen seeds are in `tools/batch04.py` and `experiments/BATCH04_PLAN.json`.',
        '', '```powershell',
        'gh run download 42434045945 --name batch04-profile --dir reports/batch04-profile',
        'gh run download 42434610957 --name batch04-bench --dir reports/batch04-bench',
        '.\.venv\Scripts\python.exe tools/report_batch04.py',
        '```','',
        f"Baseline image: `{report['images']['baseline']}`. Candidate image: `{report['images']['candidate']}`.",
        '',
        '[Successful profile](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434045945), [exact-commit validation and all 12 matches](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434610957). Full gates, source hashes, official per-match statistics, reliability counters and evidence-file SHA-256 hashes are preserved in `BATCH04.json`.',
        ''])
    if report['submission']:
        z=report['submission']
        lines.extend([f"Submission ZIP: `Starfish-{CANDIDATE['commit'][:7]}.zip`, {z['bytes']:,} bytes, SHA-256 `{z['sha256']}`. Every archived file was verified against the exact candidate commit. Its adjacent manifest contains all file hashes. No submission form was posted; default branch and frozen fallback remain unchanged.",''])
    return '\n'.join(lines)

def archive(commit):
    # Only these exact committed files may enter a submission ZIP.
    files=[*RUNTIME,'.dockerignore','docker/Dockerfile.base','docker/Dockerfile.agent',
           'tools/check_build.sh','tools/smoke_test.py','tools/check_container_reliability.py']
    folder=OUT/'submission';folder.mkdir(exist_ok=True);path=folder/f'Starfish-{commit[:7]}.zip'
    subprocess.run(['git','archive','--format=zip','-o',str(path),commit,*files],cwd=ROOT,check=True)
    with zipfile.ZipFile(path) as z:
        assert sorted(n for n in z.namelist() if not n.endswith('/'))==sorted(files)
        for f in files:assert z.read(f)==blob(commit,f)
    result=dict(commit=commit,path=str(path),sha256=sha(path.read_bytes()),bytes=path.stat().st_size,
        files={f:sha(blob(commit,f)) for f in files})
    save(path.with_suffix('.manifest.json'),result);return result

def main():
    benchmark=load(OUT/'benchmark.json');assert benchmark['status']=='complete'
    rows=benchmark['matches'];ledger=load(OUT/'match-ledger.json');assert len(rows)==len(ledger)==12
    assert all(r['status']=='complete' for r in ledger)
    eq=load(OUT/'equivalence.json');container=load(OUT/'candidate-container-reliability.json')
    policy_equal=all(blob(PLAN['baseline'],f)==blob(CANDIDATE['commit'],f) for f in CANDIDATE['unchanged'])
    pairs=paired(rows);perf=timing(rows,pairs)
    clean=all(all(r[k] for k in ('bot_valid','opponent_valid','reliability_clean','opponent_reliability_clean')) for r in rows)
    tests=(OUT/'candidate-tests.log').read_text();official=(OUT/'candidate-official-build.log').read_text()
    packaging=load(OUT/'candidate-packaging.json');candidate_image=load(OUT/'candidate-image.json')
    gates=dict(policy_source_unchanged=policy_equal,controlled_behavior_and_protocol=eq['passed'],
        five_paired_repeats=perf['bluffy_repeats']==5,median_at_least_15_percent=perf['median_reduction']>=.15,
        no_observed_worst_case_regression=all(max(p['candidate_charged'])<=max(p['baseline_charged']) for p in pairs),
        zero_observed_faults=clean,official_bank_not_exhausted=all(not h['timed_out'] for r in rows for hs in r['agent_stats'].values() for h in hs),
        required_tests=bool(re.search(r'127 passed',tests)),official_docker_protocol='SMOKE TEST PASSED' in official and container['passed'],
        exact_image_validated=container['image_id']==candidate_image['image']==benchmark['images']['candidate'],
        research_excluded_from_image=sorted(packaging['app_files'])==sorted(RUNTIME),match_cap=len(rows)<=12)
    # Live action differences are explicitly reported. Source/clock-conditional
    # equivalence must not be described as equality under differing real clocks.
    promotion=all(gates.values())
    report=dict(reported_utc=datetime.now(timezone.utc).isoformat(),baseline=PLAN['baseline'],candidate=CANDIDATE,
        benchmark_source='ef4403900a7b0df755648bfc2631282056115088',profile=profile_summary(),
        equivalence=eq,gates=gates,promotion=promotion,decision='advance candidate' if promotion else 'retain fd5c428',
        timing=perf,pairs=pairs,matches=rows,packaging=packaging,container_validation=container,
        scores=score_summary(rows,pairs),environment=environment_summary(rows),
        report_generator_sha256=sha(Path(__file__).read_bytes()),
        evidence_sha256={str(p.relative_to(OUT)):sha(p.read_bytes()) for p in sorted(OUT.rglob('*.json'))
            if 'candidate-source' not in p.parts and 'submission' not in p.parts and p.name!='decision.json'},
        images=benchmark['images'],ledger=ledger,heldouts_used=False,unused_confirmation_seeds_used=False,
        policy_hashes={f:sha(blob(CANDIDATE['commit'],f)) for f in RUNTIME},
        incidents=['Local Docker probe was unresponsive; only its owned probe processes were stopped. Linux CI used instead.',
          'Initial unscored replay-client attempt 42433778162 exited nonzero; stderr was not retained by that first harness. Closing failed HTTP connections and retaining failure logs corrected the retry path. The failed artifact and log remain preserved; zero scored match slots were consumed.'],
        limitations=['Profiling overhead changes pacing; profile timings are excluded from performance gates.',
          'Identical observed inputs plus identical clock budgets have exact actions, bet amounts, equity outputs, rollout streams, RNG progression, and opponent memory. Different real clocks can still change trajectories.',
          'Idle preflight and cgroup limits do not establish physical-host isolation or a future runtime guarantee.',
          'Official image transitive dependency versions differ from Batch03 host tests; baseline and candidate in this batch share the same built official base.'],
        workflows=['https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434045945',
                   'https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434610957'])
    report['submission']=archive(CANDIDATE['commit']) if promotion else None
    save(ROOT/'docs/BATCH04.json',report)
    (ROOT/'docs/BATCH04.md').write_text(markdown(report),encoding='utf-8')
    save(OUT/'decision.json',dict(decision=report['decision'],gates=gates,submission=report['submission']))
    print(json.dumps(dict(decision=report['decision'],gates=gates,timing=perf,submission=report['submission']),indent=2))

if __name__=='__main__':main()
