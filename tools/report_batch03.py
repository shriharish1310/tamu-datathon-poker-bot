"""Preserve official verdicts plus explicitly exploratory paired uncertainty."""
from collections import defaultdict
from datetime import datetime,timezone
import hashlib,json,math,random,re,statistics,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.adversarial_batch import save
OUT=ROOT/'reports/batch03'


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def matched(root,phase,profile,rows):
    seeds=sorted({r['seed'] for r in rows});opps=sorted({r['opponent'] for r in rows})
    blocks=[];seedmeans=[]
    for seed in seeds:
        vectors=[]
        for opp in opps:
            a=load(root/phase/f'{profile}_{opp}_{seed}.json')['paired_bb']
            b=load(root/phase/f'raw_{opp}_{seed}.json')['paired_bb']
            vectors.append([x-y for x,y in zip(a,b)])
        means=[statistics.mean(v[i] for v in vectors) for i in range(len(vectors[0]))]
        seedmeans.append(statistics.mean(means))
        blocks += [statistics.mean(means[i:i+100]) for i in range(0,len(means),100)]
    rng=random.Random(20917);draws=sorted(statistics.mean(rng.choices(blocks,k=len(blocks))) for _ in range(5000))
    center=statistics.mean(seedmeans)
    if len(seedmeans)==2:
        radius=math.tan(math.pi*.475)*statistics.stdev(seedmeans)/math.sqrt(2)
        seed_ci=[center-radius,center+radius]
    else:seed_ci=None
    return dict(mean=center,block_ci95=[draws[125],draws[4874]],independent_seed_means=seedmeans,
        independent_seed_t_ci95=seed_ci,method='100-deal paired block bootstrap, seats/opponents kept together, 5000 resamples',
        caveat='Development evidence only; adaptation crosses blocks, only two seeds. Seed-level interval is the conservative generalization diagnostic.')


def compact_match(r):
    result={k:v for k,v in r.items() if k not in ('cpu','reliability_halves')}
    result['background_preflight_cores']=r['cpu']['preflight']['background_process_cores']
    result['idle_preflight']=r['cpu']['idle_preflight']
    result['background_during_mean_cores']=statistics.mean(s['background_process_cores'] for s in r['cpu']['samples'])
    result['background_during_max_cores']=max(s['background_process_cores'] for s in r['cpu']['samples'])
    result['opponent_fault_events']=sum(h['opponent_diagnostics']['fault_events'] for h in r['reliability_halves'])
    result['opponent_fallback_decisions']=sum(h['opponent_diagnostics']['fallback_decisions'] for h in r['reliability_halves'])
    return result


def comparison(root,phase):
    data=load(root/(phase+'-summary.json'))
    if data['status']!='complete':return data
    rows=data['matches'];summary=[]
    for name in ('raw','observed','hybrid'):
        group=[r for r in rows if r['profile']==name]
        if not group:continue
        opponents={o:dict(points=sum(r['points'] for r in group if r['opponent']==o),
            bb_per_deal=statistics.mean(r['mean_bb_per_deal'] for r in group if r['opponent']==o),
            official_ci=[r['ci'] for r in group if r['opponent']==o]) for o in dict.fromkeys(r['opponent'] for r in group)}
        halves=[h for r in group for h in r['agent_stats']['agent1']]
        metrics=[m for r in group for m in r['metrics']]
        startups=[]
        for r in group:
            log=(root/phase/f'{name}_{r["opponent"]}_{r["seed"]}.runner.log').read_text()
            startups += [float(s) for s in re.findall(r'server=batch03_audit_server.*?startup=([0-9.]+)s',log)]
        summary.append(dict(profile=name,matches=len(group),points=sum(r['points'] for r in group),
            bb_per_deal=statistics.mean(r['mean_bb_per_deal'] for r in group),by_opponent=opponents,
            worst_match=min(r['mean_bb_per_deal'] for r in group),worst_charged_half=max(h['time_seconds'] for h in halves),
            over_four_seconds=sum(h['time_seconds']>=4 for h in halves),
            matched_delta=None if name=='raw' else matched(root,phase,name,rows),
            counters={**{k:sum(r[k] for r in group) for k in ('fault_events','fallback_decisions','log_fault_events')},
                      **{k:sum(h[k] for h in halves) for k in ('errors','forfeited','timed_out','skipped_calls')}},
            gates_passed=all(r['gate_passed'] for r in group),
            model_states=sum(m['model_states'] for m in metrics),ood_mc_routes=sum(m['ood_mc_routes'] for m in metrics),
            inference_seconds=sum(m['inference_seconds'] for m in metrics),
            worst_startup_seconds=max(startups),
            worst_model_load_seconds=max((m['model_load_seconds'] for m in metrics),default=0),
            actual_trials_by_street=[sum(m['actual_trials'][i] for m in metrics) for i in range(4)] if metrics else None,
            actual_trials_total=sum(sum(m['actual_trials']) for m in metrics) if metrics else
                sum(m['experiment']['sampled_trials'] for r in group for m in r['original_counters'])))
    return dict(status='complete',summary=summary,matches=[compact_match(r) for r in rows],paired_deltas=data['paired_deltas'])


