# Champion and remaining-time protocol

Champion is `range_130_budget25` at `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.
CHAMPION.json records canonical source hashes and configuration. Its runtime
files are reconstructed from Git into `reports/champion-fd5c428`; research
changes must not alter that source. The production branch remains at champion.

User deadline: November 8, 2026, 04:00 America/Chicago (timezone inferred from
the user's environment). Stop development at 00:00 Central; reserve 00:00-04:00
for final validation and submission preparation. The batch runner checks that
cutoff before every new match. Started November 7 at approximately 14:16 Central:
about 9h44 of development time and four hours reserved, not an unlimited search.

## Batch 01: stronger evaluation pool

24 configurations across tight, loose, aggressive, selective value, bluff-heavy,
and range-aware families. Each family has independent call/value/raise/bluff/size
parameters. All share the official evaluator and some rollout infrastructure;
this limits algorithmic diversity. Range-aware strength is measured, not assumed.

Screen all configurations on 300 paired development deals. Select the opponent
in each family minimizing champion official points, then BB/deal. Confirm these
six configurations on two other development seeds at 1,000 paired deals each.
Run all six through two full official HTTP matches, sequentially, with fresh
processes between halves. This is adversarial development, not final validation.

Twelve separately generated opponent configurations remain unused. They are
held-out parameters within known families, not unseen policy architectures.
Do not search against them or use them for calibration. Preserve all screens,
including losses and inconclusive matches. Short direct screens do not measure
charged runtime or establish a statistically reliable exploit.

Opponent diagnostics use the same fault adapter as champion. The official game,
evaluator, judge and champion policy remain unchanged. Summaries checkpoint after
each match; individual reports survive interruption. Resume with:

```powershell
python tools/adversarial_batch.py run
```

The same sources and inputs are required. Partial failed matches must be
retained and audited before retrying, rather than counted as completed evidence.
The manifest is the authoritative source lock. BATCH01_INPUTS.json also records
the generated configuration files. No final holdout is consumed by this batch.

## Next development priorities

1. Use sufficiently supported weak matchups to fit action likelihoods. Generate
   offline labeled opponent observations from development policies only. Split
   by paired deal and opponent configuration, not individual actions. Estimate
   action probability conditional on street, facing size, visible strength and
   prior aggression; retain a positive likelihood floor and sparse-cell shrinkage.
   Evaluate held-out development log loss/calibration, then official match points.
2. Model fold/call/raise response probabilities separately for each prospective
   legal size. Include continued betting and future position in continuation
   value; do not treat a raise as an automatic terminal showdown. Ablate sizing
   separately from range calibration on fixed development opponents and deals.
3. Train a small offline equity model with official-evaluator Monte Carlo or
   exact labels. Split by deal/card state, report probability calibration and
   label Monte Carlo error. Benchmark inference plus feature extraction, memory,
   and full-match charged runtime against simulation. Better prediction loss
   alone never promotes a policy.
4. Limit the external-sampling MCCFR feasibility pilot to 15 wall-clock minutes
   and a declared memory cap. Check sampling/unbiased update conventions on a
   small known game first. Record traversals/second, information-set growth,
   memory, and fixed-development-policy performance at checkpoints. Estimate
   achievable remaining traversals before expanding. Any abstraction is an
   approximation; do not label it solved or GTO. Keep champion independent.
5. Start population RL only after measuring complete environment/training
   throughput and demonstrating that useful learning plus comparison matches
   fit before midnight. Do not replace measurements with speculative GPU gains.

Before starting another batch, recalculate actual remaining time and budget its
measurements and comparison matches. Do not use the four-hour reserve for tuning.

## Promotion and release

Compare candidate and champion on matched deals and fixed opponent versions.
Use fresh processes, official per-match verdicts/points/BB-per-deal/CIs, paired
candidate-minus-champion differences, worst opponents, and charged timing.
Use new seeds and held-out configurations only after locking a finalist.
Results opened for final validation never re-enter tuning; preserve inconclusive
results as inconclusive. Select on balanced official points, then profit.

Zero observed internal faults/fallbacks, judge errors, forfeits or exhausted banks;
target every champion/candidate half under four charged seconds. Validate the
opponents too. A prediction model or baseline-only win cannot replace champion.

Before release run the official Docker build/size/smoke and supplementary fault
check on the exact proposed submission commit. Record its full SHA and CI URL;
do not modify that commit after validation. Preparing the submission does not
submit the organizer's form. No submission has been made.
