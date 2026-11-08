"""Recompute public-screen scoring from raw halves without importing any bot."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


def audit(directory: Path) -> dict:
    lock = json.loads((Path(__file__).resolve().parents[1] / 'experiments/PUBLIC_OPPONENTS_LOCK.json').read_text())
    pinned = {r['repo']: r['sha'] for r in lock['opponents']}
    rows = []
    for path in sorted(directory.rglob('result.json')):
        row = json.loads(path.read_text())
        if row['repo'] == 'harness-self-check':
            continue
        assert pinned[row['repo']] == row['sha'], path
        if row['status'] == 'played':
            halves = [json.loads((path.parent / f'half{i}.json').read_text()) for i in (1, 2)]
            match = json.loads((path.parent / 'match.json').read_text())
            for i, half in enumerate(halves):
                assert half['half'] == i + 1 and half['agent1_seat'] == i
                assert half['match_seed'] == lock['seed'] and half['num_deals'] == lock['deals']
                assert len(half['nets_agent1']) == lock['deals']
                assert all(a == -b for a, b in zip(half['nets_agent1'], half['nets_agent2']))
            paired = [(a + b) / 2 for a, b in zip(halves[0]['nets_agent1'], halves[1]['nets_agent1'])]
            mean = statistics.mean(paired)
            se = statistics.stdev(paired) / math.sqrt(len(paired))
            ci = [mean - 1.96 * se, mean + 1.96 * se]
            assert match['paired_bb'] == paired
            assert math.isclose(mean, match['mean_bb_per_deal'], abs_tol=1e-10)
            assert math.isclose(mean, row['bb_per_deal'], abs_tol=1e-10)
            assert all(math.isclose(a, b, abs_tol=1e-10) for a, b in zip(ci, match['ci']))
            assert all(math.isclose(a, b, abs_tol=1e-10) for a, b in zip(ci, row['ci']))
            forfeits = [any(h['agent_stats'][name]['forfeited'] for h in halves) for name in ('agent1', 'agent2')]
            verdict = ('BOTH_FORFEIT' if all(forfeits) else 'AGENT2_WIN' if forfeits[0]
                       else 'AGENT1_WIN' if forfeits[1] or ci[0] > 0
                       else 'AGENT2_WIN' if ci[1] < 0 else 'CHOP')
            assert verdict == row['verdict'] == match['verdict']
            points = 1.0 if verdict == 'AGENT1_WIN' else .5 if verdict == 'CHOP' else 0.0
            assert row['points'] == match['points']['agent1'] == points
            assert row['agent_stats'] == match['agent_stats']
            row['raw_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [path.parent / 'half1.json', path.parent / 'half2.json', path.parent / 'match.json']}
        rows.append(row)
    assert len({r['repo'] for r in rows}) == len(rows), 'duplicate repository results'
    played = [r for r in rows if r['status'] == 'played']
    clean = [r for r in played if not r['starfish_forfeit'] and not r['opponent_forfeit']]
    healthy = [r for r in clean if not any(s['errors'] or s['timed_out']
               for halves in r['agent_stats'].values() for s in halves)]
    own_stats = [s for r in played for s in r['agent_stats']['agent1']]
    opponent_stats = [s for r in played for s in r['agent_stats']['agent2']]
    diagnostics = [half[0] for r in played for half in r['diagnostics']]
    summary = {
        'starfish_sha': lock['starfish_sha'], 'seed': lock['seed'], 'deals_per_match': lock['deals'],
        'attempted': len(rows), 'locked_repositories': len(pinned),
        'statuses': dict(Counter(r['status'] for r in rows)),
        'official_points': sum(r['points'] for r in played),
        'official_verdicts': dict(Counter(r['verdict'] for r in played)),
        'nonforfeit_matches': len(clean),
        'nonforfeit_verdicts': dict(Counter(r['verdict'] for r in clean)),
        'nonforfeit_mean_bb_per_deal': statistics.mean(r['bb_per_deal'] for r in clean) if clean else None,
        'healthy_matches': len(healthy),
        'healthy_verdicts': dict(Counter(r['verdict'] for r in healthy)),
        'healthy_points': sum(r['points'] for r in healthy),
        'healthy_mean_bb_per_deal': statistics.mean(r['bb_per_deal'] for r in healthy) if healthy else None,
        'starfish_max_charged_half': max((s['time_seconds'] for s in own_stats), default=None),
        'starfish_errors': sum(s['errors'] for s in own_stats),
        'starfish_forfeited_halves': sum(s['forfeited'] for s in own_stats),
        'starfish_exhausted_halves': sum(s['timed_out'] for s in own_stats),
        'starfish_fault_events': sum(d['fault_events'] for d in diagnostics if d is not None),
        'starfish_fallback_decisions': sum(d['fallback_decisions'] for d in diagnostics if d is not None),
        'starfish_missing_diagnostics': sum(d is None for d in diagnostics),
        'opponent_errors': sum(s['errors'] for s in opponent_stats),
        'opponent_forfeited_halves': sum(s['forfeited'] for s in opponent_stats),
        'opponent_exhausted_halves': sum(s['timed_out'] for s in opponent_stats),
        'results': rows,
    }
    (directory / 'PUBLIC_AUDIT.json').write_text(json.dumps(summary, indent=2) + '\n')
    return {k: v for k, v in summary.items() if k != 'results'}


if __name__ == '__main__':
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
