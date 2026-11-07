# Starfish — TAMU Datathon poker bot

A Python bot for **Heads-Up Short Deck 5-card Pot-Limit Omaha**, built on the
official tournament engine and HTTP protocol. The current default is
`range_130_budget25`, selected from 19 tested configurations.

On final, previously unused seeds it won **18/18 official matches**, including
**5/5 against frozen Starfish v1** and **5/5 against the separate Desktop bot**.
Across the identical 13-match common opponent pool, it earned **13 points versus
v1's 10.5**. These results establish an advantage against the tested policies,
not a solved strategy or guaranteed performance against other teams.

See [all experiments and rejected variants](docs/EXPERIMENTS.md),
[exact metrics and source hashes](docs/EXPERIMENTS.json), and
[release validation](docs/VALIDATION.md).

## Run

PowerShell from this project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest test_agent.py tests -q
.\.venv\Scripts\python.exe tools/run_local_match.py --opponent random --deals 1000 --seed practice-1
```

The local match helper starts two **loopback-only** servers, runs the official
judge, restarts both servers between duplicate halves, saves JSON reports,
and stops its own processes afterward. Opponents: `calling`, `half`, `pot`, `random`.
The helper uses the same Python interpreter that launches it. Official judge
JSON remains unchanged; a separate `*.reliability.json` records post-half health
diagnostics and fault-marker counts from the stopped processes' stderr logs.

For direct strategy iteration without HTTP overhead:

```powershell
.\.venv\Scripts\python.exe tools/benchmark_strategy.py --deals 1000 --seed dev-a dev-b --opponent all --output reports/development.json
```

Use separate, previously untouched seeds for final evaluation. Direct benchmark
timing excludes HTTP/serialization and does not enforce the time bank.

The selected policy passed **123 tests** and fresh-process official HTTP matches
with zero observed judge errors, strategy faults, fallbacks, forfeits or timeouts.
Its slowest charged half was **2.850s locally** and **2.906s in Linux validation**,
below the 4-second release target and official 8-second bank. The
[Linux workflow](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42408822715)
also passed eight additional baseline matches and the official and supplementary
Docker checks. Full-match timings were measured on the hosts; the restricted
container ran smoke checks. The staged CI policy matches the production source
after normalizing line endings.

Historical v1 evidence is retained in [BASELINE_MATRIX.json](docs/BASELINE_MATRIX.json),
[LINUX_VALIDATION.json](docs/LINUX_VALIDATION.json), and
[HEAD_TO_HEAD.md](docs/HEAD_TO_HEAD.md); those files describe the older policy.

To compare a compatible bot from another folder, the helper can manage both
servers and fresh halves automatically:

```powershell
python tools/run_local_match.py --opponent-dir "$env:USERPROFILE\Desktop\heads-up-bundle" --deals 1000 --seed comparison-new-seed --output reports/desktop-comparison.json --logs
```

Run the full official baseline matrix (20 matches, fresh processes per half):

```powershell
.\.venv\Scripts\python.exe tools/evaluate_suite.py --output reports/baseline_matrix
```

Defaults: all four official opponents, seeds 7/19/43/101/202, 1,000 deals per
match. The output directory must be new or empty. Reports include untouched
official verdicts and CIs, charged timing per half, hand logs, runtime versions,
and an exact source snapshot. Each bot half must stay below the 4-second target;
both bots' validity is checked. Our bot must also have zero strategy faults,
fallback decisions and logged fault markers, with the fallback latch inactive.
Missing or malformed evidence fails the gate. The suite saves results and exits
nonzero on any runtime, validity or reliability gate failure, even if the official
verdict is a win. Matches run sequentially to avoid CPU contention.

## What the bot does

The hybrid combines Monte Carlo equity, expected-value heuristics, opponent
adaptation and selective randomized bluffs. The reliability adapter preserves
the existing betting policy when its callbacks succeed.

1. Uses the organizer's exact evaluator: 36 cards; exactly two hole cards and
   three board cards; flush above full house; trips above straight.
2. Estimates showdown equity by sampling disjoint opponent cards and board
   completions. Ties count as half a pot. After a selective opponent raises,
   importance weights favor stronger holdings; habitual aggression receives
   less range narrowing. Only currently visible cards inform these weights.
3. Compares call cost with pot odds, with heuristic adjustments for position,
   future betting, and observed opponent aggression.
4. Uses Bayesian-smoothed fold and aggression counts, including terminal
   responses missing from the next observation.
5. Makes value bets against callers. Mixes occasional nut-draw semi-bluffs,
   nut-flush-blocker river bluffs, and button steals only after sufficient
   evidence that the opponent folds.
6. Chooses from legal actions and reduces rollout counts when computation
   runs ahead of a conservative per-half allowance.

The selected configuration is:

| Setting | Value |
|---|---|
| Range selectivity multiplier | `range_blend=1.3`, actual mix capped at `0.90` |
| Separate caller equity | `caller_power=0.0` (off) |
| Extra samples near decision boundaries | `adaptive_max=0` (off) |
| Position margin | `position="legacy"` |
| Initial samples by street | `24, 32, 40, 64` |
| Core compute pacing | `compute_fraction=0.25`, a 2-second allowance per half |

Sample counts halve when computation runs ahead of pace. Core computation is
different from the official charged HTTP time. Lazy feature computation and
caching preserve sample results while reducing overhead. Separate caller equity,
extra boundary samples and position changes did not justify inclusion in the
tested variants. The big blind acts last preflop but first postflop, so a future
equity-realization margin can still be useful.

Range likelihoods and fold estimates remain heuristic, and Monte Carlo sampling
is noisy. This is the best configuration measured in this search, not a GTO claim.

If a strategy callback raises or returns an invalid action, the adapter logs
`BOT_STRATEGY_FAULT` with a traceback and disables the core for the rest of that
half. Subsequent decisions use a legal conservative fallback: check when free,
otherwise fold. Fault and fallback counters remain outside the strategy's state
and are exposed by the health endpoint. A fresh half resets this state. Fallbacks
keep a recoverable fault from becoming an illegal action; any fallback still
blocks release. The adapter cannot recover process death or interrupt a hang.

## Structure

| File | Purpose |
|---|---|
| `agent.py` | Official FastAPI server with our strategy adapter |
| `reliability.py` | Callback validation, fault logging, fallback latch and health counters |
| `strategy.py` | Selected production profile and callback adapter |
| `advanced_policy.py`, `policy_config.py` | Experimental policies, opponent adjustments and configuration |
| `range_equity.py` | Cached importance-weighted Monte Carlo equity and sampling uncertainty |
| `baseline_strategy.py`, `equity.py` | Frozen v1 policy/equity and shared opponent-accounting helpers |
| `evaluator.py`, `game.py` | Unmodified official evaluation and game rules |
| `judge_engine.py` | Official HTTP judge and duplicate scoring |
| `tools/benchmark_strategy.py` | Fast paired-deal evaluation |
| `tools/run_local_match.py` | Temporary servers and fresh-process HTTP halves |
| `tools/evaluate_suite.py` | Official 20-match matrix and per-opponent summaries |
| `tools/experiment_grid.py` | Controlled direct policy screens using official scoring |
| `tools/package_profile.py`, `tools/validate_profiles.py` | Frozen policy packages and sequential fresh-process validation |
| `tests/`, `test_agent.py` | Evaluator, strategy, opponent model, and API checks |
| `docs/OFFICIAL_GUIDE.md` | Original organizer guide |
| `docs/VALIDATION.md` | Measured results and remaining validation |
| `docs/SCORING.md` | Confirmed ranking, tie-break, and evaluation scorecard |
| `experiments/`, `docs/EXPERIMENTS.md` | Configurations, locked evaluation protocol and complete experiment results |

## Runtime and submission

The official constraints are **8 seconds charged per 1,000-hand half**,
at most **1 second per request**, and **15 seconds startup**. Files are read-only,
there is no external network, and each half uses a fresh process. Learning and
equity caches live only in the per-half `memory` dictionary.

Keep `requirements.txt` at the root and retain the pinned FastAPI/uvicorn versions.
No additional inference library, GPU, Redis, database, or external API is needed.

Before submitting:

- The default participant name is already **Starfish** in `agent.py`.
- Run the fresh-process evaluation suite and require every release gate to pass.
- Run `bash tools/check_build.sh` in Git Bash or WSL with Docker Desktop running.
  This verifies the official Linux image, size, read-only runtime, and smoke cases.
- Run `python tools/check_container_reliability.py` after that check to reject
  hidden strategy faults in the same restricted image. The manual GitHub Actions
  workflow runs both checks on Linux when local Docker is unavailable.
- Push the reviewed bot to the [team repository](https://github.com/shriharish1310/tamu-datathon-poker-bot)
  and submit that exact full commit SHA using the organizer's form. Tournament
  submission has not been performed.

The local development environment was created with `--system-site-packages` and
the organizer-pinned web packages installed inside it; create a clean venv using
the commands above when reproducing on another machine.

## Source and reuse decision

Official starter:
https://github.com/tamu-datathon-org/heads-up-bundle

Imported snapshot: `c83ab6eeb7660a2fd1fae7df224315d41fe985a9`.
Organizer files retain their original comments and rules. Our new strategy,
equity estimator, tests, and local match tooling are separate.

The user's repository search was reviewed. PokerKit is useful reference material,
but its built-in PLO and short-deck variants do not directly match this combination.
PyPokerEngine targets Hold'em, and poker_ai's supplied training setup uses a
different deck. No code from those repositories was copied into this bot.

## Further experiments

Use new development seeds and reserve new final seeds before another search.
The current experiment seeds are now validation history. Calibrated range
likelihoods, offline preflop estimates and more diverse strong opponents remain
useful directions; retain changes only after measuring profit, official points
and runtime on the same opponent pool.
