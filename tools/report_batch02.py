"""Official A/B outcomes and paired block uncertainty; no alternate ranking rule."""
from collections import defaultdict
from datetime import datetime,timezone
import hashlib,json,math,random,statistics,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.adversarial_batch import save
OUT=ROOT/'reports/batch02'


def pooled_delta(profile,rows):
    """Resample 100-deal blocks, preserving seats and all opponent correlations.

    Diagnostic interval only; official individual match intervals are retained
    separately. Two seeds and one policy family sample do not support universal
    generalization. All six opponents have equal weight.
    """
    seeds=sorted({r['seed'] for r in rows});opponents=sorted({r['opponent'] for r in rows})
    blocks=[];seed_means=[]
    for seed in seeds:
        vectors=[]
        for opp in opponents:
            parts=[]
            for half in (1,2):
                a=json.loads((OUT/'confirm'/f'{profile}_{opp}_{seed}.half{half}.json').read_text())['nets_agent1']
                b=json.loads((OUT/'confirm'/f'champion_{opp}_{seed}.half{half}.json').read_text())['nets_agent1']
                parts.append([x-y for x,y in zip(a,b)])
            vectors.append([(a+b)/2 for a,b in zip(*parts)])
        means=[statistics.mean(v[i] for v in vectors) for i in range(len(vectors[0]))]
        seed_means.append(statistics.mean(means))
        blocks.extend(statistics.mean(means[i:i+100]) for i in range(0,len(means),100))
    rng=random.Random(20917)
    draws=sorted(statistics.mean(rng.choices(blocks,k=len(blocks))) for _ in range(5000))
    # With only two independently generated match seeds, seed-level uncertainty
    # is much larger than within-seed block uncertainty. Expose both; never
    # equate a positive block interval with a generalization guarantee.
    assert len(seed_means)==2
    tcrit=math.tan(math.pi*(.975-.5))  # Student t with 1 degree of freedom
    radius=tcrit*statistics.stdev(seed_means)/math.sqrt(2)
    center=statistics.mean(seed_means)
    return {'mean':statistics.mean(blocks),'ci95':[draws[125],draws[4874]],'blocks':len(blocks),
            'independent_seed_means':seed_means,'independent_seed_t_ci95':[center-radius,center+radius],
            'method':'paired 100-deal block bootstrap, opponents averaged equally within deal; 5000 resamples',
            'limits':'Exploratory development interval; two seeds, no held-out opponent configurations.'}


def summary(rows,deltas):
    groups=defaultdict(list)
    for r in rows:groups[r['profile']].append(r)
    result=[];reference=sum(r['points'] for r in groups['champion'])
    for name,items in groups.items():
        byopp={opp:{'points':sum(r['points'] for r in items if r['opponent']==opp),
                    'bb_per_deal':statistics.mean(r['mean_bb_per_deal'] for r in items if r['opponent']==opp),
                    'individual_ci':[r['ci'] for r in items if r['opponent']==opp]}
               for opp in dict.fromkeys(r['opponent'] for r in items)}
        difference=None if name=='champion' else pooled_delta(name,rows)
        gates=all(r['gate_passed'] for r in items);points=sum(r['points'] for r in items)
        decision='retain frozen fallback'
        if name!='champion':
            if not gates or points<reference:decision='reject'
            elif points>reference:decision='retain for new final validation; observed point gain, not promoted'
            elif difference['ci95'][1]<0:decision='reject'
            elif difference['ci95'][0]>0:decision='retain for new final validation; not promoted'
            else:decision='inconclusive; do not promote'
        metrics=[m for r in items for m in r['research_metrics']]
        item={'profile':name,'points':points,'matches':len(items),'bb_per_deal':statistics.mean(r['mean_bb_per_deal'] for r in items),
              'paired_delta':difference,'by_opponent':byopp,'worst_match_bb_per_deal':min(r['mean_bb_per_deal'] for r in items),
              'worst_opponent':min(byopp,key=lambda o:byopp[o]['bb_per_deal']),
              'max_charged_half':max(r['max_time_seconds'] for r in items),'release_gates_passed':gates,'decision':decision,
              'halves_over_4s':sum(h['time_seconds']>=4 for r in items for h in r['agent_stats']['agent1']),
              'profit_generalization':'reference' if difference is None else 'inconclusive across two independent seed blocks',
              'counters':{k:sum(r[k] for r in items) for k in ('fault_events','fallback_decisions','log_fault_events')},
              'judge_errors':sum(h['errors'] for r in items for h in r['agent_stats']['agent1']),
              'timeouts':sum(h['timed_out'] for r in items for h in r['agent_stats']['agent1']),
              'forfeits':sum(h['forfeited'] for r in items for h in r['agent_stats']['agent1']),
              'research_metrics':metrics}
        if metrics:
            item['min_ess_fraction']=min(m['min_ess_fraction'] for m in metrics if m['weighted_queries']) if any(m['weighted_queries'] for m in metrics) else None
            item['ess_shrink_events']=sum(m['ess_shrink_events'] for m in metrics)
            modeled=sum(m['action_value_decisions'] for m in metrics);skipped=sum(m['action_budget_skips'] for m in metrics)
            item['action_model_decision_fraction']=modeled/(modeled+skipped) if modeled+skipped else None
        result.append(item)
    return result


