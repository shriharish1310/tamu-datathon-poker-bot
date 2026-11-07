# Starfish research leaderboard

Champion: **range_130_budget25**, commit
`fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`, tag `champion-range-130-budget25`.
Production source and configuration remain frozen. Research branch:
`codex/adversarial-pool`.

| Policy | Evaluation pool | Official points | Decision |
|---|---|---:|---|
| Frozen champion | Adversarial batch 01, six selected families, two development seeds | 11/12 | Retain; 10 wins, two inconclusive chops |
| Frozen champion | Previous final validation, Desktop/v1/four official baselines | 18/18 | Historical validation; different pool |
| Any new candidate | No candidate comparison completed in batch 01 | Not evaluated | No promotion |

Do not compare totals across different opponent pools. Batch 01 has no matched
candidate-minus-champion estimate because no candidate was evaluated. The two
range-aware chops are not established wins or established losses.

[Batch 01 results and loss diagnostics](ADVERSARIAL_BATCH01.md) and
[machine-readable leaderboard/evidence](ADVERSARIAL_BATCH01.json) retain all
individual official points, BB/deal, confidence intervals and charged timing.
The 24-screen / 12-confirmation direct runs are included as development evidence.
All 12 held-out opponent configurations remain unevaluated.

Resume: `python tools/adversarial_batch.py run` from the research checkout.
The completed checkpoint was reloaded successfully without rerunning matches.
Raw reports and process logs: `reports/adversarial-batch-01`.

Next priority: calibrate action-conditioned likelihoods against the range-aware
and tight opponents, especially flop pot bets faced from the big blind. Then
test size-specific response/continuation values. The conditional losses do not
prove a decision error; candidate ablations must demonstrate improvement.

Offline learned equity, the bounded MCCFR pilot and population RL remain unrun.
See [the time budget and gates](../experiments/NEXT_BATCHES.md). Development stops
at midnight Central November 8; the final four hours are reserved for validation
and submission preparation before the user's 04:00 deadline.

The [exact champion commit's Docker checks passed](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42410659498).
Any different final submission commit must pass its own official Docker checks.
No tournament submission has been made.
