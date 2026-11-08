# Starfish

**A range-aware poker bot built for profit under a strict compute budget.**

Starfish plays heads-up **Short Deck 5-card Pot-Limit Omaha** for the TAMU
Datathon Heads Up challenge. It combines Monte Carlo equity, opponent modeling,
pot-odds decisions, and selective bluffs in a lightweight Python service.
The objective is official match points and chip profit, rather than hand-win rate.

**Submission / project link:**
[github.com/shriharish1310/tamu-datathon-poker-bot](https://github.com/shriharish1310/tamu-datathon-poker-bot)

The default branch contains the current release. This public presentation keeps
the playing code and dependencies byte-for-byte identical to the validated
release. No model download, GPU, external API, or database is required.

## Measured results

| Final generalization benchmark | Result |
|---|---:|
| Official match points | **36 / 36** |
| Wins / chops / losses | **36 / 0 / 0** |
| Equally weighted mean points per match | **1.000** |
| Mean profit | **+3.625 BB per paired deal** |
| Across-seed 95% interval for mean profit | **[+2.499, +4.751]** |
| Worst charged bot half | **3.729 s** |
| Observed errors, faults, fallbacks, forfeits, bank exhaustion | **0** |

The frozen bot faced **12 previously unused opponent configurations**, three
new seeds each, with 1,000 paired deals per match: **72,000 played hands**.
Both bots restarted between halves. Matches ran sequentially in restricted
Linux containers. All 72 Starfish halves met our four-second engineering target;
the official bank is eight seconds per half.

These are benchmark results against parameter configurations in six known
opponent families, **not an organizer tournament ranking**. Three seeds give
limited evidence about future opponents, and measured timing is not a runtime
guarantee. See [results, confidence intervals, and provenance](docs/RESULTS.md).

## How it plays

1. **Estimate equity.** Sample legal opponent holdings and board completions with
   the official evaluator. Omaha hands use exactly two private cards and three
   board cards; short-deck hand rankings follow the organizer's rules.
2. **Condition on the opponent.** Importance weighting favors stronger holdings
   after selective raises, with less narrowing against habitual aggression.
   Smoothed fold and aggression estimates adapt within each half.
3. **Choose profitable actions.** Combine equity and pot odds with heuristic
   adjustments for position, future betting, and opponent tendencies. Value bets
   and selective semi-bluffs or blocker bluffs use only decision-time information.
4. **Respect the time bank.** Cache repeated calculations, pace rollout work,
   and serve decisions through FastAPI/Uvicorn with the `httptools` parser.
5. **Make failures observable.** Validate legal actions, log internal faults,
   and expose fault/fallback counters. Any observed fallback blocks release.

The final policy uses simulation and explicit decision rules. It does not use a
trained neural estimator and is not a solved or GTO policy.

## Run locally

Use Python 3.12. From the repository directory:

```bash
python -m venv .venv
```

Activate it with `.\.venv\Scripts\Activate.ps1` on Windows PowerShell, or
`source .venv/bin/activate` on Linux/macOS, then:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python agent.py
```

The bot serves the official HTTP protocol on port **5008**. To run a practice
match instead of starting the server manually:

```bash
python tools/run_local_match.py --opponent random --deals 1000 --seed practice-1
```

The helper starts both servers, restarts them between halves, preserves official
judge JSON and reliability diagnostics, then stops its own processes. Other
practice opponents: `calling`, `half`, and `pot`.

## Docker validation

With Docker running, use Bash, WSL, or Git Bash from the repository root:

```bash
bash tools/check_build.sh
python tools/check_container_reliability.py --output reports/container-reliability.json
```

The first command is the organizer's build/startup/protocol smoke check. The
second inspects internal fault counters and logs in the same restricted image.
The image includes only the required runtime files, excluding research and docs.
The [release-check workflow](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/workflows/reliability.yml)
also verifies that runtime files still match the frozen, match-tested release
before testing.

## Code map

| File | Responsibility |
|---|---|
| `strategy.py`, `policy_config.py` | Frozen production configuration |
| `advanced_policy.py` | Betting decisions and opponent adaptation |
| `range_equity.py`, `equity.py` | Equity sampling, weighting, and caches |
| `baseline_strategy.py` | Shared strategy/accounting helpers required at runtime |
| `reliability.py` | Legal-action checks, fault logging, and diagnostics |
| `agent.py` | FastAPI service and official judge protocol |
| `evaluator.py`, `game.py`, `judge_engine.py` | Official rules, hand evaluation, and scoring |
| `tests/`, `test_agent.py` | Correctness, protocol, and fault-injection tests |

[Devpost project write-up](docs/DEVPOST.md) · [Current benchmark details](docs/RESULTS.md)

Built on the [official Heads Up starter](https://github.com/tamu-datathon-org/heads-up-bundle),
imported at `c83ab6eeb7660a2fd1fae7df224315d41fe985a9`. The organizer's evaluator,
game rules, and judge remain the scoring authority. Historical experiments and
fallback revisions remain available in Git history; the default branch is the
current release entry point.
