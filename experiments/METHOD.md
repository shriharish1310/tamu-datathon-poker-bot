# What is being compared

These are policy and simulation configurations, not separately trained ML models.
All variants retain the official evaluator, game, raise sizing, and scoring.

## Range-weighted equity

Sample legal opponent holdings and runouts without replacement. Compute a visible
strength ordering for each sampled opponent hand using only its hole cards and
the current public board. Preflop uses rank/pair/connectivity/suit features;
postflop uses the official current made-hand score plus a small flush-draw bonus.
Turn those features into tie-aware empirical percentiles `q`.

For an observed opponent raise on the current street:

```
aggression = raises / (raises + passive)    # per-street Beta(2,6) prior
selectivity = max(0, 0.65 - aggression) / 0.65
mix = min(0.90, range_blend * selectivity * pot_raise_factor)
weight = (1 - mix + mix*q)**raise_power
```

`pot_raise_factor` is 1.15 for a pot raise, otherwise 1.0. `raise_power` is 3
for pot and 2 for half-pot. Without a real raise, or for habitual aggressors
with aggression at least 0.65, weights are uniform. Posting blinds is not a
raise. Existing scalar range penalties are replaced, not added a second time.

The resulting weighted mean estimates showdown pot share against that heuristic
range. It is not an inferred exact posterior or an equilibrium solution. Future
runouts never contribute to the weights. Known private cards remove blocked
holdings from the sample space automatically.

## Equity conditional on continuing

For each prospective half-pot or pot raise, multiply current-range weights by
an increasing continuation likelihood:

```
power = min(5, caller_power * fold_rate / max(0.05, 1-fold_rate))
continuation_weight = (0.05 + 0.95*q)**min(5, power*size_factor)
```

`size_factor` is 1.0 for half-pot and 1.4 for pot. Fold rates use the original
per-street Beta(2,8) prior. These size factors are modeled assumptions, not
size-specific measured response rates. Call/fold decisions use current-range
equity; each value raise uses its own caller-conditioned equity. The original
value thresholds remain fixed to isolate this change.

Weighted estimates report effective sample size `(sum w)^2 / sum(w^2)`.
Shrinkage uses effective sample size; the Monte Carlo error uses a weighted
variance estimate. Neither quantity measures uncertainty in the range model.

## Boundary refinement

Start at 24/32/40/64 trials for preflop/flop/turn/river. Reuse the existing sample
stream and add trials only near a call or value-raise threshold, as measured by
`boundary_sigma * MC_standard_error`. At most 96 or 128 trials are retained per
private hand/public board state. Weighting is recomputed after action-history
changes even when the sampled cards are reused.

Initial screens allocated 35% of the 8-second bank (2.8s) to core computation.
After runtime validation, the selected candidate uses 25% (2.0s), with extra
refinement disabled. Initial samples are halved when ahead of that pace. This
is not a guarantee of charged HTTP time; fresh-process full matches enforce the
actual time bank. Range features are computed only when conditioning needs them;
uniform and repeated weighted estimates are cached.

## Position alternatives

- `legacy`: extra 0.015 realization margin for the non-button before the river.
- `no_preflop`: remove that extra preflop margin, retain it postflop.
- `street_order`: charge the button preflop and non-button postflop.
- `none`: remove all extra position margins.

All-in calls have zero future-realization margin in every variant. The big blind
acts last preflop but first postflop; immediate action order and future equity
realization are different considerations.

## Statistical interpretation

Official points and per-match confidence intervals come from `combine_halves`.
Direct screens use synthetic result wrappers solely for that same calculation;
their runtime is not official charged runtime. Final acceptance uses real HTTP
judge output and reliability sidecars. No pooled CI or alternate scoring rule
is invented. All failed or inconclusive variants remain in the experiment report.
