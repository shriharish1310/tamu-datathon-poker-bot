# Adversarial opponent batch 01

**Decision: RETAIN frozen `range_130_budget25`.** This batch tested the evaluation pool; no candidate upgrade was promoted.

Champion: `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`. The production branch and its runtime/configuration remain unchanged.

24 independently parameterized configurations across six families were screened on 300 paired deals.
The strongest adversary in each family was selected on that screen, then checked on two new development seeds
at 1,000 paired deals and two additional official HTTP seeds. All 12 held-out configurations remain unused.
These are held-out parameters within known families, not unseen architectures. Policies share evaluator/rollout code.

**Official HTTP: 11/12 points; 24,000 hands.** Both processes restart between halves; matches run sequentially.
Direct screening/confirmation adds 38,400 hands; it does not measure official charged time.

| Family | Selected opponent | Points / 2 | Mean BB/paired deal | Worst match | Lowest individual CI bound | Max charged half |
|---|---|---:|---:|---:|---:|---:|
| range_aware | range_aware_2 | 1/2 | +0.5863 | +0.4350 | -0.3968 | 2.016s |
| tight | tight_3 | 2/2 | +0.9968 | +0.8380 | +0.3433 | 2.627s |
| selective | selective_2 | 2/2 | +1.2280 | +1.1060 | +0.5978 | 2.238s |
| aggressive | aggressive_1 | 2/2 | +2.8480 | +2.2120 | +1.0668 | 2.028s |
| loose | loose_2 | 2/2 | +4.5308 | +4.2465 | +3.2325 | 2.355s |
| bluffy | bluffy_1 | 2/2 | +5.8240 | +5.3475 | +4.3397 | 2.535s |

The CI column is the lowest bound of individual official match intervals, not a pooled CI.
A CHOP is statistically inconclusive. Screening losses selected for extremeness are not proof of an exploit.

## Individual official matches

| Opponent | Seed | Verdict | Points | BB/paired deal | Official 95% CI | Charged seconds |
|---|---|---|---:|---:|---|---:|
| tight_3 | adv-dev-http-01 | AGENT1_WIN | 1 | +1.1555 | [+0.6445, +1.6665] | 1.955s |
| loose_2 | adv-dev-http-01 | AGENT1_WIN | 1 | +4.2465 | [+3.2325, +5.2605] | 2.355s |
| aggressive_1 | adv-dev-http-01 | AGENT1_WIN | 1 | +2.2120 | [+1.0668, +3.3572] | 1.933s |
| selective_2 | adv-dev-http-01 | AGENT1_WIN | 1 | +1.3500 | [+0.8199, +1.8801] | 2.091s |
| bluffy_1 | adv-dev-http-01 | AGENT1_WIN | 1 | +5.3475 | [+4.3397, +6.3553] | 2.315s |
| range_aware_2 | adv-dev-http-01 | CHOP | 0.5 | +0.4350 | [-0.3968, +1.2668] | 2.016s |
| tight_3 | adv-dev-http-02 | AGENT1_WIN | 1 | +0.8380 | [+0.3433, +1.3327] | 2.627s |
| loose_2 | adv-dev-http-02 | AGENT1_WIN | 1 | +4.8150 | [+3.8109, +5.8191] | 2.305s |
| aggressive_1 | adv-dev-http-02 | AGENT1_WIN | 1 | +3.4840 | [+2.3178, +4.6502] | 2.028s |
| selective_2 | adv-dev-http-02 | AGENT1_WIN | 1 | +1.1060 | [+0.5978, +1.6142] | 2.238s |
| bluffy_1 | adv-dev-http-02 | AGENT1_WIN | 1 | +6.3005 | [+5.2845, +7.3165] | 2.535s |
| range_aware_2 | adv-dev-http-02 | CHOP | 0.5 | +0.7375 | [-0.1723, +1.6473] | 1.983s |

## Loss diagnostics

All official action logs were replayed; final nets/pots and marginal partition totals were checked.
Last betting street, button/big-blind position, largest opponent raise in the hand, and final pot size
partition each hand exactly once per dimension.
Decision-context groups also appear in the JSON; a hand is counted once per context but contexts overlap.
These are descriptive final outcomes, not causal decision values or evidence that a fold was wrong.

Below: supported negative slices for the two weakest matchup families. Require at least 200 hands,
100 distinct paired deals and two seeds. No subgroup significance claim is made.

| Opponent | Dimension | Group | Hands | Distinct paired deals | Net BB | Gross lost BB |
|---|---|---|---:|---:|---:|---:|
| tight_3 | largest_opponent_raise | pot | 554 | 522 | -1161.0 | 3220.0 |
| range_aware_2 | final_pot | 10-30BB | 948 | 833 | -668.0 | 2387.0 |
| tight_3 | largest_opponent_raise | half | 827 | 779 | -536.0 | 3352.0 |
| range_aware_2 | largest_opponent_raise | pot | 2834 | 1849 | -455.0 | 13932.0 |
| range_aware_2 | final_pot | <10BB | 2253 | 1536 | -446.5 | 1748.0 |
| range_aware_2 | position | big_blind | 2000 | 2000 | -367.5 | 6907.0 |
| tight_3 | final_pot | <10BB | 3260 | 1812 | -13.5 | 2027.0 |

All slices, including small and nonnegative groups, remain in the JSON. Do not add overlapping dimensions.

Supported decision contexts with the largest negative final outcomes in the weakest matchup:

| Street | Position | Facing | Pot before decision | Hands | Final net BB | Mean BB/hand |
|---|---|---|---|---:|---:|---:|
| FLOP | big_blind | RAISE_POT | <10BB | 427 | -1130.0 | -2.646 |
| FLOP | big_blind | free | <10BB | 1710 | -689.0 | -0.403 |
| FLOP | button | RAISE_POT | 10-30BB | 312 | -315.0 | -1.010 |
| PREFLOP | big_blind | RAISE_POT | <10BB | 414 | -245.0 | -0.592 |
| TURN | big_blind | free | <10BB | 954 | -154.0 | -0.161 |
| TURN | button | RAISE_POT | 10-30BB | 219 | -59.0 | -0.269 |

These groups include folds as well as calls and raises; do not interpret their final losses as the cost of calling.

## Reliability and checkpoint

All observed champion and research-opponent judge errors, internal faults/fallbacks, forfeits and bank exhaustion were zero. Maximum champion charged half: 2.627044s.
The research harness passed 126 tests before the batch; champion itself has 123 tests at its frozen commit.
The [exact champion release workflow](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42410659498) passed without staging another policy, including the official Docker build/size/smoke and supplementary container-fault checks.
Full matches measure host HTTP timing; restricted containers run smoke checks.

Production stays on the champion commit. Research code, inputs and compact results live on `codex/adversarial-pool`.
Local checkpoint: `reports/adversarial-batch-01`; resume the same batch with `python tools/adversarial_batch.py run`.
Each match is retained separately with source locks, fresh-process logs and reliability sidecars.

## Next decision

Prioritize action-likelihood calibration for flop pot bets faced from the big blind and tight opponents' raises,
then test size-dependent response/continuation values as a separate ablation. This batch supplies
development targets, not evidence that either proposed change will improve the champion.
A learned equity estimator and bounded MCCFR pilot remain unrun; population RL has not been justified.
All future candidate comparisons need matched champion runs and newly locked final seeds/configurations.
Stop development at midnight Central on November 8; reserve four hours before the user's 04:00 deadline.

[Machine-readable results](ADVERSARIAL_BATCH01.json) · [Next batches and release protocol](../experiments/NEXT_BATCHES.md)
