# Validation - 2026-11-07

## Correctness

**123 tests passed** using Python 3.10.11, FastAPI 0.156.1 and uvicorn 0.54.0.
Coverage includes the official HTTP API, action legality across both seats,
exact Omaha evaluation against the official reference, sampling without card
collisions, split pots, per-half memory isolation, opponent-response accounting,
conditional river bluffing, official scoring integration, and evaluation-report
validation. Added fault-injection tests cover callback exceptions, illegal action
types, per-half fault latching, conservative fallback, persistent diagnostics,
stderr evidence, and release-gate rejection. Docker helper tests use mocked CLI
responses; they do not establish a successful container run. The strategy/equity
modules require no additional inference libraries. The new equity tests cover
importance-weighted estimates, effective sample size, incremental samples,
visible-card-only range features, position variants and equivalence to the
frozen eager implementation on the active Python version.

## Current release: range-weighted policy

The production profile is `range_130_budget25`: range multiplier 1.3, caller
conditioning off, extra boundary samples off, legacy position margin,
24/32/40/64 initial samples and a 25% core compute allowance.

The final holdout consisted of **31 full official HTTP matches / 62,000 hands**.
Candidate and v1 runs were interleaved; both bot processes restarted between
halves. Configurations and source hashes were locked before opening the five
final seeds. The selected bot earned:

- **18/18 official match points**, all individual official confidence intervals
  strictly positive.
- **5/5 versus frozen Starfish v1**, averaging **+1.4292 BB per paired deal**.
- **5/5 versus Desktop ShortDeckAce-v2**, averaging **+2.2849 BB per paired deal**.
- **8/8 versus the four official baselines**, two seeds each.
- **13/13 versus v1's 10.5/13 on the identical common opponent/seed pool**.
- Zero observed judge errors, bank exhaustion, forfeits, strategy faults,
  fallback decisions or stderr fault markers. Both agents' validity was checked.
- Maximum candidate charged half **2.849586 seconds**, below the 4-second target.

The selected runtime source also passed the
[Linux release workflow](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42408822715)
at experiment commit `ef0ce3db6a675ee64cf738aeebaceb4a14cf78e1`:

- All **123 tests passed** on Python 3.12.
- **8/8 additional official baseline matches**, with fresh processes between halves.
- Zero observed faults, fallbacks or judge validity violations; maximum candidate
  charged half **2.905858 seconds**.
- Unchanged official Docker build, size and smoke checks passed.
- Supplementary zero-fault container check passed under 1 CPU, 4 GB RAM,
  no network and a read-only filesystem except `/tmp`.

The workflow staged the selected profile before testing. Every runtime file in
that artifact matches the final production files after CRLF/LF normalization.
Full-match timings were measured on Windows/Linux hosts; the restricted Docker
image ran smoke checks rather than full matches.

[EXPERIMENTS.md](EXPERIMENTS.md) explains all four requested experiments and the
selection decision. [EXPERIMENTS.json](EXPERIMENTS.json) contains individual
official metrics, configurations, source hashes, paired profit comparisons and
Linux/container evidence. It also preserves the first candidate's rejected
runtime results rather than dropping failed experiments.

## Historical v1 Linux validation

The following results describe the previous policy, not the new release above.

Commit `f7941ca79785dc78bfecfae38bf4f6679008114b` passed the
[Linux release workflow](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42402994032):

- All **102 tests passed** on Python 3.12.16.
- **8/8 official match points across 16,000 hands**, all four baselines on
  additional seeds 731 and 947. Both servers restarted between every half.
- Zero judge errors, forfeits or bank exhaustion for either bot; zero Starfish
  strategy faults, fallback decisions or stderr fault markers.
- Largest Starfish charged half: **2.578290 seconds**, below the 4-second target.
- Unchanged official Docker build/size/smoke check passed.
- Supplementary container check passed with zero fault evidence, under 1 CPU,
  4 GB RAM, no network and a read-only filesystem except `/tmp`. Smoke startup
  was 0.8 seconds and the sampled action requests were 2–3 milliseconds.

[LINUX_VALIDATION.json](LINUX_VALIDATION.json) preserves official per-match
metrics, source hashes, environment and restricted-container evidence. Raw logs
are retained in the workflow artifact. Match timing above was measured on the
Linux runner outside Docker; the restricted container ran smoke cases, not the
full matches. This validates compatibility and these baseline results, not an
advantage over other teams or a candidate improvement over the previous policy.

## Historical official baseline matrix

These results describe commit `b1a73dd2c2349cc4b693c66babe9156dcdf0254f`, before
the Starfish metadata and observable reliability adapter. They establish the
original policy's baseline performance, not validation of the current release.

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

- The current opponent pool includes the four simple baselines, frozen v1 and
  Desktop ShortDeckAce-v2. It does not cover every competitive strategy or solver.
- The 19-configuration search identifies the best tested setting, not a global
  optimum. The final seeds are now historical evidence; future upgrades require
  new unseen seeds. See the experiment report for direct-screen timing limits.
- Range weights remain heuristic and equity estimates noisy. No offline training
  or equilibrium-solving has been performed. Hardware load and Python versions
  can affect sampling and decisions.
- Docker Desktop failed to start locally. The successful official Linux build
  and smoke check ran on GitHub Actions as documented above.
- The team metadata is now **Starfish**.
- No tournament submission has been made.

Run `bash tools/check_build.sh` in Git Bash/WSL with Docker running before
submitting. Then run `python tools/check_container_reliability.py` to reject
logged or counted strategy faults even if the smoke test received legal actions.
Keep the official Dockerfiles and package pins unchanged.

The manual `Starfish release checks` GitHub Actions workflow runs Python 3.12
tests, eight sequential fresh-process matches against all four baselines on
additional seeds 731 and 947, the unchanged official Docker check, and the
supplementary container reliability gate. Successful execution must be checked
for each future release; the current successful run covers the selected runtime
files recorded in EXPERIMENTS.json, including the staged production wrapper.
