# Starfish policy experiments â€” 2026-11-07

**Selected: `range_130_budget25`.** 19 configurations were tested.
The selected default uses range-weighted equity, lazy range features and a 25% compute allocation.
Caller-conditioned raising and extra boundary sampling remain off; the original position margin remains.

## Untouched-seed result

31 full official HTTP matches / 62,000 hands; 1,000 paired deals per match.
Both servers restart between halves. Versions are interleaved and face identical deals.
Configuration and sources were locked before the final five seeds were opened.

Against frozen Starfish v1: **5/5 points**, mean **+1.4292 BB per paired deal**.
On the identical 13-match common pool: **13/13** versus v1's **10.5/13**.

| Opponent | New points | V1 points on same deals | New mean BB/deal | V1 mean BB/deal | Lowest new individual CI bound |
|---|---:|---:|---:|---:|---:|
| desktop | 5/5 | 2.5/5 | +2.2849 | +0.3233 | +0.7913 |
| frozen | 5/5 | opponent | +1.4292 | â€” | +0.4482 |
| calling | 2/2 | 2/2 | +9.7700 | +9.3227 | +8.6312 |
| half | 2/2 | 2/2 | +11.8697 | +11.8443 | +10.5487 |
| pot | 2/2 | 2/2 | +5.7063 | +5.8090 | +3.3170 |
| random | 2/2 | 2/2 | +8.6175 | +8.6707 | +7.2294 |

The CI column is the minimum lower bound of individual official match intervals,
not a pooled confidence interval. Profit units are BB per paired deal.
Paired candidate-minus-v1 profit comparisons are retained separately in the JSON;
they use the official estimator on matched net-chip differences and earn no extra match points.

Maximum selected-bot charged half: **2.849586s**. Zero observed errors,
timeouts, forfeits, strategy faults, fallback decisions or fault-log markers in final validation.
Both bot processes' official validity was checked.

## Configuration to use

```json
{
  "name": "range_130_budget25",
  "range_blend": 1.3,
  "caller_power": 0.0,
  "adaptive_max": 0,
  "boundary_sigma": 0.75,
  "position": "legacy",
  "samples": [
    24,
    32,
    40,
    64
  ],
  "compute_fraction": 0.25
}
```

Range mix is capped at 0.90, using per-street aggression with a Beta(2,6) prior.
Half-pot and pot raises use strength exponents 2 and 3, respectively. The 0.25
compute fraction allocates 2 seconds of the official 8-second bank to core pacing.
Initial samples are halved when ahead of that pace. This allocation is not charged HTTP time.

## Ablation results

Full-length development confirmation B used one seed against six opponents. These
are direct simulations using the official game/scorer, not HTTP release results.

| Configuration | Points / 6 | BB/deal vs v1 | BB/deal vs Desktop | Max direct compute per half |
|---|---:|---:|---:|---:|
| baseline | 6/6 | +0.2295 | +0.8520 | 2.812s |
| range_strong | 6/6 | +0.6715 | +1.7215 | 3.495s |
| range_130 | 6/6 | +0.8850 | +1.7540 | 3.461s |
| callers_light | 4.5/6 | -0.4625 | -0.1020 | 4.143s |
| adaptive_128 | 5/6 | -0.0565 | -0.2425 | 3.924s |
| position_no_preflop | 5/6 | +0.1415 | -0.0565 | 3.221s |
| range_adaptive | 6/6 | +0.6540 | +1.4700 | 3.863s |
| range_callers | 6/6 | +0.4980 | +1.4560 | 3.908s |
| all_four | 6/6 | +0.7815 | +1.5500 | 4.395s |

- Range 1.30 also beat both stronger opponents on confirmation C; the near-uniform
  control that only removed the old penalty lost to v1 by 1.761 BB/deal.
- Caller power 0.5 and 1.0 failed to improve standalone results. Keep this particular
  caller model off; that does not imply caller-conditioned equity is useless in general.
- Caps 96 and 128 and combined variants were tested. After optimization, the cap-96
  combination won its three development matches, but had lower average profit against
  the two stronger opponents and a slower worst half than the selected plain range model.
- Removing/reversing the preflop position margin did not establish an improvement.
  The big blind acts last preflop but first postflop; future realization still matters.
- Wall-clock sample pacing caused even v1 self-play to vary in full-length direct
  screens. Those screens were not used as standalone proof of an upgrade.

## Runtime development

| Optimized profile | Desktop BB/deal | V1 BB/deal | Calling BB/deal | Worst charged half |
|---|---:|---:|---:|---:|
| range_130_budget25 | +3.1455 | +1.5875 | +10.2745 | 2.460s |
| range_130_budget20 | +2.3335 | +1.5955 | +10.3415 | 2.866s |
| range_130_budget25_adaptive | +2.7335 | +1.6230 | +10.3575 | 2.998s |

The first eager 35% candidate was rejected after local halves reached 4.354s and
5.026s. Its 13 completed matches remain in the JSON. The batch was stopped for
the runtime gate, not for profit. Range features are now deferred until needed,
uniform estimates and repeated weight queries are cached, and bit-encoded cards
are retained during rollouts. Fixed-sample results match the frozen eager reference.

## Release checks and limits

123 tests and the selected profile passed the
[Linux workflow](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42408822715),
including eight additional baseline matches, the official Docker build/size/smoke
check, and the independent zero-fault container check under 1 CPU / 4 GB / no network.
The workflow stages the selected wrapper. Its runtime source was checked against the
local validation snapshot with only CRLF/LF line endings normalized.

Python 3.12 [changed floating-point summation](https://docs.python.org/3.12/library/functions.html#sum).
Tiny feature differences can change percentile ties. The optimization regression test
therefore compares against the frozen eager algorithm on the same interpreter, while
retaining the Python 3.10 reference fixtures. It does not weaken the equity tolerance.

This is the best tested configuration in this finite search, not a global optimum.
Range likelihoods remain heuristic and the opponent pool does not represent every team.
All final seeds are now validation history and must not be reused as unseen evidence.

[EXPERIMENTS.json](EXPERIMENTS.json) contains configurations, individual metrics,
confidence intervals, source hashes, rejected runs and Linux/container evidence.
See [the protocol](../experiments/PLAN.md) and [model details](../experiments/METHOD.md).