def runtime(root):
    data=load(root/'runtime-summary.json');rows=data['matches'];halves=[]
    for r in rows:
        for i,h in enumerate(r['agent_stats']['agent1']):
            c=r['original_counters'][i];m=r['metrics'][i] if r['metrics'] else None
            halves.append(dict(profile=r['profile'],seed=r['seed'],half=i+1,calls=h['calls'],
                decisions=c['decisions'],actual_samples=c['experiment']['sampled_trials'],
                core_wall=c['core_wall_seconds'],core_cpu=None if m is None else m['core_cpu_seconds'],
                http_wall=h['wall_seconds'],charged=h['time_seconds'],
                nonpolicy_http_wall=h['wall_seconds']-c['core_wall_seconds'],
                sample_hist=None if m is None else m['sample_hist'],
                background_preflight_cores=r['cpu']['preflight']['background_process_cores'],
                background_mean_cores=statistics.mean(x['background_process_cores'] for x in r['cpu']['samples'])))
    instrumentation=[]
    for seed in sorted({r['seed'] for r in rows}):
        raw=load(root/'runtime'/f'raw_bluffy_1_{seed}.json');obs=load(root/'runtime'/f'observed_bluffy_1_{seed}.json')
        changes=sum(a['actions']!=b['actions'] for half in ('half1','half2') for a,b in zip(raw['logs'][half],obs['logs'][half]))
        instrumentation.append(dict(seed=seed,hands_with_different_action_trace=changes,played_hands=2000,
            caveat='Observed/raw difference combines measurement overhead with timing jitter; neither is separately identified.',
            bb_per_deal_difference=obs['mean_bb_per_deal']-raw['mean_bb_per_deal']))
    micro=load(root/'microbench.json');fixed={}
    for mode in ('model',0,1,2,3):
        group=[r for r in micro if r['mode']==mode]
        fixed[str(mode)]={k:statistics.median(r[k]/r['states']*1e6 for r in group) for k in ('wall_seconds','cpu_seconds')}
    return dict(environment=load(root/'environment.json'),halves=halves,instrumentation=instrumentation,
        fixed_work_us_per_state=fixed,matches=[compact_match(r) for r in rows])


