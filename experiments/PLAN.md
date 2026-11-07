# Starfish experiments — protocol fixed before screening

Baseline: production strategy at commit 1a785d24eb34d7f87414119a7302220097d9628a,
preserved as baseline_strategy.py. The Desktop opponent is the frozen
ShortDeckAce-v2 snapshot already used in the prior head-to-head experiment.

1. Screen all 11 configurations (baseline plus 10 ablations) on exp-dev-A,
   500 duplicate deals, against Desktop, frozen Starfish, and AlwaysPot.
2. Select promising individual settings and combinations for development
   confirmation on exp-dev-B and, if needed, exp-dev-C. Include all four
   official baselines, Desktop, and frozen Starfish; use full 1,000-deal matches.
3. Lock one finalist before opening holdout seeds. Final head-to-head seeds:
   exp-hold-1709, exp-hold-1907, exp-hold-2111, exp-hold-2309, exp-hold-2503.
   Test the finalist against frozen Starfish and Desktop on every seed. Compare
   finalist and baseline against the four official baselines on the first two
   holdout seeds. Preserve individual official confidence intervals.
4. Finalist must also pass fresh-process official HTTP matches, all tests,
   zero observed faults/fallbacks/errors/timeouts/forfeits, and the Docker gate.
   Target less than four charged seconds per half; official maximum is eight.

Development order: official points first, then profit against the stronger
opponents, then average profit across the pool, subject to runtime. A single
screening win is not evidence for release. Keep the old default if holdout
results do not support an upgrade. Report negative and inconclusive results.

Direct simulations use the official game and combine_halves score calculation,
but do not enforce HTTP/time banks. They are screening evidence only. Opponent
state is fresh each half and matches run sequentially. No sample count, range
parameter, threshold or profile is tuned on the holdout outcomes.

Range/caller weights are heuristic likelihood models, not trained ranges or
solvers. Their features use only public boards and sampled opponent holdings;
future runouts are used solely for showdown outcomes. Monte Carlo error excludes
range-model uncertainty. "Best" means best measured within this finite search.

Position deserves an ablation: the big blind acts last preflop but out of
position on later streets, so a preflop realization penalty need not be an error.

## Final lock before opening holdouts

Selected `range_130`: range blend 1.30, caller power 0, adaptive cap 0, legacy
position margin and original sample counts/budget. See FINALIST_LOCK.json.
Confirmation C also tested a near-uniform control with the old scalar penalty
removed; it lost to frozen Starfish. Range weighting itself mattered in that test.

The locked HTTP plan adds baseline-versus-Desktop on all five holdout seeds so
both versions face that opponent on identical deals. Total: 31 full matches,
62,000 played hands. Candidate: five versus frozen Starfish, five versus Desktop,
eight versus the four baselines. Reference: five versus Desktop and eight versus
the four baselines. Versions are interleaved to reduce host-load order effects.
