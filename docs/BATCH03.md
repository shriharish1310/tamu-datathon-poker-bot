# Batch 03: runtime diagnosis and preflop-only learned equity

**Champion remains `range_130_budget25` at `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.**
Hybrid decision: **inconclusive; retain champion**. All matches are development-only; the 12 held-out configurations and final holdout seeds remain unused.

## Official comparison

Primary environment: fresh Linux runner, Python 3.10.11, h11. Models were selected using estimator-selection data before estimator-test or match results.
All policies use matched deals, fixed opponents, interleaved order, and fresh processes between halves. Points are official verdict points, equally weighted across opponents.

| Policy | Points | BB/paired deal | Matched delta [95% block CI] | Worst charged half | Faults / exception fallbacks / errors / forfeits / timeouts |
|---|---:|---:|---|---:|---|
| raw | 2.5/4 | +0.4404 | reference | 4.274s | 0/0/0/0/0 |
| observed | 2.5/4 | +0.4684 | +0.0280 [+0.0030, +0.0612] | 4.346s | 0/0/0/0/0 |
| hybrid | 2.5/4 | +0.3039 | -0.1365 [-0.2800, +0.0028] | 3.452s | 0/0/0/0/0 |

Six-family confirmation was not justified by the predefined screen gate; no confirmation seeds were consumed.

The block intervals are exploratory. Only two independent seeds were used; adaptation crosses block boundaries. The wider two-seed Student-t interval and each official per-match CI are preserved in [BATCH03.json](BATCH03.json).

| Opponent | Exact champion points / BB per deal | Instrumented champion points / BB per deal | Hybrid points / BB per deal |
|---|---|---|---|
| range_aware_2 | 1.5 / +0.8808 | 1.5 / +0.9367 | 1.5 / +0.5885 |
| champion | 1 / +0.0000 | 1 / +0.0000 | 1 / +0.0193 |

## Runtime evidence

The earlier 6.278s Windows and 2.113s Linux maxima used different opponent pools and Python versions. They were not a controlled operating-system comparison. Request counts were nevertheless similar: Windows had 3,973 calls and 10.244636s HTTP wall time; Linux had 3,948 calls and 6.060094s HTTP wall time. Historical actual samples and core times were not captured, so the original gap cannot be causally reconstructed.
This batch repeats the same three seeds against frozen bluffy_1, interleaving exact and instrumented champion. Linux comparisons run sequentially before any container builds. Windows background load failed the idle preflight, so those measurements are diagnostic only.

| Environment, exact champion | Charged half range | Policy wall-time range | Actual rollouts/half | Decisions/half |
|---|---:|---:|---:|---:|
| windows | 2.939–7.163s | 3.897–5.740s | 61672–62832 | 3946–4021 |
| linux310 | 4.329–4.614s | 4.826–4.944s | 61864–62796 | 3945–4022 |
| linux312 | 3.686–4.171s | 4.661–4.841s | 61892–62892 | 3945–4022 |

Configured rollout counts remain 24/32/40/64. Wall-clock pacing halves those budgets when ahead of allowance; the detailed report includes actual sample histograms. Preflop model savings can change subsequent pacing even though postflop source is identical.
The read-only exact-control probe runs after all charged requests. Instrumented controls add counters/CPU timers; their changed action trajectories are measured separately. Core CPU time is available for instrumented controls; original core wall time and total actual samples are available for exact champion.
HTTP wall minus policy wall includes serialization, server/client handling, scheduling, callbacks, and transport. It is not pure network latency. Official charged time subtracts at most 1ms per request, so it must not be equated with core time.
Eight charged seconds is the official limit; four seconds is our engineering target. Repeated Linux host results are not a guarantee under tournament container CPU quotas, physical-host contention, or other platforms.

### Parser ablation

| Forced parser, same Linux Python 3.10 host | Charged half range | Mean charged half |
|---|---:|---:|
| h11 | 2.555–2.821s | 2.654s |
| httptools | 2.165–2.287s | 2.224s |

Parser order is h11/httptools, httptools/h11, h11/httptools across the three seeds. CPU clock/thermal state, core scheduling on the Windows laptop, transient background activity, and cloud physical-host contention were not individually controlled. These remain possible contributors, not proven causes.

## Estimator quantity and calibration

The model predicts preflop showdown equity against uniformly sampled legal opponent holdings and runouts. It is used only when both range_mix and caller_power are zero. Positive range weights always materialize the original seeded Monte Carlo stream. The same is true for an out-of-support prediction; that bounded route has its own counter and is not an exception fallback.
The unchanged policy receives the predicted mean with its existing virtual n=12 or n=24 shrinkage count. This is not a claim that model predictions used those rollouts. Value-gate uncertainty is max(0.025, sqrt(p(1-p)/(n-1))); it is a conservative proxy, not a measured Monte Carlo SE for the model. Actual simulated trials and virtual counts are logged separately.
Train/selection/test contain 6,000/1,000/1,000 disjoint canonical five-card configurations. Canonicalization takes the minimum hand over all 24 suit permutations. Official-evaluator labels use 256/1,024/2,048 rollouts per state. Opponent holdings are sampled from the full legal space, without filtering on showdown participation.
MLP: 55 features, one 32-ReLU hidden layer, Adam, alpha=.03, learning rate=.002, max_iter=200, early stopping, random_state=3107. Tree: 12 ExtraTrees, depth 10, min leaf 5, one training thread, same random state. Selection criterion was independent selection RMSE; only the selected MLP entered match screening.

| Range mix / power | Label mean MC SE | MC12 RMSE | MC24 RMSE | MLP hybrid RMSE | Tree hybrid RMSE | Hybrid bias / ECE | Route |
|---|---:|---:|---:|---:|---:|---:|---|
| 0.0:2.0 | 0.0107 | 0.1380 | 0.0990 | 0.0177 | 0.0198 | +0.0015 / 0.0028 | model |
| 0.35:2.0 | 0.0110 | 0.1412 | 0.1021 | 0.1021 | 0.1021 | -0.0042 / 0.0710 | unchanged_MC24 |
| 0.65:2.0 | 0.0121 | 0.1539 | 0.1122 | 0.1122 | 0.1122 | -0.0047 / 0.0772 | unchanged_MC24 |
| 0.65:3.0 | 0.0132 | 0.1686 | 0.1233 | 0.1233 | 0.1233 | -0.0050 / 0.0839 | unchanged_MC24 |
| 0.9:3.0 | 0.0153 | 0.1954 | 0.1432 | 0.1432 | 0.1432 | -0.0052 / 0.1018 | unchanged_MC24 |

Nonzero-range rows measure retained simulation, not learned range-conditioned accuracy. ECE is the sample-weighted absolute gap between mean predictions and mean labels in fixed 0.1-wide bins. Calibration bins and boundary disagreements by range are in BATCH03.json. Boundary probes exclude labels whose 95% MC interval overlaps the threshold; small tail groups are descriptive only and are not evidence of action regret.

### Feature extraction, inference, and startup

- MLP32: 123.1 microseconds/state, median of three interleaved local passes; local load is not claimed isolated.
- ExtraTrees12_depth10: 32.8 microseconds/state, median of three interleaved local passes; local load is not claimed isolated.
- MC24: 1244.5 microseconds/state, median of three interleaved local passes; local load is not claimed isolated.
- raw: worst server startup 0.763s; worst model-file load 0.000000s; model states 0; OOD Monte Carlo routes 0.
- observed: worst server startup 0.763s; worst model-file load 0.000000s; model states 0; OOD Monte Carlo routes 0.
- hybrid: worst server startup 0.763s; worst model-file load 0.000715s; model states 7166; OOD Monte Carlo routes 0.

## Reproduction and preserved evidence

- Policy/model experiment source: `82beb8f0f05588eb79124cc12b4a38f2498808dc`.
- Parser diagnostic source: `87e85d31d2a7fc4d03f91b96124739c4ffe829ad`.
- Selected model SHA-256 (canonical LF): `2b0d8e26888d5c44c38a2a52912eb10b5e6191cbddcaabd17011f4c8cfabf40e`.
- Tree checkpoint SHA-256 (canonical LF): `699723eedf45a6a9e22d6fbf9eb330b49b3a5b164cb7283637ff790a29da42eb`; preserved in experiments/batch03_tree_weights.json, not match-screened.
- Label artifact SHA-256: `735728cc8d49c866056b28ade32fa3e940ef65dcdd51e6f6620a59b5b6bbe646`.
- Full package hashes, dependency versions, official JSON CIs, reliability counters, startup logs, and CPU telemetry are retained under reports/batch03. Compact evidence is in BATCH03.json; reports/batch03/leaderboard.json is the resumable leaderboard.
- Initial incomplete diagnostic attempts are preserved in reports/batch03-initial-audit-bug and CI 42429523850. The probe fix changed no policy or model. Earlier Batch02 timing failures remain untouched.

```powershell
python tools/batch03_train.py  # regenerate canonical-grouped labels and compare fixed model specifications
python tools/batch03.py init  # recreate exact frozen packages and their hash lock
python tools/run_local_match.py --agent-dir reports/batch03/packages/hybrid --opponent-dir reports/batch03/opponents/range_aware_2 --agent-module batch03_audit_server --collect-batch03-metrics --deals 1000 --seed b03-screen-23 --logs --require-opponent-diagnostics --output reports/replay/hybrid_range_aware_2_b03-screen-23.json
```

Use Python 3.10.11 and experiments/batch03-runtime-requirements.txt for match reproduction. Label/model regeneration additionally uses numpy==2.0.1 and scikit-learn==1.5.1. Offline learning never loads held-out opponent configurations. Model loading occurs at server import, outside timed decisions.
The phase orchestrator enforces the original batch end time; the explicit match command supports later reproduction without changing any frozen policy. Runtime differences can change pacing and therefore decisions despite identical deals.

No candidate was released. Exact fallback fd5c428 already passed official Docker build/smoke and container reliability checks in CI 42426541174. Any eventual changed submission commit still requires its own final Docker checks. No MCCFR, RL, or open-ended training was launched. The organizer deadline/timezone remains unverified.
