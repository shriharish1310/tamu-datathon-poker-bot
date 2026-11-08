**Final evaluation: release 6e5b590.** Frozen candidate `6e5b590bc922f047de670efdd5fd599f7459a75d`; fallback `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.

Equally weighted official match points: **1.000000 per match (36/36 points)**. Results: 36 wins, 0 chops, 0 losses. Each configuration receives weight 1/12 and each of its seeds weight 1/3. Mean profit: **+3.625069 BB/paired deal**; across-seed 95% t interval [+2.499, +4.751].

The pre-open protocol was committed at `a16e68f9139a638743c9d085a48bd68b54f7e51e`. The pool matched its original Batch 01 hash and no prior evaluation was found in available records. All 36 locked full matches completed: 1,000 paired deals each, 72,000 played hands total, fresh processes between halves, sequential execution on one fresh Linux runner, and no concurrent training. No candidate or opponent parameters were changed.

| Configuration | W / C / L | Points / 3 | BB/paired deal | 95% interval across 3 seeds | Worst charged half (s) |
|---|---:|---:|---:|---|---:|
| tight_held_0 | 3 / 0 / 0 | 3 | +0.7870 | [+0.104, +1.470] | 2.665291 |
| tight_held_1 | 3 / 0 / 0 | 3 | +1.4555 | [+0.711, +2.200] | 2.730839 |
| loose_held_0 | 3 / 0 / 0 | 3 | +5.5525 | [+4.179, +6.926] | 3.129666 |
| loose_held_1 | 3 / 0 / 0 | 3 | +5.9963 | [+3.682, +8.311] | 2.927139 |
| aggressive_held_0 | 3 / 0 / 0 | 3 | +4.1217 | [+2.643, +5.600] | 3.474248 |
| aggressive_held_1 | 3 / 0 / 0 | 3 | +3.6133 | [+2.220, +5.007] | 3.297395 |
| selective_held_0 | 3 / 0 / 0 | 3 | +1.2108 | [+0.213, +2.209] | 3.503644 |
| selective_held_1 | 3 / 0 / 0 | 3 | +2.9418 | [+1.768, +4.116] | 3.728515 |
| bluffy_held_0 | 3 / 0 / 0 | 3 | +8.2723 | [+5.413, +11.131] | 3.551146 |
| bluffy_held_1 | 3 / 0 / 0 | 3 | +6.2075 | [+5.074, +7.341] | 3.096035 |
| range_aware_held_0 | 3 / 0 / 0 | 3 | +1.1513 | [+0.631, +1.671] | 2.982231 |
| range_aware_held_1 | 3 / 0 / 0 | 3 | +2.1907 | [+0.867, +3.514] | 3.043312 |

Seed intervals use three independent match-seed clusters and Student-t df=2. They are not the official per-match confidence intervals. They are wide with only three seeds, are not adjusted for 12 simultaneous comparisons, and cannot establish tournament dominance. A chop means the official match interval includes zero; it is not proof of equal strength.

| Match seed | Mean official points | Mean BB/paired deal across all 12 configurations |
|---|---:|---:|
| final-6e5b590-20261107-a-19f273e4 | 1.000000 | +3.667500 |
| final-6e5b590-20261107-b-62ad8301 | 1.000000 | +3.152042 |
| final-6e5b590-20261107-c-b4c9175e | 1.000000 | +4.055667 |

Across-seed points interval (unclipped): [+1.000, +1.000]. A degenerate interval from identical observed seed scores does not imply zero uncertainty on future seeds or opponents.

Worst matchups, ranked by mean match points then BB/deal:

- `tight_held_0`: 3/3 points; +0.7870 BB/deal; individual seed profits +0.5650, +0.7015, +1.0945; seed interval [+0.104, +1.470].
- `range_aware_held_0`: 3/3 points; +1.1513 BB/deal; individual seed profits +1.3445, +0.9290, +1.1805; seed interval [+0.631, +1.671].
- `selective_held_0`: 3/3 points; +1.2108 BB/deal; individual seed profits +1.3940, +0.7500, +1.4885; seed interval [+0.213, +2.209].

**Official per-match results**

A/B/C refer to the three locked seeds in their listed order. Each cell is BB/paired deal followed by the untouched official 95% CI. Individual verdicts, points, logs and statistics remain in the JSON report and CI artifact.

| Configuration | Seed A: BB [official CI] | Seed B: BB [official CI] | Seed C: BB [official CI] |
|---|---|---|---|
| tight_held_0 | +0.5650 [+0.095, +1.035] | +0.7015 [+0.163, +1.240] | +1.0945 [+0.606, +1.583] |
| tight_held_1 | +1.7330 [+1.064, +2.402] | +1.1375 [+0.411, +1.864] | +1.4960 [+0.751, +2.241] |
| loose_held_0 | +5.5495 [+4.585, +6.514] | +5.0010 [+4.081, +5.921] | +6.1070 [+5.142, +7.072] |
| loose_held_1 | +5.7165 [+4.510, +6.923] | +5.2365 [+4.076, +6.397] | +7.0360 [+5.864, +8.208] |
| aggressive_held_0 | +3.9665 [+2.783, +5.150] | +3.6195 [+2.521, +4.718] | +4.7790 [+3.609, +5.949] |
| aggressive_held_1 | +3.2295 [+2.067, +4.392] | +3.3535 [+2.235, +4.472] | +4.2570 [+3.145, +5.369] |
| selective_held_0 | +1.3940 [+0.909, +1.879] | +0.7500 [+0.275, +1.225] | +1.4885 [+0.984, +1.993] |
| selective_held_1 | +3.4125 [+2.694, +4.131] | +2.4675 [+1.777, +3.158] | +2.9455 [+2.243, +3.648] |
| bluffy_held_0 | +9.0995 [+7.825, +10.374] | +6.9580 [+5.722, +8.194] | +8.7595 [+7.538, +9.981] |
| bluffy_held_1 | +6.0250 [+4.915, +7.135] | +5.8705 [+4.745, +6.996] | +6.7270 [+5.614, +7.840] |
| range_aware_held_0 | +1.3445 [+0.703, +1.986] | +0.9290 [+0.323, +1.535] | +1.1805 [+0.500, +1.861] |
| range_aware_held_1 | +1.9745 [+1.198, +2.751] | +1.8000 [+0.962, +2.638] | +2.7975 [+1.950, +3.645] |

**Runtime and release gates**

Candidate median/max charged half: 2.766622s / **3.728515s**. Halves at or above the four-second engineering target: 0/72. Minimum observed headroom to the official eight-second bank: 4.271485s. Opponent max: 4.763500s. These are observed samples, not a runtime guarantee.

| Participant | Bank exhaustion | Judge errors | Forfeits | Internal faults | Exception fallbacks | Logged faults |
|---|---:|---:|---:|---:|---:|---:|
| Candidate | 0 | 0 | 0 | 0 | 0 | 0 |
| Opponents | 0 | 0 | 0 | 0 | 0 | 0 |

| Locked gate | Passed |
|---|---|
| complete_36 | True |
| average_points_at_least_075 | True |
| each_configuration_at_least_15_points | True |
| each_configuration_positive_mean_profit | True |
| aggregate_profit_seed_ci_positive | True |
| candidate_each_half_under_four | True |
| zero_reliability_failures | True |
| exact_candidate_tests | True |
| exact_candidate_official_docker | True |

The candidate passed its tests and the official Docker startup/protocol checks again before any match. All matches used that same validated immutable image. Runtime was restricted to one CPU quota and 4 GiB per bot, non-root, read-only filesystem, loopback-only network, with separate judge/opponent cgroups. Actual per-half decisions, rollouts, core computation, HTTP charged time, dependency/parser versions, CPU preflights and reliability evidence are preserved in JSON. The physical host is not exclusively controlled; this does not erase earlier Windows timing failures.

**Frozen artifacts and submission status**

Exact submission SHA: `6e5b590bc922f047de670efdd5fd599f7459a75d`. Evaluation harness SHA: `aea0985877efe459579581dc7310fafffd51d2a9`. Validated image: `sha256:802ea8bdafa7f5a249f290ab49867a6455e957090b5fc744da8d5c37968f4d75`. Fallback remains `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`. No model or strategy tuning occurred during this final evaluation.

Prepared ZIP: `Starfish-6e5b590.zip`; SHA-256 `ae8e1de9360dfcef3ac60262a6cfb3b5e509601076f1c512daceeb2f39c04227`. Its files were rechecked against the exact candidate Git objects. No new candidate was created.

**Submission status: not submitted by this agent.** Team registration is confirmed, but no organizer submission receipt for this SHA was found in the connected account or project records. A separate submission by another team member is not verified. A Git push, ZIP, successful CI run or registration email does not constitute tournament submission.

[Final Docker checks and complete evaluation](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42440992607). Raw artifact: `final-generalization`; local path: `reports/final-generalization`. The machine-readable report includes all source/evidence hashes and every official match result.

Executed commands (Linux runner):

```bash
python -m pip install -r requirements-dev.txt psutil==7.1.3
docker build -t poker-agent-base:local - < docker/Dockerfile.base
python tools/final_generalization.py --check
python tools/final_generalization.py
```

Report-only reproduction (does not run matches):

```powershell
gh run download 42440992607 --name final-generalization --dir reports/final-generalization
.\.venv\Scripts\python.exe tools/report_final_generalization.py
```

**Evaluation pool status:** consumed final validation history. These 12 configurations are held-out parameters within six known families sharing evaluator/rollout code, not 12 independently designed competitor architectures. If these results inform any new candidate, mark this pool and its three seeds as development history and reserve a new independent final evaluation. Do not tune and then reuse this pool as untouched evidence.