def target_diagnostics(rows):
    """Exploratory matched target subset fixed by champion trajectory only.

    Candidate and champion evaluated on the same hand indices. This avoids
    selecting a different subgroup after the candidate changes the trajectory.
    Final outcomes remain associations, not decision-level causal estimates.
    """
    from game import Game,make_deal,Action
    groups=defaultdict(list)
    for r in rows:
        if r['profile']!='champion' or r['opponent']!='range_aware_2':continue
        report=json.loads((OUT/'confirm'/Path(r['report']).name).read_text())
        for half in (1,2):
            seat=half-1
            for hand in report['logs'][f'half{half}']:
                if seat==hand['button_seat']:continue
                i=hand['deal_index'];g=Game(make_deal(r['seed'],i),i%2,i);target=False
                for action in hand['actions']:
                    if g.to_act==seat:
                        obs=g.observation(seat)
                        prior=[e for e in obs.action_history if not e.is_me and e.street==obs.street and e.action in (Action.RAISE_HALF,Action.RAISE_POT)]
                        target|=(int(obs.street)==1 and obs.pot<20 and obs.to_call>0 and bool(prior) and prior[-1].action==Action.RAISE_POT)
                    g.apply(Action[action['action']])
                if target:groups[(r['seed'],half)].append(i)
    output={}
    for profile in dict.fromkeys(r['profile'] for r in rows):
        sums=[]
        for (seed,half),indices in groups.items():
            path=OUT/'confirm'/f'{profile}_range_aware_2_{seed}.half{half}.json'
            nets=json.loads(path.read_text())['nets_agent1'];sums.extend(nets[i]/2 for i in indices)
        output[profile]={'hands':len(sums),'net_bb':sum(sums),'mean_bb_per_hand':statistics.mean(sums) if sums else None}
    return {'definition':'Champion-defined BB flop facing pot bet with pot <10BB; matched hand indices across candidates',
            'interpretation':'Exploratory final-hand outcomes, not errors or action EV; no tuning on these confirmation slices.',
            'profiles':output}


