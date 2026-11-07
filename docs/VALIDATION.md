# Local validation - 2026-11-07

## Correctness

**54 tests passed** using Python 3.10.11, FastAPI 0.156.1 and uvicorn 0.54.0.
Coverage includes the official HTTP API, action legality across both seats,
exact Omaha evaluation against the official reference, sampling without card
collisions, split pots, per-half memory isolation, opponent-response accounting,
conditional river bluffing, official scoring integration, and evaluation-report
validation. The strategy/equity modules require no additional inference libraries.

## Full official baseline matrix

The bot completed **20 full matches / 40,000 played hands**, against all four
official baselines with seeds **7, 19, 43, 101, 202**. Each match contains 1,000
duplicate deals played in two halves with seats swapped. Both bot processes
were restarted between halves, and matches ran sequentially.

Every match earned **1 official point: 20/20 total**. All 20 official confidence
intervals had lower bounds above zero. Both agents had **zero errors, forfeits,
time-bank exhaustion, or skipped calls** throughout the matrix.

The largest charged time for any bot half was **2.918391 seconds**, below our
4-second target and the official 8-second allowance. These are local Windows
measurements, not a guarantee of latency on the tournament's Linux machine.

| Opponent | Official points | Mean BB/deal | Worst match BB/deal | Lowest match CI bound | Max charged seconds |
|---|---:|---:|---:|---:|---:|
| RandomBot | 5/5 | +7.9427 | +7.2215 | +5.932407 | 1.973416 |
| CallingStation | 5/5 | +9.4811 | +9.1865 | +8.305879 | 2.918391 |
| AlwaysHalfBot | 5/5 | +12.0213 | +11.7040 | +10.416129 | 2.644811 |
| AlwaysPotBot | 5/5 | +6.7624 | +6.3130 | +4.667369 | 2.154669 |

The CI column is the minimum lower bound among five **individual official
match intervals**, not a confidence interval on a pooled mean. Profit units
are BB per paired deal; conventional BB/100 is 50 times that value.

[BASELINE_MATRIX.json](BASELINE_MATRIX.json) contains the exact 20 match verdicts,
points, profit estimates, official confidence intervals, per-half validity and
charged-time metrics, per-opponent summaries, package versions, and SHA-256
hashes of the evaluated strategy, equity estimator, and official scoring/rules
files. It contains no machine-specific absolute paths, local server addresses,
or team-account identifiers. All verdicts and match metrics come directly from
`judge_engine.py`; the report does not implement a separate scoring formula.

Reproduce the matrix from the project root:

```powershell
python tools/evaluate_suite.py --output reports/new-baseline-matrix
```

Use an empty output directory. The defaults run these four opponents and five
seeds for 1,000 deals per match, with complete official logs and source snapshots.
The tool rejects source changes during evaluation. Because the policy adapts
sampling to measured computation time, fixed deals do not guarantee identical
decisions on differently loaded machines.

## Limits and remaining checks

- These four practice policies are simple. Stronger equity-based policies,
  competitive opponent models, solvers, and previous-version comparisons have
  **not** been tested. Baseline success does not establish tournament strength.
- This matrix evaluates one frozen strategy; it does not demonstrate a candidate
  improvement on additional, unused seeds. Reserve separate seeds for that test.
- The policy uses noisy, uniformly sampled opponent holdings with heuristic
  range discounts. No offline training or equilibrium-solving has been performed.
- The official Linux Docker build/smoke test has **not** run: Docker Desktop's
  Linux daemon was unavailable. The official base uses Python 3.12; the local
  evaluation used Python 3.10.11.
- The team-name placeholder needs replacement before submission.
- No tournament submission has been made.

Run `bash tools/check_build.sh` in Git Bash/WSL with Docker running before
submitting. Keep the official Dockerfiles and package pins unchanged.
