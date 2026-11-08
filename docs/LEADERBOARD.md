# Starfish research leaderboard

Recommended release: **range_130_budget25 with transport optimizations**, frozen
commit `6e5b590bc922f047de670efdd5fd599f7459a75d`, tag `release-candidate-6e5b590`.
Fallback remains `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`, tag
`champion-range-130-budget25`. Latest research branch: `codex/final-generalization`.

Final generalization: **36/36 official points, 36 wins, no chops or losses**, on
12 previously unevaluated configurations and three locked new seeds each.
Equally weighted mean: **1.000 points/match**, **+3.625069 BB/paired deal**;
across-seed 95% t interval **[+2.498999, +4.751140]**. Worst candidate charged
half: **3.728515s**; all 72 halves below four seconds, with zero faults, fallbacks,
errors, forfeits or bank exhaustion. Exact-commit 127 tests and official Docker
checks passed. [Full final scorecard and all official CIs](FINAL_GENERALIZATION.md).

All 12 held-out configurations and these three seeds are now **consumed final
validation history**. No tuning occurred during this evaluation. If these results
inform another candidate, reclassify the pool as development history and reserve
a new independent final evaluation. These policies share known architectures;
the result is not a claim of tournament dominance.

Batch 04: both champion and candidate earned 6/6 points on the runtime pool.
The candidate reduced median charged time by 21.47%; controlled-clock behavior
matched exactly, while live pacing still varied. [Batch 04 evidence](BATCH04.md).

[Exact submission values](SUBMISSION.md) are prepared. The agent has not submitted
the bot; no organizer receipt was found. Independent teammate submissions remain
unverified. A Git tag or successful CI run is not a tournament submission.

The following entries and notes are preserved **historical Batch 01/02 records**;
their statements that the held-out pool was unused apply at that earlier time.

| Policy | Evaluation pool | Official points | Decision |
|---|---|---:|---|
| Frozen champion | Batch 02, six fixed development opponents, two new seeds | 11/12 | Retain fallback; Windows runtime target missed |
| A50s16 | Same Batch 02 deals/opponents | 11/12 | Reject release: runtime; +0.1145 BB/deal development delta |
| Bz075 | Same Batch 02 deals/opponents | 11/12 | Reject: runtime and -0.6387 BB/deal development delta |
| Frozen champion | Adversarial batch 01, six selected families, two development seeds | 11/12 | Retain; 10 wins, two inconclusive chops |
| Frozen champion | Previous final validation, Desktop/v1/four official baselines | 18/18 | Historical validation; different pool |

Do not compare totals across different opponent pools/seeds. Batch 02 matched
intervals, individual official CIs, configuration hashes and all runtime misses
are preserved in [the full report](BATCH02.md) and [JSON evidence](BATCH02.json).
A's within-batch block interval is positive, but the two seed gains have opposite
signs. Generalization remains inconclusive; neither candidate met the runtime gate.
No A+B combination was justified by the independent screens.

[Batch 01 results and loss diagnostics](ADVERSARIAL_BATCH01.md) and
[machine-readable leaderboard/evidence](ADVERSARIAL_BATCH01.json) retain all
individual official points, BB/deal, confidence intervals and charged timing.
The 24-screen / 12-confirmation direct runs are included as development evidence.
All 12 held-out opponent configurations remain unevaluated.

Resume: `python tools/adversarial_batch.py run` from the research checkout.
The completed checkpoint was reloaded successfully without rerunning matches.
Raw reports and process logs: `reports/adversarial-batch-01`.

Batch 02 completed calibrated action likelihoods and independent response-based
action values. No further heuristic tuning was performed after confirmation.
The fixed champion-defined flop subset did not improve for either candidate;
conditional final-hand losses still do not prove an individual action was wrong.

A bounded learned-equity pilot is complete: 4,000 training / 1,000 independent
check states, a 32-unit hidden layer and exported scalar inference. Uniform-equity
RMSE was 0.0983 versus 0.0760 for champion-style shrunk simulation. Inference was
12-17x faster across corrected timing batches, but this does not establish bot
speed or match performance. Preflop accuracy was promising; turn/river accuracy
was worse. The trained weights are preserved; no expensive training was launched.
MCCFR and population RL remain unrun. All 12 held-out opponent configurations
and final holdout seeds remain untouched.

Resume Batch 02 inside its declared budget with `python tools/batch02.py confirm`.
Raw checkpoints: `reports/batch02`; source/configuration drift is rejected.
The original 90-minute cutoff is fixed at November 7, 18:50:36 Central.
The user clarified 04:00 is an unverified planning assumption, not an official
deadline. No authoritative final freeze is scheduled pending organizer confirmation.

The [exact champion commit's fresh Docker checks passed](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42426541174).
Linux's maximum charged half was 2.113s; that does not erase the Windows misses.
Any different final submission commit must pass its own official Docker checks.
No tournament submission has been made.