def main():
    lock=json.loads((OUT/'confirmation-lock.json').read_text());screen=json.loads((OUT/'screen-summary.json').read_text())
    confirm=json.loads((OUT/'confirm-summary.json').read_text());assert confirm['status']=='complete'
    for path,hashes in lock['lock']['hashes'].items():
        for name,expected in hashes.items():assert hashlib.sha256((Path(path)/name).read_bytes()).hexdigest()==expected
    ranked=summary(confirm['matches'],confirm['paired_deltas'])
    pilot_path=OUT/'equity-pilot/summary.json';pilot=json.loads(pilot_path.read_text()) if pilot_path.exists() else None
    artifact=OUT/'champion-linux-exact'
    champion=json.loads((ROOT/'experiments/CHAMPION.json').read_text())
    for name,expected in champion['sha256'].items():
        assert hashlib.sha256((artifact/'linux-reliability/source'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected
    linux=json.loads((artifact/'linux-reliability/summary.json').read_text())
    container=json.loads((artifact/'container-reliability.json').read_text())
    assert linux['summary']['release_gates_passed'] and container['passed']
    report={'champion_commit':'fd5c428475eee98edb7c38bd1e7fc0870ddbf42d','champion_unchanged':True,
            'research_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'started_utc':'2026-11-07T23:20:36+00:00','reported_utc':datetime.now(timezone.utc).isoformat(),
            'deadline':'Unverified. User says 04:00 is a planning assumption only; no authoritative final freeze scheduled.',
            'configuration':json.loads((ROOT/'experiments/BATCH02_PLAN.json').read_text()),'selection':lock['selection'],
            'calibration':json.loads((OUT/'calibration.json').read_text()),'screen':screen,'confirmation':confirm,
            'comparison':ranked,'target_flop':target_diagnostics(confirm['matches']),
            'learned_equity_pilot':pilot,'heldout_opponent_configs_used':False,'final_holdout_used':False,
            'environment':json.loads((OUT/'environment.json').read_text()),
            'exact_champion_linux':{'workflow':'https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42426541174',
                'source_verified':True,'summary':linux['summary'],'matches':linux['matches'],'container':container}}
    save(ROOT/'docs/BATCH02.json',report)
    save(OUT/'leaderboard.json',{'status':'complete','comparison':ranked,'learned_equity_pilot':pilot})
    lines=['# Batch 02: independent range and action-value experiments','',
           '**Frozen fallback remains `range_130_budget25` at `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.**',
           'All evaluation is development-only; the 12 held-out configurations and final holdout seeds were untouched.',
           '', '## Comparison','',
           'Each confirmed profile played the same six fixed opponents on two predefined seeds: 12 matches / 24,000 hands.',
           'All matches use the official HTTP judge with fresh processes between halves. Points are equally weighted.',
           'Opponent order below: tight / loose / aggressive / selective / bluff-heavy / range-aware.',
           '', '| Policy | Configuration | Points / 12 | Mean BB/deal | Paired delta [95% block interval] | Points by opponent | BB/deal by opponent | Worst charged half | Faults/fallbacks/errors/timeouts/forfeits | Decision |',
           '|---|---|---:|---:|---|---|---|---:|---|---|']
    order=['tight_3','loose_2','aggressive_1','selective_2','bluffy_1','range_aware_2']
    for r in ranked:
        cfg=lock['lock'].get('configs',{}).get(r['profile'],{})
        desc='Frozen range 1.3, budget .25' if not cfg else (f'A blend {cfg["alpha"]}, shrink {cfg["shrink"]}' if not cfg['action_values'] else f'B z={cfg["uncertainty"]}, risk={cfg["risk_penalty"]}, .65s action budget')
        delta=r['paired_delta'];ds='reference' if delta is None else f'{delta["mean"]:+.4f} [{delta["ci95"][0]:+.4f}, {delta["ci95"][1]:+.4f}]'
        points=' / '.join(f'{r["by_opponent"][o]["points"]:g}' for o in order)
        profit=' / '.join(f'{r["by_opponent"][o]["bb_per_deal"]:+.3f}' for o in order)
        counts=f'{r["counters"]["fault_events"]}/{r["counters"]["fallback_decisions"]}/{r["judge_errors"]}/{r["timeouts"]}/{r["forfeits"]}'
        lines.append(f'| {r["profile"]} | {desc} | {r["points"]:g}/12 | {r["bb_per_deal"]:+.4f} | {ds} | {points} | {profit} | {r["max_charged_half"]:.3f}s | {counts} | {r["decision"]} |')
    if not lock['selection']['combination_justified']:
        lines+=['| A+B | Not justified by independent screens | Not run | — | — | — | — | — | — | No combination experiment |']
    lines+=['', 'Paired delta intervals resample 100-deal blocks with seats and all opponents kept together (5,000 resamples).',
            'These are exploratory development intervals, not official match verdicts or a new scoring rule.',
            'Individual official CIs and per-opponent/seed matched improvement intervals are preserved in BATCH02.json.',
            'Only two confirmation seeds were used; no claim of generalization to held-out configurations follows.',
            'A separate Student-t interval over the two independent seed means is also retained in the JSON; it is much wider and crosses zero for both candidates.',
            '', '## What was tested','',
            '- A replaces part of champion weights with a hierarchical empirical action likelihood. Separate half/pot labels, street, board texture, prior raises, facing size and smoothed aggression enter the model. Strength uses only currently visible cards. Blend/shrink settings: .25/32, .50/16, .50/64. ESS below 45% triggers uniform shrinkage.',
            '- Training uses all simulated opponent actions including folded holdings. This avoids showdown-only selection, but remains biased toward the six development policies and their state occupancy against champion. The check seed was separate from training; no held-out configurations were used.',
            '- B retains champion range weights. It compares legal check/call and raise sizes via modeled fold/call/raise responses, official game stack/raise rules, shared sampled holdings/runouts, a conservative one-response continuation proxy and uncertainty/risk deductions. It does not solve future betting.',
            '- B has a .65-second per-half action-comparison allocation; beyond its pace it explicitly uses champion decisions. These budget branches are counted separately from exception fallbacks. The model-decision fraction is recorded below.',
            '', '## Diagnostics','']
    for r in ranked:
        if r['profile']!='champion':
            ess='not applicable' if r.get('min_ess_fraction') is None else f'{r["min_ess_fraction"]:.1%}'
            fraction='not applicable' if r.get('action_model_decision_fraction') is None else f'{r["action_model_decision_fraction"]:.1%}'
            lines.append(f'- {r["profile"]}: minimum calibrated ESS fraction {ess}; ESS shrink events {r.get("ess_shrink_events")}; modeled action fraction {fraction}; worst opponent {r["worst_opponent"]}; worst individual match {r["worst_match_bb_per_deal"]:+.4f} BB/deal.')
    lines+=['', 'Champion, A and B each had six of 24 Windows confirmation halves at or above the four-second target. Zero observed faults/fallbacks/errors/forfeits/bank exhaustion does not make those runtime gates pass.']
    lines+=['', 'The targeted flop subset is defined using champion hands, then those same indices are compared across policies.',
            'This prevents selecting a different subgroup after a policy changes play. Outcomes remain descriptive, not proof of a bad action.',
            '', '| Profile | Matched target hands | Net BB | Mean BB/hand |','|---|---:|---:|---:|']
    for name,r in report['target_flop']['profiles'].items():lines.append(f'| {name} | {r["hands"]} | {r["net_bb"]:+.2f} | {r["mean_bb_per_hand"]:+.4f} |')
    lines+=['', '## Reproduce and resume','', '```powershell','python tools/calibrate_actions.py',
            'python tools/batch02.py init','python tools/batch02.py screen','python tools/batch02.py confirm',
            'python tools/report_batch02.py','```','',
            'Batch01 raw logs must be present for calibration. Existing checkpoints require identical source/configuration hashes.',
            'Frozen packages, exact source hashes, official JSON, logs and reliability evidence are in reports/batch02.',
            'Pilot commands: `python tools/learned_equity_pilot.py` then `python tools/benchmark_equity_checkpoint.py`. Exported weights are also preserved in experiments/batch02_learned_equity_weights.json.',
            'The original 90-minute cutoff is enforced by the runner; reproducing after that cutoff requires a new declared batch budget.',
            '', '## Deadline and release','',
            'The live organizer guide still contained a deadline placeholder; the submission form did not specify a deadline.',
            'The user confirmed 04:00 is an unverified planning assumption and is checking with organizers. No authoritative final freeze was scheduled.',
            'Champion passed fresh official Docker checks on its exact commit in [run 42426541174](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42426541174). No new submission commit was released.',
            'Windows confirmation recorded multiple runtime-target misses, including champion. These remain failures of the local 4-second gate even though Linux validation passed. Their cause is unresolved; no selective reruns replaced them.',
            'Any eventual different submission commit requires its own official Docker checks.',
            '', '[Full metrics and source hashes](BATCH02.json)']
    if pilot:
        lines+=['','## Bounded learned-equity pilot','',f'Uniform-opponent equity only: {pilot["train_states"]} training / {pilot["check_states"]} independent check states, official-evaluator labels.',
                f'Full direct-game throughput: {pilot["simulator_throughput"]["hands_per_second"]:.1f} hands/s and {pilot["simulator_throughput"]["decisions_per_second"]:.1f} decisions/s, excluding HTTP/startup.',
                f'Label throughput {pilot["label_rollouts_per_second"]:.0f} rollouts/s; label generation {pilot["label_seconds"]:.1f}s; fitting {pilot["fit_seconds"]:.2f}s.',
                f'Model RMSE {pilot["model"]["rmse"]:.4f}; simulation RMSE {pilot["simulation"]["rmse"]:.4f}; label mean MC SE {pilot["mean_check_label_stderr"]:.4f}.',
                f'Champion-style uniform shrinkage RMSE: {pilot["champion_uniform_shrinkage"]["rmse"]:.4f}. The full-sample uniform control does not include range conditioning or runtime sample halving.',
                f'Feature extraction + scalar inference {pilot["scalar_feature_and_inference_us"]:.1f}us versus simulation {pilot["simulation_us"]:.1f}us ({pilot["speed_ratio"]:.2f}x).',
                'Speed uses the median of three alternating-order passes; both corrected timing batches are retained (12.45x and 16.90x batch ratios). Complete-game throughput varied from 76 to 123 hands/s between the original and corrected-benchmark runs.',
                'The benchmark correction used production Rollouts and nonoverlapping calibration bins. Original benchmark evidence was retained; labels and trained weights remained byte-identical. No model retuning occurred.',
                'This measures feasibility only. The estimator has no range-conditioning or official match-performance evidence. No expensive training or production replacement was launched.']
    (ROOT/'docs/BATCH02.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k!='research_metrics'} for r in ranked],indent=2))

if __name__=='__main__':main()