def markdown(report,chosen):
    lines=['# Batch 03: runtime diagnosis and preflop-only learned equity','',
        '**Champion remains `range_130_budget25` at `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.**',
        f'Hybrid decision: **{report["hybrid_decision"]}**. All matches are development-only; the 12 held-out configurations and final holdout seeds remain unused.',
        '', '## Official comparison','',
        'Primary environment: fresh Linux runner, Python 3.10.11, h11. Models were selected using estimator-selection data before estimator-test or match results.',
        'All policies use matched deals, fixed opponents, interleaved order, and fresh processes between halves. Points are official verdict points, equally weighted across opponents.',
        '', '| Policy | Points | BB/paired deal | Matched delta [95% block CI] | Worst charged half | Faults / exception fallbacks / errors / forfeits / timeouts |',
        '|---|---:|---:|---|---:|---|']
    for r in chosen['summary']:
        d=r['matched_delta'];delta='reference' if d is None else f'{d["mean"]:+.4f} [{d["block_ci95"][0]:+.4f}, {d["block_ci95"][1]:+.4f}]'
        c=r['counters'];counts='/'.join(str(c[k]) for k in ('fault_events','fallback_decisions','errors','forfeited','timed_out'))
        lines.append(f'| {r["profile"]} | {r["points"]:g}/{r["matches"]} | {r["bb_per_deal"]:+.4f} | {delta} | {r["worst_charged_half"]:.3f}s | {counts} |')
    if report['confirmation']['status']!='complete':
        lines += ['', 'Six-family confirmation was not justified by the predefined screen gate; no confirmation seeds were consumed.']
    lines += ['', 'The block intervals are exploratory. Only two independent seeds were used; adaptation crosses block boundaries. The wider two-seed Student-t interval and each official per-match CI are preserved in [BATCH03.json](BATCH03.json).',
        '', '| Opponent | Exact champion points / BB per deal | Instrumented champion points / BB per deal | Hybrid points / BB per deal |', '|---|---|---|---|']
    for o in chosen['summary'][0]['by_opponent']:
        cells=[]
        for r in chosen['summary']:
            v=r['by_opponent'][o];cells.append(f'{v["points"]:g} / {v["bb_per_deal"]:+.4f}')
        lines.append('| '+o+' | '+' | '.join(cells)+' |')
    lines += ['', '## Runtime evidence','',
        'The earlier 6.278s Windows and 2.113s Linux maxima used different opponent pools and Python versions. They were not a controlled operating-system comparison. Request counts were nevertheless similar: Windows had 3,973 calls and 10.244636s HTTP wall time; Linux had 3,948 calls and 6.060094s HTTP wall time. Historical actual samples and core times were not captured, so the original gap cannot be causally reconstructed.',
        'This batch repeats the same three seeds against frozen bluffy_1, interleaving exact and instrumented champion. Linux comparisons run sequentially before any container builds. Windows background load failed the idle preflight, so those measurements are diagnostic only.',
        '', '| Environment, exact champion | Charged half range | Policy wall-time range | Actual rollouts/half | Decisions/half |', '|---|---:|---:|---:|---:|']
    for name in ('windows','linux310','linux312'):
        halves=[h for h in report[name]['halves'] if h['profile']=='raw']
        def span(k,fmt):return format(min(h[k] for h in halves),fmt)+'–'+format(max(h[k] for h in halves),fmt)
        lines.append(f'| {name} | {span("charged",".3f")}s | {span("core_wall",".3f")}s | {span("actual_samples","d")} | {span("decisions","d")} |')
    lines += ['', 'Configured rollout counts remain 24/32/40/64. Wall-clock pacing halves those budgets when ahead of allowance; the detailed report includes actual sample histograms. Preflop model savings can change subsequent pacing even though postflop source is identical.',
        'The read-only exact-control probe runs after all charged requests. Instrumented controls add counters/CPU timers; their changed action trajectories are measured separately. Core CPU time is available for instrumented controls; original core wall time and total actual samples are available for exact champion.',
        'HTTP wall minus policy wall includes serialization, server/client handling, scheduling, callbacks, and transport. It is not pure network latency. Official charged time subtracts at most 1ms per request, so it must not be equated with core time.',
        'Eight charged seconds is the official limit; four seconds is our engineering target. Repeated Linux host results are not a guarantee under tournament container CPU quotas, physical-host contention, or other platforms.',
        '', '### Parser ablation','', '| Forced parser, same Linux Python 3.10 host | Charged half range | Mean charged half |', '|---|---:|---:|']
    for parser in ('h11','httptools'):
        values=[h['time_seconds'] for r in report['parser_ablation']['matches'] if r['forced_http_parser']==parser for h in r['agent_stats']['agent1']]
        lines.append(f'| {parser} | {min(values):.3f}–{max(values):.3f}s | {statistics.mean(values):.3f}s |')
    lines += ['', 'Parser order is h11/httptools, httptools/h11, h11/httptools across the three seeds. CPU clock/thermal state, core scheduling on the Windows laptop, transient background activity, and cloud physical-host contention were not individually controlled. These remain possible contributors, not proven causes.',
        '', '## Estimator quantity and calibration','',
        'The model predicts preflop showdown equity against uniformly sampled legal opponent holdings and runouts. It is used only when both range_mix and caller_power are zero. Positive range weights always materialize the original seeded Monte Carlo stream. The same is true for an out-of-support prediction; that bounded route has its own counter and is not an exception fallback.',
        'The unchanged policy receives the predicted mean with its existing virtual n=12 or n=24 shrinkage count. This is not a claim that model predictions used those rollouts. Value-gate uncertainty is max(0.025, sqrt(p(1-p)/(n-1))); it is a conservative proxy, not a measured Monte Carlo SE for the model. Actual simulated trials and virtual counts are logged separately.',
        'Train/selection/test contain 6,000/1,000/1,000 disjoint canonical five-card configurations. Canonicalization takes the minimum hand over all 24 suit permutations. Official-evaluator labels use 256/1,024/2,048 rollouts per state. Opponent holdings are sampled from the full legal space, without filtering on showdown participation.',
        'MLP: 55 features, one 32-ReLU hidden layer, Adam, alpha=.03, learning rate=.002, max_iter=200, early stopping, random_state=3107. Tree: 12 ExtraTrees, depth 10, min leaf 5, one training thread, same random state. Selection criterion was independent selection RMSE; only the selected MLP entered match screening.',
        '', '| Range mix / power | Label mean MC SE | MC12 RMSE | MC24 RMSE | MLP hybrid RMSE | Tree hybrid RMSE | Hybrid bias / ECE | Route |', '|---|---:|---:|---:|---:|---:|---:|---|']
    for key,v in report['estimator']['by_range'].items():
        h=v['MLP32_hybrid'];ece=sum(b['n']*abs(b['prediction']-b['label']) for b in h['calibration'])/h['n']
        lines.append(f'| {key} | {v["mean_label_se"]:.4f} | {v["MC12"]["rmse"]:.4f} | {v["MC24"]["rmse"]:.4f} | {h["rmse"]:.4f} | {v["ExtraTrees12_depth10_hybrid"]["rmse"]:.4f} | {h["bias"]:+.4f} / {ece:.4f} | {h["route"]} |')
    lines += ['', 'Nonzero-range rows measure retained simulation, not learned range-conditioned accuracy. ECE is the sample-weighted absolute gap between mean predictions and mean labels in fixed 0.1-wide bins. Calibration bins and boundary disagreements by range are in BATCH03.json. Boundary probes exclude labels whose 95% MC interval overlaps the threshold; small tail groups are descriptive only and are not evidence of action regret.',
        '', '### Feature extraction, inference, and startup','']
    for name in ('MLP32','ExtraTrees12_depth10','MC24'):
        values=[r['microseconds_per_state'] for r in report['estimator']['timings'] if r['name']==name]
        lines.append(f'- {name}: {statistics.median(values):.1f} microseconds/state, median of three interleaved local passes; local load is not claimed isolated.')
    for r in chosen['summary']:
        lines.append(f'- {r["profile"]}: worst server startup {r["worst_startup_seconds"]:.3f}s; worst model-file load {r["worst_model_load_seconds"]:.6f}s; model states {r["model_states"]}; OOD Monte Carlo routes {r["ood_mc_routes"]}.')
    lines += ['', '## Reproduction and preserved evidence','',
        f'- Policy/model experiment source: `{report["policy_source"]}`.',
        f'- Parser diagnostic source: `{report["parser_source"]}`.',
        f'- Selected model SHA-256 (canonical LF): `{report["canonical_model_sha256"]}`.',
        f'- Tree checkpoint SHA-256 (canonical LF): `{report["model_checkpoints"]["ExtraTrees12_depth10"]["canonical_sha256"]}`; preserved in experiments/batch03_tree_weights.json, not match-screened.',
        f'- Label artifact SHA-256: `{report["labels_sha256"]}`.',
        '- Full package hashes, dependency versions, official JSON CIs, reliability counters, startup logs, and CPU telemetry are retained under reports/batch03. Compact evidence is in BATCH03.json; reports/batch03/leaderboard.json is the resumable leaderboard.',
        '- Initial incomplete diagnostic attempts are preserved in reports/batch03-initial-audit-bug and CI 42429523850. The probe fix changed no policy or model. Earlier Batch02 timing failures remain untouched.',
        '', '```powershell',
        'python tools/batch03_train.py  # regenerate canonical-grouped labels and compare fixed model specifications',
        'python tools/batch03.py init  # recreate exact frozen packages and their hash lock',
        'python tools/run_local_match.py --agent-dir reports/batch03/packages/hybrid --opponent-dir reports/batch03/opponents/range_aware_2 --agent-module batch03_audit_server --collect-batch03-metrics --deals 1000 --seed b03-screen-23 --logs --require-opponent-diagnostics --output reports/replay/hybrid_range_aware_2_b03-screen-23.json',
        '```', '', 'Use Python 3.10.11 and experiments/batch03-runtime-requirements.txt for match reproduction. Label/model regeneration additionally uses numpy==2.0.1 and scikit-learn==1.5.1. Offline learning never loads held-out opponent configurations. Model loading occurs at server import, outside timed decisions.',
        'The phase orchestrator enforces the original batch end time; the explicit match command supports later reproduction without changing any frozen policy. Runtime differences can change pacing and therefore decisions despite identical deals.',
        '', 'No candidate was released. Exact fallback fd5c428 already passed official Docker build/smoke and container reliability checks in CI 42426541174. Any eventual changed submission commit still requires its own final Docker checks. No MCCFR, RL, or open-ended training was launched. The organizer deadline/timezone remains unverified.']
    (ROOT/'docs/BATCH03.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    linux=OUT/'linux310';other=OUT/'linux312';parser=OUT/'parser'
    screen=comparison(linux,'screen');confirm=comparison(linux,'confirm')
    chosen=confirm if confirm['status']=='complete' else screen
    raw=next(r for r in chosen['summary'] if r['profile']=='raw')
    hybrid=next(r for r in chosen['summary'] if r['profile']=='hybrid')
    delta=hybrid['matched_delta']
    if not hybrid['gates_passed'] or hybrid['points']<raw['points'] or (hybrid['points']==raw['points'] and delta['block_ci95'][1]<0):decision='reject'
    elif hybrid['points']>raw['points'] and delta['independent_seed_t_ci95'][0]>0:decision='retain for final held-out validation; not promoted'
    else:decision='inconclusive; retain champion'
    estimator=load(OUT/'estimator/summary.json')
    frozen=load(ROOT/'experiments/CHAMPION.json')['sha256']
    for name,expected in frozen.items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected
    assert subprocess.run(['git','diff','--quiet','b725121','--','experiments/opponents-heldout.json']).returncode==0
    previous=load(ROOT/'docs/BATCH02.json')
    historical={}
    for key,rows in [('linux',previous['exact_champion_linux']['matches']),
                     ('windows',[r for r in previous['confirmation']['matches'] if r['profile']=='champion'])]:
        value=max(((h['time_seconds'],r,i+1,h) for r in rows for i,h in enumerate(r['agent_stats']['agent1'])),key=lambda x:x[0])
        historical[key]=dict(opponent=value[1]['opponent'],seed=value[1]['seed'],half=value[2],official_stats=value[3],
            actual_samples=None,core_time=None,limitation='Not captured in historical run; cannot retrospectively attribute original timing gap')
    models={name:dict(canonical_sha256=hashlib.sha256((OUT/'estimator'/(name+'.json')).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        file_bytes=(OUT/'estimator'/(name+'.json')).stat().st_size) for name in ('MLP32','ExtraTrees12_depth10')}
    report=dict(started_utc=load(ROOT/'experiments/BATCH03_PLAN.json')['started_utc'],reported_utc=datetime.now(timezone.utc).isoformat(),
        champion='fd5c428475eee98edb7c38bd1e7fc0870ddbf42d',policy_source='82beb8f0f05588eb79124cc12b4a38f2498808dc',
        parser_source=subprocess.check_output(['git','rev-parse','87e85d3'],text=True).strip(),
        hybrid_decision=decision,champion_retained=True,heldout_configurations_used=False,final_holdout_seeds_used=False,
        protocol=load(ROOT/'experiments/BATCH03_PLAN.json'),estimator=estimator,model_checkpoints=models,
        historical_runtime=historical,
        windows=runtime(OUT),linux310=runtime(linux),linux312=runtime(other),
        parser_ablation={**load(parser/'PLAN.json'),'matches':[compact_match(r) for r in load(parser/'summary.json')['matches']]},
        screen=screen,confirmation=confirm,
        source_hashes=load(linux/'LOCK.json')['hashes'],
        canonical_model_sha256=hashlib.sha256((ROOT/'experiments/batch03_preflop_weights.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        labels_sha256=hashlib.sha256((OUT/'estimator/labels.json').read_bytes()).hexdigest(),
        preserved_incident='Initial audit probe read outer reliability memory and returned null core counters; attempts archived unchanged under reports/batch03-initial-audit-bug and CI 42429523850. Fixed probe reads CORE_KEY and rejects missing evidence; no policy/model retuning.',
        workflows=['https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42429741175',
                   'https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42430066403'],
        limitations=['Historical Windows 6.278 and Linux 2.113 were different opponent workloads and interpreter versions, not a controlled OS experiment.',
            'Windows runs failed idle-host preflight and are diagnostic only. Linux process counters do not establish physical hypervisor isolation.',
            'Wall-clock pacing changes sample counts and action trajectories, including under instrumentation.',
            'Conditional range queries retain noisy Monte Carlo; uniform-model accuracy does not establish range-conditioned learned accuracy.',
            'No final holdout or eventual new submission commit was released. Exact fd5c428 Docker checks already passed in CI 42426541174.'])
    groups=[report[k]['matches'] for k in ('windows','linux310','linux312')]
    groups += [report['screen']['matches'],report['parser_ablation']['matches']]
    matches=sum(groups,[])
    report['completed_match_count']=len(matches)
    report['played_hands']=sum(r['num_deals']*2 for r in matches)
    report['all_completed_matches_reliability_clean']=all(all(r[k] for k in ('bot_valid','opponent_valid','reliability_clean','opponent_reliability_clean')) for r in matches)
    report['worst_charged_half_either_agent']=max(h['time_seconds'] for r in matches for hs in r['agent_stats'].values() for h in hs)
    report['elapsed_minutes']=(datetime.fromisoformat(report['reported_utc'])-datetime.fromisoformat(report['started_utc'])).total_seconds()/60
    save(ROOT/'docs/BATCH03.json',report)
    save(OUT/'leaderboard.json',dict(champion=report['champion'],decision=decision,primary_environment='Linux Python3.10 h11',
                                  phase='confirm' if confirm['status']=='complete' else 'screen',rows=chosen['summary']))
    markdown(report,chosen)
    print(json.dumps(dict(decision=decision,rows=chosen['summary']),indent=2))

if __name__=='__main__':main()
