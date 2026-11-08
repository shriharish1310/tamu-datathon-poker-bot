# Starfish — teammate_baseline_4 team integration

Starfish's current poker entry integrates our teammate's **teammate_baseline_4** from
[650JoshLee (teammate baseline)](https://github.com/650JoshLee), used with the
author's permission. The original strategy and preflop table are credited to
quad-j. Our integration changes the tournament identity, exposes existing
fallback counters through the health endpoint, and adds the strategy adjustment below.

## Playing approach

Heads-up Short Deck 5-card Pot-Limit Omaha, using precomputed preflop equity,
Numba-compiled Monte Carlo evaluation, opponent-range inference, and bet selection.
The strategy and model data originate from upstream **teammate_baseline_4** at
`987f97aa183cf93cb846afb5cc235664db24a90f`. Later upstream experimental generations
are not included. See [PROVENANCE.json](PROVENANCE.json) for exact hashes.

**Starfish strategy change:** when the estimated continuing range has fewer than
64 effective samples, the bot estimates sampling noise in the pot-raise versus
call EV difference using the same rollouts. The required EV margin ranges from
1.25 to 2 times the original margin, according to that estimate. This is a bounded
heuristic, not a calibrated confidence guarantee. Half-pot selection and the
preflop model remain as upstream.

Health diagnostics expose guard evaluations, rejected pot raises, effective
sample size, approximate EV standard error, and illegal-action corrections.
No additional rollouts or dependencies are introduced.

**Validation status:** this final adjustment was published without further tests
at the team's request. It has not demonstrated an improvement over teammate_baseline_4.

## Run

Use Python 3.12. Keep `data/preflop.npy` beside the bot's source directory.

```sh
python -m pip install -r requirements.txt
python agent.py
```

The HTTP service listens on port 5008, or the tournament-provided `PORT`.
Team identity: **Starfish**. Agent identity: **Starfish-riskguard**.

## Validate

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
bash tools/check_build.sh
```

The official Docker check covers image size, startup, authentication, legal
actions, and the hand-end protocol under tournament restrictions. The release
workflow can be started manually. Automatic checks are disabled for this rushed release.

## Evidence and attribution

Before integration, this exact upstream teammate_baseline_4 defeated the previous Starfish
release in three official 1,000-paired-deal matches. That establishes the direct
matchup in our sample, not general superiority or a tournament placement.
Earlier Starfish benchmark claims describe the previous implementation and do
not apply to this integration.

Game rules, reference evaluator, judge, Docker recipe, and protocol originate
from [the official TAMU Heads Up starter](https://github.com/tamu-datathon-org/heads-up-bundle).
The prior Starfish code remains preserved at `6e5b590` and fallback `fd5c428`.
