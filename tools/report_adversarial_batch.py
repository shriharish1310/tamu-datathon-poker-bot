"""Publish a compact, auditable development leaderboard without changing champion."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.diagnose_matchups import analyze


def main():
    folder=ROOT/'reports/adversarial-batch-01'
    board=json.loads((folder/'leaderboard.json').read_text())
    assert board['status']=='complete' and len(board['matches'])==12
    sources=json.loads((folder/'manifest.json').read_text())
    inputs=json.loads((ROOT/'experiments/BATCH01_INPUTS.json').read_text())
    for name,expected in {**sources,**inputs}.items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected,name
    frozen=json.loads((ROOT/'experiments/CHAMPION.json').read_text())
    for name,expected in frozen['sha256'].items():
        assert hashlib.sha256((ROOT/'reports/champion-fd5c428'/name).read_bytes()).hexdigest()==expected,name
    groups=defaultdict(list)
    for row in board['matches']: groups[row['family']].append(row)
    summary=[]
    for family,rows in groups.items():
        summary.append({'family':family,'opponent':rows[0]['opponent'],'matches':len(rows),
                        'points':sum(r['points'] for r in rows),
                        'bb_per_deal':sum(r['mean_bb_per_deal'] for r in rows)/len(rows),
                        'worst_match':min(r['mean_bb_per_deal'] for r in rows),
                        'min_individual_ci_lower':min(r['ci'][0] for r in rows),
                        'max_charged_seconds':max(r['max_time_seconds'] for r in rows),
                        'verdicts':[r['verdict'] for r in rows]})
    summary.sort(key=lambda r:(r['points'],r['bb_per_deal']))
    diagnostics=analyze(folder,board)
    ci=json.loads(subprocess.check_output(['gh','run','view','42410659498','--json','status,conclusion,headSha,url,jobs'],cwd=ROOT))
    assert ci['headSha']==frozen['commit'] and ci['conclusion']=='success',ci
    artifact=ROOT/'reports/champion-exact-ci-42410659498'
    for name,expected in frozen['sha256'].items():
        actual=(artifact/'linux-reliability/source'/name).read_bytes().replace(b'\r\n',b'\n')
        assert hashlib.sha256(actual).hexdigest()==expected,name
    ci_summary=json.loads((artifact/'linux-reliability/summary.json').read_text())
    container=json.loads((artifact/'container-reliability.json').read_text())
    assert ci_summary['summary']['release_gates_passed'] and container['passed']
    direct=json.loads((folder/'direct-summary.json').read_text())
    # Preserve all scalar match results; raw half outcomes remain checkpointed.
    compact={phase:[{k:v for k,v in r.items() if k not in ('halves','paired_bb')} for r in rows]
             for phase,rows in direct.items()}
    result={'decision':'RETAIN range_130_budget25; no candidate replacement evaluated',
            'champion':frozen,'research_source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'development_only':True,'heldout_opponents_used':False,'final_holdout_used':False,
            'matched_candidate_improvement':None,
            'matched_improvement_note':'No candidate was tested. This batch characterizes frozen champion only.',
            'source_hashes':sources,'input_hashes':inputs,'per_opponent':summary,
            'official_http':board,'direct_development':compact,'diagnostics':diagnostics,'exact_champion_ci':ci,
            'exact_champion_ci_source_verified':True,'linux_summary':ci_summary['summary'],
            'linux_matches':ci_summary['matches'],'container_evidence':container}
    (ROOT/'docs/ADVERSARIAL_BATCH01.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    total=sum(r['points'] for r in board['matches'])
    maximum=max(r['max_time_seconds'] for r in board['matches'])
    lines=['# Adversarial opponent batch 01','',
           '**Decision: RETAIN frozen `range_130_budget25`.** This batch tested the evaluation pool; no candidate upgrade was promoted.',
           '',f'Champion: `{frozen["commit"]}`. The production branch and its runtime/configuration remain unchanged.',
           '', '24 independently parameterized configurations across six families were screened on 300 paired deals.',
           'The strongest adversary in each family was selected on that screen, then checked on two new development seeds',
           'at 1,000 paired deals and two additional official HTTP seeds. All 12 held-out configurations remain unused.',
           'These are held-out parameters within known families, not unseen architectures. Policies share evaluator/rollout code.',
           '',f'**Official HTTP: {total:g}/12 points; 24,000 hands.** Both processes restart between halves; matches run sequentially.',
           'Direct screening/confirmation adds 38,400 hands; it does not measure official charged time.',
           '', '| Family | Selected opponent | Points / 2 | Mean BB/paired deal | Worst match | Lowest individual CI bound | Max charged half |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f'| {r["family"]} | {r["opponent"]} | {r["points"]:g}/2 | {r["bb_per_deal"]:+.4f} | {r["worst_match"]:+.4f} | {r["min_individual_ci_lower"]:+.4f} | {r["max_charged_seconds"]:.3f}s |')
    lines += ['', 'The CI column is the lowest bound of individual official match intervals, not a pooled CI.',
              'A CHOP is statistically inconclusive. Screening losses selected for extremeness are not proof of an exploit.',
              '', '## Individual official matches','',
              '| Opponent | Seed | Verdict | Points | BB/paired deal | Official 95% CI | Charged seconds |',
              '|---|---|---|---:|---:|---|---:|']
    for r in board['matches']:
        lines.append(f'| {r["opponent"]} | {r["seed"]} | {r["verdict"]} | {r["points"]:g} | {r["mean_bb_per_deal"]:+.4f} | [{r["ci"][0]:+.4f}, {r["ci"][1]:+.4f}] | {r["max_time_seconds"]:.3f}s |')
    lines += ['', '## Loss diagnostics','',
              'All official action logs were replayed; final nets/pots and marginal partition totals were checked.',
              'Last betting street, button/big-blind position, largest opponent raise in the hand, and final pot size',
              'partition each hand exactly once per dimension.',
              'Decision-context groups also appear in the JSON; a hand is counted once per context but contexts overlap.',
              'These are descriptive final outcomes, not causal decision values or evidence that a fold was wrong.',
              '', 'Below: supported negative slices for the two weakest matchup families. Require at least 200 hands,',
              '100 distinct paired deals and two seeds. No subgroup significance claim is made.',
              '', '| Opponent | Dimension | Group | Hands | Distinct paired deals | Net BB | Gross lost BB |',
              '|---|---|---|---:|---:|---:|---:|']
    weakest={r['opponent'] for r in summary[:2]}
    eligible=[r for r in diagnostics['partitioned_hand_outcomes'] if r['sufficient_for_description']
              and r['group'][0] in weakest and r['group'][1]!='joint' and r['net_bb']<0]
    for r in eligible:
        lines.append(f'| {r["group"][0]} | {r["group"][1]} | {r["group"][2]} | {r["hands"]} | {r["distinct_paired_deals"]} | {r["net_bb"]:+.1f} | {r["gross_loss_bb"]:.1f} |')
    lines += ['', 'All slices, including small and nonnegative groups, remain in the JSON. Do not add overlapping dimensions.',
              '', 'Supported decision contexts with the largest negative final outcomes in the weakest matchup:',
              '', '| Street | Position | Facing | Pot before decision | Hands | Final net BB | Mean BB/hand |',
              '|---|---|---|---|---:|---:|---:|']
    contexts=[r for r in diagnostics['overlapping_decision_contexts'] if r['sufficient_for_description']
              and r['group'][0]==summary[0]['opponent'] and r['net_bb']<0]
    for r in contexts[:6]:
        g=r['group']
        lines.append(f'| {g[2]} | {g[3]} | {g[4]} | {g[5]} | {r["hands"]} | {r["net_bb"]:+.1f} | {r["mean_bb_per_hand"]:+.3f} |')
    lines += ['', 'These groups include folds as well as calls and raises; do not interpret their final losses as the cost of calling.',
              '', '## Reliability and checkpoint','',
              f'All observed champion and research-opponent judge errors, internal faults/fallbacks, forfeits and bank exhaustion were zero. Maximum champion charged half: {maximum:.6f}s.',
              'The research harness passed 126 tests before the batch; champion itself has 123 tests at its frozen commit.',
              f'The [exact champion release workflow]({ci["url"]}) passed without staging another policy, including the official Docker build/size/smoke and supplementary container-fault checks.',
              'Full matches measure host HTTP timing; restricted containers run smoke checks.',
              '', 'Production stays on the champion commit. Research code, inputs and compact results live on `codex/adversarial-pool`.',
              'Local checkpoint: `reports/adversarial-batch-01`; resume the same batch with `python tools/adversarial_batch.py run`.',
              'Each match is retained separately with source locks, fresh-process logs and reliability sidecars.',
              '', '## Next decision','',
              'Prioritize action-likelihood calibration for flop pot bets faced from the big blind and tight opponents\' raises,',
              'then test size-dependent response/continuation values as a separate ablation. This batch supplies',
              'development targets, not evidence that either proposed change will improve the champion.',
              'A learned equity estimator and bounded MCCFR pilot remain unrun; population RL has not been justified.',
              'All future candidate comparisons need matched champion runs and newly locked final seeds/configurations.',
              'Stop development at midnight Central on November 8; reserve four hours before the user\'s 04:00 deadline.',
              '', '[Machine-readable results](ADVERSARIAL_BATCH01.json) · [Next batches and release protocol](../experiments/NEXT_BATCHES.md)']
    (ROOT/'docs/ADVERSARIAL_BATCH01.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
