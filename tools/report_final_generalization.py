"""Read-only final evaluation audit; no tuning, scoring replacement or reruns."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.adversarial_batch import save, RUNTIME
from tools.evaluate_suite import read_official
from tools.final_generalization import inputs, LOCK_COMMIT

OUT = ROOT/'reports/final-generalization'
RUN_ID = '42440992607'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def seed_interval(values):
    """Three independent seed-block means; do not count actions as samples."""
    if len(values) != 3:
        raise ValueError('Expected three seed estimates')
    mean = statistics.mean(values)
    radius = 4.302652729911275 * statistics.stdev(values) / (3**.5)
    return [mean-radius, mean+radius]


def validate_matrix(rows, plan, configs):
    expected = {(c['name'], s) for c in configs for s in plan['seeds']}
    actual = [(r['opponent'], r['seed']) for r in rows]
    if len(rows) != 36 or len(set(actual)) != 36 or set(actual) != expected:
        raise ValueError('Incomplete, duplicate, or unplanned match matrix')
    if any(r['num_deals'] != 1000 for r in rows):
        raise ValueError('Wrong deal count')


def aggregate(rows, plan, configs):
    validate_matrix(rows, plan, configs)
    per_opponent = []
    for cfg in configs:
        group = [next(r for r in rows if r['opponent']==cfg['name'] and r['seed']==s) for s in plan['seeds']]
        counts = Counter(r['verdict'] for r in group)
        bb = [r['mean_bb_per_deal'] for r in group]
        per_opponent.append(dict(opponent=cfg['name'], family=cfg['family'], matches=3,
            wins=counts['AGENT1_WIN'], chops=counts['CHOP'], losses=counts['AGENT2_WIN'],
            other_verdicts={k:v for k,v in counts.items() if k not in ('AGENT1_WIN','CHOP','AGENT2_WIN')},
            points=sum(r['points'] for r in group), mean_points=statistics.mean(r['points'] for r in group),
            bb_per_paired_deal=statistics.mean(bb), seed_bb_values=bb,
            seed_t_ci95=seed_interval(bb), worst_seed_bb=min(bb), best_seed_bb=max(bb),
            official_match_cis=[r['ci'] for r in group],
            max_charged_seconds=max(r['max_time_seconds'] for r in group),
            seeds=[dict(seed=r['seed'],verdict=r['verdict'],points=r['points'],
                        bb_per_deal=r['mean_bb_per_deal'],official_ci=r['ci'],
                        max_charged_seconds=r['max_time_seconds'],report=r['report']) for r in group]))
    seed_rounds = []
    for s in plan['seeds']:
        group = [r for r in rows if r['seed']==s]
        seed_rounds.append(dict(seed=s, configurations=len(group),
            points=statistics.mean(r['points'] for r in group),
            bb_per_paired_deal=statistics.mean(r['mean_bb_per_deal'] for r in group)))
    verdicts = Counter(r['verdict'] for r in rows)
    return dict(equally_weighted_match_points=statistics.mean(p['mean_points'] for p in per_opponent),
        total_points=sum(r['points'] for r in rows),wins=verdicts['AGENT1_WIN'],
        chops=verdicts['CHOP'],losses=verdicts['AGENT2_WIN'],
        mean_bb_per_paired_deal=statistics.mean(p['bb_per_paired_deal'] for p in per_opponent),
        seed_rounds=seed_rounds,
        seed_cluster_bb_t_ci95=seed_interval([s['bb_per_paired_deal'] for s in seed_rounds]),
        seed_cluster_points_t_ci95_unclipped=seed_interval([s['points'] for s in seed_rounds]),
        per_opponent=per_opponent,
        worst_matchups=sorted(per_opponent,key=lambda p:(p['mean_points'],p['bb_per_paired_deal']))[:3],
        uncertainty_scope='Three common seed clusters, df=2; per-match CIs are the official judge CIs. Seed-level t intervals describe this fixed pool and assume seed independence, not unseen architectures or all competing teams.')


def reliability(rows):
    result = {}
    for who, diag_key, log_key in [('agent1','diagnostics','log_fault_events'),
                                  ('agent2','opponent_diagnostics','opponent_log_fault_events')]:
        halves=[h for r in rows for h in r['agent_stats'][who]]
        evidence=[h for r in rows for h in r['reliability_halves']]
        result[who]=dict(halves=len(halves),max_charged_seconds=max(h['time_seconds'] for h in halves),
            median_charged_seconds=statistics.median(h['time_seconds'] for h in halves),
            at_or_over_four=sum(h['time_seconds']>=4 for h in halves),
            bank_exhaustions=sum(h['timed_out'] for h in halves),errors=sum(h['errors'] for h in halves),
            forfeits=sum(h['forfeited'] for h in halves),
            fault_events=sum(h[diag_key]['fault_events'] for h in evidence),
            exception_fallback_decisions=sum(h[diag_key]['fallback_decisions'] for h in evidence),
            disabled_halves=sum(h[diag_key]['disabled'] for h in evidence),
            logged_fault_events=sum(h[log_key] for h in evidence))
    ms=[m for r in rows for m in r['metrics']]
    result['candidate_runtime']=dict(decisions=[m['decisions'] for m in ms],
        actual_rollouts=[m['experiment']['sampled_trials'] for m in ms],
        core_seconds=[m['core_seconds'] for m in ms],
        cpu_preflight_percent=[r['idle_host_cpu_percent'] for r in rows],
        environment={k:ms[0][k] for k in ('python','versions','http_parser','httptools','cpuinfo','cgroup_cpu_max','cgroup_memory_max')})
    return result


def acceptance(summary, rel, rows, tests_passed, docker_passed):
    zero_keys=('bank_exhaustions','errors','forfeits','fault_events',
               'exception_fallback_decisions','disabled_halves','logged_fault_events')
    return dict(complete_36=len(rows)==36,
        average_points_at_least_075=summary['equally_weighted_match_points']>=.75,
        each_configuration_at_least_15_points=all(p['points']>=1.5 for p in summary['per_opponent']),
        each_configuration_positive_mean_profit=all(p['bb_per_paired_deal']>0 for p in summary['per_opponent']),
        aggregate_profit_seed_ci_positive=summary['seed_cluster_bb_t_ci95'][0]>0,
        candidate_each_half_under_four=rel['agent1']['at_or_over_four']==0,
        zero_reliability_failures=all(rel[who][k]==0 for who in ('agent1','agent2') for k in zero_keys)
            and all(all(r[k] for k in ('bot_valid','opponent_valid','reliability_clean','opponent_reliability_clean')) for r in rows),
        exact_candidate_tests=tests_passed,exact_candidate_official_docker=docker_passed)


def markdown(r):
    s=r['summary'];ours=r['reliability']['agent1'];opps=r['reliability']['agent2']
    ci=lambda v:f'[{v[0]:+.3f}, {v[1]:+.3f}]'
    lines=[f"**Final evaluation: {r['recommendation']}.** Frozen candidate `{r['candidate']}`; fallback `{r['fallback']}`.",'',
        f"Equally weighted official match points: **{s['equally_weighted_match_points']:.6f} per match ({s['total_points']:g}/36 points)**. Results: {s['wins']} wins, {s['chops']} chops, {s['losses']} losses. Each configuration receives weight 1/12 and each of its seeds weight 1/3. Mean profit: **{s['mean_bb_per_paired_deal']:+.6f} BB/paired deal**; across-seed 95% t interval {ci(s['seed_cluster_bb_t_ci95'])}.",'',
        'The pre-open protocol was committed at `a16e68f9139a638743c9d085a48bd68b54f7e51e`. The pool matched its original Batch 01 hash and no prior evaluation was found in available records. All 36 locked full matches completed: 1,000 paired deals each, 72,000 played hands total, fresh processes between halves, sequential execution on one fresh Linux runner, and no concurrent training. No candidate or opponent parameters were changed.', '',
        '| Configuration | W / C / L | Points / 3 | BB/paired deal | 95% interval across 3 seeds | Worst charged half (s) |',
        '|---|---:|---:|---:|---|---:|']
    for p in s['per_opponent']:
        lines.append(f"| {p['opponent']} | {p['wins']} / {p['chops']} / {p['losses']} | {p['points']:g} | {p['bb_per_paired_deal']:+.4f} | {ci(p['seed_t_ci95'])} | {p['max_charged_seconds']:.6f} |")
    lines+=['','Seed intervals use three independent match-seed clusters and Student-t df=2. They are not the official per-match confidence intervals. They are wide with only three seeds, are not adjusted for 12 simultaneous comparisons, and cannot establish tournament dominance. A chop means the official match interval includes zero; it is not proof of equal strength.', '',
        '| Match seed | Mean official points | Mean BB/paired deal across all 12 configurations |','|---|---:|---:|']
    for x in s['seed_rounds']:lines.append(f"| {x['seed']} | {x['points']:.6f} | {x['bb_per_paired_deal']:+.6f} |")
    lines+=['',f"Across-seed points interval (unclipped): {ci(s['seed_cluster_points_t_ci95_unclipped'])}. A degenerate interval from identical observed seed scores does not imply zero uncertainty on future seeds or opponents.",'',
        'Worst matchups, ranked by mean match points then BB/deal:', '']
    for p in s['worst_matchups']:
        lines.append(f"- `{p['opponent']}`: {p['points']:g}/3 points; {p['bb_per_paired_deal']:+.4f} BB/deal; individual seed profits {', '.join(f'{v:+.4f}' for v in p['seed_bb_values'])}; seed interval {ci(p['seed_t_ci95'])}.")
    lines+=['','**Official per-match results**','','A/B/C refer to the three locked seeds in their listed order. Each cell is BB/paired deal followed by the untouched official 95% CI. Individual verdicts, points, logs and statistics remain in the JSON report and CI artifact.','',
        '| Configuration | Seed A: BB [official CI] | Seed B: BB [official CI] | Seed C: BB [official CI] |','|---|---|---|---|']
    for p in s['per_opponent']:
        cells=[f"{x['bb_per_deal']:+.4f} {ci(x['official_ci'])}" for x in p['seeds']]
        lines.append('| '+p['opponent']+' | '+' | '.join(cells)+' |')
    lines+=['','**Runtime and release gates**','',
        f"Candidate median/max charged half: {ours['median_charged_seconds']:.6f}s / **{ours['max_charged_seconds']:.6f}s**. Halves at or above the four-second engineering target: {ours['at_or_over_four']}/72. Minimum observed headroom to the official eight-second bank: {8-ours['max_charged_seconds']:.6f}s. Opponent max: {opps['max_charged_seconds']:.6f}s. These are observed samples, not a runtime guarantee.",'',
        '| Participant | Bank exhaustion | Judge errors | Forfeits | Internal faults | Exception fallbacks | Logged faults |','|---|---:|---:|---:|---:|---:|---:|']
    for label,who in [('Candidate','agent1'),('Opponents','agent2')]:
        x=r['reliability'][who];lines.append(f"| {label} | {x['bank_exhaustions']} | {x['errors']} | {x['forfeits']} | {x['fault_events']} | {x['exception_fallback_decisions']} | {x['logged_fault_events']} |")
    lines+=['','| Locked gate | Passed |','|---|---|']
    lines += [f"| {k} | {v} |" for k,v in r['gates'].items()]
    lines+=['',
        'The candidate passed its tests and the official Docker startup/protocol checks again before any match. All matches used that same validated immutable image. Runtime was restricted to one CPU quota and 4 GiB per bot, non-root, read-only filesystem, loopback-only network, with separate judge/opponent cgroups. Actual per-half decisions, rollouts, core computation, HTTP charged time, dependency/parser versions, CPU preflights and reliability evidence are preserved in JSON. The physical host is not exclusively controlled; this does not erase earlier Windows timing failures.', '',
        '**Frozen artifacts and submission status**','',
        f"Exact submission SHA: `{r['candidate']}`. Evaluation harness SHA: `{r['research_commit']}`. Validated image: `{r['candidate_image']}`. Fallback remains `{r['fallback']}`. No model or strategy tuning occurred during this final evaluation.",'',
        f"Prepared ZIP: `{r['submission']['filename']}`; SHA-256 `{r['submission']['sha256']}`. Its files were rechecked against the exact candidate Git objects. No new candidate was created.",'',
        '**Submission status: not submitted by this agent.** Team registration is confirmed, but no organizer submission receipt for this SHA was found in the connected account or project records. A separate submission by another team member is not verified. A Git push, ZIP, successful CI run or registration email does not constitute tournament submission.', '',
        f"[Final Docker checks and complete evaluation](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/{RUN_ID}). Raw artifact: `final-generalization`; local path: `reports/final-generalization`. The machine-readable report includes all source/evidence hashes and every official match result.",'',
        'Executed commands (Linux runner):','', '```bash','python -m pip install -r requirements-dev.txt psutil==7.1.3',
        'docker build -t poker-agent-base:local - < docker/Dockerfile.base',
        'python tools/final_generalization.py --check','python tools/final_generalization.py','```','',
        'Report-only reproduction (does not run matches):','', '```powershell',
        f'gh run download {RUN_ID} --name final-generalization --dir reports/final-generalization',
        '.\\.venv\\Scripts\\python.exe tools/report_final_generalization.py','```','',
        '**Evaluation pool status:** consumed final validation history. These 12 configurations are held-out parameters within six known families sharing evaluator/rollout code, not 12 independently designed competitor architectures. If these results inform any new candidate, mark this pool and its three seeds as development history and reserve a new independent final evaluation. Do not tune and then reuse this pool as untouched evidence.','']
    return '\n'.join(lines)


def main():
    plan, configs, schedule = inputs()
    result=load(OUT/'benchmark.json');ledger=load(OUT/'match-ledger.json');manifest=load(OUT/'manifest.json')
    assert result['status']=='complete' and result['candidate_commit']==plan['candidate']
    assert len(ledger)==36 and all(s['status']=='complete' for s in ledger)
    assert [{k:x[k] for k in ('index','opponent','seed')} for x in ledger]==schedule
    assert manifest['plan']==plan and manifest['lock_commit']==LOCK_COMMIT
    rows=result['matches'];validate_matrix(rows,plan,configs)
    # Re-read untouched judge files and reliability sidecars; reject stale summaries.
    for row in rows:
        parsed=read_official(OUT/row['report'],row['seed'],1000,row['opponent'],4.)
        assert all(row[k]==v for k,v in parsed.items())
    container=load(OUT/'candidate-container-reliability.json');image=load(OUT/'candidate-image.json')
    assert image['commit']==plan['candidate']
    assert image['image']==container['image_id']==result['candidate_image']
    tests=(OUT/'candidate-tests.log').read_text();build=(OUT/'candidate-official-build.log').read_text()
    summary=aggregate(rows,plan,configs);rel=reliability(rows)
    gates=acceptance(summary,rel,rows,bool(re.search(r'127 passed',tests)),
                     container['passed'] and 'SMOKE TEST PASSED' in build and not container['fault_log_markers'])
    archive=ROOT/'reports/batch04-bench/submission/Starfish-6e5b590.zip'
    archive_manifest=load(archive.with_suffix('.manifest.json'))
    assert archive_manifest['commit']==plan['candidate'] and sha(archive.read_bytes())==archive_manifest['sha256']
    with zipfile.ZipFile(archive) as z:
        assert sorted(n for n in z.namelist() if not n.endswith('/'))==sorted(archive_manifest['files'])
        for path,digest in archive_manifest['files'].items():
            source=subprocess.check_output(['git','show',f'{plan["candidate"]}:{path}'],cwd=ROOT)
            assert z.read(path)==source and sha(source)==digest
    report=dict(reported_utc=datetime.now(timezone.utc).isoformat(),candidate=plan['candidate'],fallback=plan['fallback'],
        lock_commit=LOCK_COMMIT,research_commit=manifest['research_commit'],candidate_image=image['image'],
        plan=plan,summary=summary,reliability=rel,gates=gates,
        recommendation='release 6e5b590' if all(gates.values()) else 'further investigation; no unconditional release recommendation',
        matches=rows,container_validation=container,submission=dict(filename=archive.name,path=str(archive),
            sha256=archive_manifest['sha256'],submitted_by_agent=False,organizer_receipt_verified=False,
            independent_team_member_submission='not verified'),
        pool_status='consumed final validation history; reclassify as development if used to develop another candidate',
        evidence_sha256={str(p.relative_to(OUT)):sha(p.read_bytes()) for p in OUT.rglob('*.json') if 'candidate-source' not in p.parts},
        report_source_sha256=sha(Path(__file__).read_bytes()))
    save(ROOT/'docs/FINAL_GENERALIZATION.json',report)
    (ROOT/'docs/FINAL_GENERALIZATION.md').write_text(markdown(report),encoding='utf-8')
    (ROOT/'docs/SUBMISSION.md').write_text('\n'.join([
        '**Starfish submission preparation**', '',
        'Repository: https://github.com/shriharish1310/tamu-datathon-poker-bot', '',
        f"Exact commit SHA: `{plan['candidate']}`", '',
        'Frozen tag: `release-candidate-6e5b590`', '',
        f"Recommendation: **{report['recommendation']}**. See [complete final evaluation](FINAL_GENERALIZATION.md).", '',
        f"Validated Docker image: `{image['image']}`", '',
        f"Prepared ZIP: `{archive.name}`. SHA-256: `{archive_manifest['sha256']}`.", '',
        f"Frozen fallback SHA: `{plan['fallback']}`", '',
        '**Submission has not been performed by this agent.** Team registration is confirmed; no submission receipt for this commit was found in available records. Independent submissions by teammates are unverified. Use the exact commit above, not the research branch HEAD or default branch HEAD.', '',
        'This is a prepared artifact and benchmark recommendation, not an organizer acceptance or tournament result.', ''
    ]),encoding='utf-8')
    save(ROOT/'experiments/FINAL_EVALUATION_STATUS.json',dict(candidate=plan['candidate'],
        pool_sha256=plan['opponents_canonical_sha256'],seeds=plan['seeds'],status=report['pool_status'],
        recommendation=report['recommendation'],tuned_on_final_results=False,submission=report['submission']))
    print(json.dumps(dict(recommendation=report['recommendation'],summary=summary,gates=gates,reliability=rel),indent=2))


if __name__=='__main__':
    main()
