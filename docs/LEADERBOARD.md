# Starfish research leaderboard

Strategy champion: **range_130_budget25**, commit
`fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`, tag `champion-range-130-budget25`.
This is the frozen fallback. Strategy source and configuration remain frozen.

Release candidate: `6e5b590bc922f047de670efdd5fd599f7459a75d` (`codex/batch04-runtime`).
It is the same strategy with a faster HTTP path (native `httptools` parser and a
direct `JSONResponse`); policy files are byte-identical to the champion. It is a
runtime improvement only; Batch 04 found no evidence of a playing-strength change.
Research branch: `codex/batch04-lab`.

| Policy | Evaluation pool | Official points | Decision |
|---|---|---:|---|
| Runtime candidate `6e5b590` | Batch 04, Linux official image, bluffy_1 x5 + range_aware_2 x1 | 6/6 | Advance on runtime: worst half 2.498s vs 3.202s; profit delta +0.0001 BB/deal, inconclusive |
| Frozen champion | Same Batch 04 deals/opponents | 6/6 | Retain as fallback |
| Runtime candidate `6e5b590` | Desktop ShortDeckAce-v2, one new seed, Windows host | 1/1 | Compatibility check only: +1.799 BB/deal [+0.861, +2.737]; 5.01s charged (Windows) |
| Batch 03 hybrid preflop model | Batch 03 screen, Linux, range_aware_2 + champion | 2.5/4 | Inconclusive; -0.1365 BB/deal vs exact champion (2.5/4); retain champion ([report](BATCH03.md)) |
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
The [candidate `6e5b590` passed its own exact-commit Docker checks and 12 matches](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434610957);
see [Batch 04](BATCH04.md) and the [independent verification](BATCH04_VERIFY.json).
The 12 held-out opponent configurations were first opened by the final
generalization evaluation locked in `experiments/FINAL_GENERALIZATION_LOCK.json`
on `codex/final-generalization`; its results are reported there, not here.
No tournament submission has been made.
