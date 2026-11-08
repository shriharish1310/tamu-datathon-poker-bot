# Batch 02: independent range and action-value experiments

**Frozen fallback remains `range_130_budget25` at `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.**
All evaluation is development-only; the 12 held-out configurations and final holdout seeds were untouched.

## Comparison

Each confirmed profile played the same six fixed opponents on two predefined seeds: 12 matches / 24,000 hands.
All matches use the official HTTP judge with fresh processes between halves. Points are equally weighted.
Opponent order below: tight / loose / aggressive / selective / bluff-heavy / range-aware.

| Policy | Configuration | Points / 12 | Mean BB/deal | Paired delta [95% block interval] | Points by opponent | BB/deal by opponent | Worst charged half | Faults/fallbacks/errors/timeouts/forfeits | Decision |
|---|---|---:|---:|---|---|---|---:|---|---|
| champion | Frozen range 1.3, budget .25 | 11/12 | +2.5106 | reference | 2 / 2 / 2 / 2 / 2 / 1 | +0.791 / +4.345 / +3.141 / +0.746 / +5.439 / +0.602 | 6.278s | 0/0/0/0/0 | retain frozen fallback |
| A50s16 | A blend 0.5, shrink 16 | 11/12 | +2.6251 | +0.1145 [+0.0148, +0.2108] | 2 / 2 / 2 / 2 / 2 / 1 | +1.026 / +4.397 / +3.468 / +0.668 / +5.584 / +0.607 | 6.509s | 0/0/0/0/0 | reject |
| Bz075 | B z=0.75, risk=0.01, .65s action budget | 11/12 | +1.8719 | -0.6387 [-0.8566, -0.4219] | 2 / 2 / 1.5 / 2 / 2 / 1.5 | +0.709 / +2.996 / +1.293 / +0.886 / +4.924 / +0.424 | 6.437s | 0/0/0/0/0 | reject |
| A+B | Not justified by independent screens | Not run | — | — | — | — | — | — | No combination experiment |

Paired delta intervals resample 100-deal blocks with seats and all opponents kept together (5,000 resamples).
These are exploratory development intervals, not official match verdicts or a new scoring rule.
Individual official CIs and per-opponent/seed matched improvement intervals are preserved in BATCH02.json.
Only two confirmation seeds were used; no claim of generalization to held-out configurations follows.
A separate Student-t interval over the two independent seed means is also retained in the JSON; it is much wider and crosses zero for both candidates.

## What was tested

- A replaces part of champion weights with a hierarchical empirical action likelihood. Separate half/pot labels, street, board texture, prior raises, facing size and smoothed aggression enter the model. Strength uses only currently visible cards. Blend/shrink settings: .25/32, .50/16, .50/64. ESS below 45% triggers uniform shrinkage.
- Training uses all simulated opponent actions including folded holdings. This avoids showdown-only selection, but remains biased toward the six development policies and their state occupancy against champion. The check seed was separate from training; no held-out configurations were used.
- B retains champion range weights. It compares legal check/call and raise sizes via modeled fold/call/raise responses, official game stack/raise rules, shared sampled holdings/runouts, a conservative one-response continuation proxy and uncertainty/risk deductions. It does not solve future betting.
- B has a .65-second per-half action-comparison allocation; beyond its pace it explicitly uses champion decisions. These budget branches are counted separately from exception fallbacks. The model-decision fraction is recorded below.

## Diagnostics

- A50s16: minimum calibrated ESS fraction 45.0%; ESS shrink events 511; modeled action fraction not applicable; worst opponent range_aware_2; worst individual match +0.3355 BB/deal.
- Bz075: minimum calibrated ESS fraction not applicable; ESS shrink events 0; modeled action fraction 37.0%; worst opponent range_aware_2; worst individual match -0.2635 BB/deal.

Champion, A and B each had six of 24 Windows confirmation halves at or above the four-second target. Zero observed faults/fallbacks/errors/forfeits/bank exhaustion does not make those runtime gates pass.

The targeted flop subset is defined using champion hands, then those same indices are compared across policies.
This prevents selecting a different subgroup after a policy changes play. Outcomes remain descriptive, not proof of a bad action.

| Profile | Matched target hands | Net BB | Mean BB/hand |
|---|---:|---:|---:|
| champion | 405 | -536.00 | -1.3235 |
| A50s16 | 405 | -665.00 | -1.6420 |
| Bz075 | 405 | -676.00 | -1.6691 |

## Reproduce and resume

```powershell
python tools/calibrate_actions.py
python tools/batch02.py init
python tools/batch02.py screen
python tools/batch02.py confirm
python tools/report_batch02.py
```

Batch01 raw logs must be present for calibration. Existing checkpoints require identical source/configuration hashes.
Frozen packages, exact source hashes, official JSON, logs and reliability evidence are in reports/batch02.
Pilot commands: `python tools/learned_equity_pilot.py` then `python tools/benchmark_equity_checkpoint.py`. Exported weights are also preserved in experiments/batch02_learned_equity_weights.json.
The original 90-minute cutoff is enforced by the runner; reproducing after that cutoff requires a new declared batch budget.

## Deadline and release

The live organizer guide still contained a deadline placeholder; the submission form did not specify a deadline.
The user confirmed 04:00 is an unverified planning assumption and is checking with organizers. No authoritative final freeze was scheduled.
Champion passed fresh official Docker checks on its exact commit in [run 42426541174](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42426541174). No new submission commit was released.
Windows confirmation recorded multiple runtime-target misses, including champion. These remain failures of the local 4-second gate even though Linux validation passed. Their cause is unresolved; no selective reruns replaced them.
Any eventual different submission commit requires its own official Docker checks.

[Full metrics and source hashes](BATCH02.json)

## Bounded learned-equity pilot

Uniform-opponent equity only: 4000 training / 1000 independent check states, official-evaluator labels.
Full direct-game throughput: 75.9 hands/s and 502.2 decisions/s, excluding HTTP/startup.
Label throughput 20903 rollouts/s; label generation 42.9s; fitting 0.50s.
Model RMSE 0.0983; simulation RMSE 0.0833; label mean MC SE 0.0188.
Champion-style uniform shrinkage RMSE: 0.0760. The full-sample uniform control does not include range conditioning or runtime sample halving.
Feature extraction + scalar inference 103.0us versus simulation 1739.8us (16.90x).
Speed uses the median of three alternating-order passes; both corrected timing batches are retained (12.45x and 16.90x batch ratios). Complete-game throughput varied from 76 to 123 hands/s between the original and corrected-benchmark runs.
The benchmark correction used production Rollouts and nonoverlapping calibration bins. Original benchmark evidence was retained; labels and trained weights remained byte-identical. No model retuning occurred.
This measures feasibility only. The estimator has no range-conditioning or official match-performance evidence. No expensive training or production replacement was launched.
