# ReveillePLO — TAMU Datathon poker bot

A first competitive baseline for **Heads-Up Short Deck 5-card Pot-Limit Omaha**.
Built on the official tournament engine and HTTP protocol. It is not a solved
poker strategy, and wins against the supplied practice bots do not establish
performance against other teams.

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
The helper uses the same Python interpreter that launches it.

For direct strategy iteration without HTTP overhead:

```powershell
.\.venv\Scripts\python.exe tools/benchmark_strategy.py --deals 1000 --seed dev-a dev-b --opponent all --output reports/development.json
```

Use separate, previously untouched seeds for final evaluation. Direct benchmark
timing excludes HTTP/serialization and does not enforce the time bank.

The frozen baseline scored **20/20 official match points across 40,000 hands**
against the four organizer baselines on seeds 7, 19, 43, 101 and 202. All 40 bot
halves had zero errors, timeouts or forfeits; the slowest charged half was 2.918s.
See [validation details](docs/VALIDATION.md) and the compact
[per-match metrics](docs/BASELINE_MATRIX.json). These are baseline results,
not evidence of strength against other teams.

Run the full official baseline matrix (20 matches, fresh processes per half):

```powershell
.\.venv\Scripts\python.exe tools/evaluate_suite.py --output reports/baseline_matrix
```

Defaults: all four official opponents, seeds 7/19/43/101/202, 1,000 deals per
match. The output directory must be new or empty. Reports include untouched
official verdicts and CIs, charged timing per half, hand logs, runtime versions,
and an exact source snapshot. Each bot half must stay below the 4-second target;
both bots' validity is checked. Matches run sequentially to avoid CPU contention.

## What the bot does

1. Uses the organizer's exact evaluator: 36 cards; exactly two hole cards and
   three board cards; flush above full house; trips above straight.
2. Estimates showdown equity by sampling disjoint opponent cards and board
   completions. Ties count as half a pot. Caches each hand/board estimate.
3. Compares call cost with pot odds, with heuristic adjustments for position,
   future betting, and observed opponent aggression.
4. Uses Bayesian-smoothed fold and aggression counts, including terminal
   responses missing from the next observation.
5. Makes value bets against callers. Mixes occasional nut-draw semi-bluffs,
   nut-flush-blocker river bluffs, and button steals only after sufficient
   evidence that the opponent folds.
6. Chooses from legal actions and reduces rollout counts when computation
   runs ahead of a conservative per-half allowance.

The default rollout counts are 24/32/40/64 by street and can halve under load.
Sampling uncertainty can be substantial. Equity is **against uniformly random
legal holdings**, not an inferred betting range; range adjustments are currently
heuristics. Bluff fold estimates can be affected by selection bias and bet size.
This is an actionable baseline for further measurement, not a GTO claim.

## Structure

| File | Purpose |
|---|---|
| `agent.py` | Official FastAPI server with our strategy adapter |
| `strategy.py` | Betting policy and per-half opponent model |
| `equity.py` | Small, deterministic Monte Carlo equity estimator |
| `evaluator.py`, `game.py` | Unmodified official evaluation and game rules |
| `judge_engine.py` | Official HTTP judge and duplicate scoring |
| `tools/benchmark_strategy.py` | Fast paired-deal evaluation |
| `tools/run_local_match.py` | Temporary servers and fresh-process HTTP halves |
| `tools/evaluate_suite.py` | Official 20-match matrix and per-opponent summaries |
| `tests/`, `test_agent.py` | Evaluator, strategy, opponent model, and API checks |
| `docs/OFFICIAL_GUIDE.md` | Original organizer guide |
| `docs/VALIDATION.md` | Measured results and remaining validation |
| `docs/SCORING.md` | Confirmed ranking, tie-break, and evaluation scorecard |

## Runtime and submission

The official constraints are **8 seconds charged per 1,000-hand half**,
at most **1 second per request**, and **15 seconds startup**. Files are read-only,
there is no external network, and each half uses a fresh process. Learning and
equity caches live only in the per-half `memory` dictionary.

Keep `requirements.txt` at the root and retain the pinned FastAPI/uvicorn versions.
No additional inference library, GPU, Redis, database, or external API is needed.

Before submitting:

- Replace the literal fallback `SET_YOUR_TEAM_NAME` in `agent.py` with the team's
  actual name. Do not rely on a local environment variable being set by judges.
- Run `bash tools/check_build.sh` in Git Bash or WSL with Docker Desktop running.
  This verifies the official Linux image, size, read-only runtime, and smoke cases.
- Push the reviewed bot to a public repository and submit that exact full commit
  SHA using the organizer's form. Publishing/submission has not been performed.

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

## Next performance work

Prioritize opponent-range-conditioned equity, more reliable preflop estimates
trained offline, and testing against diverse competitive policies. Validate any
change on held-out duplicate seeds; retain a change only when its measured
benefit outweighs compute cost and uncertainty.
