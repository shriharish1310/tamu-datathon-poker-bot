**Batch 04: advance candidate.** Candidate `6e5b590bc922f047de670efdd5fd599f7459a75d` passes the predefined runtime gates; frozen champion `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d` remains the fallback. No strategy or model tuning was performed.

| Version | Official points | Mean BB/paired deal | Bluff-heavy median charged half | Worst charged half | Faults / fallbacks / errors / forfeits / bank exhaustion |
|---|---:|---:|---:|---:|---|
| Champion | 6/6 | +5.008583 | 2.676216s | 3.202339s | 0 / 0 / 0 / 0 / 0 |
| Runtime candidate | 6/6 | +5.008667 | 2.101650s | 2.497638s | 0 / 0 / 0 / 0 / 0 |

Median reduction: **21.47%**. Paired bootstrap 95% interval: [14.52%, 28.07%], resampling five match-pairs with both halves together. The predefined 15% gate uses the measured median; this interval does not establish a reduction of at least 15% with 95% confidence. All 12 measured halves per version were below the four-second engineering target. None exhausted the official eight-second bank. These observations do not guarantee future runtime.

Profit difference: +0.000083 BB/paired deal; descriptive six-match-block 95% t interval [-0.0424, +0.0426]. **Playing-strength improvement is inconclusive.** The release decision concerns runtime. Match scores use the unmodified official judge. Six matches per version cover only two fixed development opponents; they are not a tournament ranking.

| Opponent | Champion points / matches | Candidate points / matches | Champion BB/deal | Candidate BB/deal |
|---|---:|---:|---:|---:|
| bluffy_1 | 5/5 | 5/5 | +5.809600 | +5.802900 |
| range_aware_2 | 1/1 | 1/1 | +1.003500 | +1.037500 |

Equally weighting the two tested opponent families gives 1.0 points/match for both; BB/deal is +3.406550 versus +3.420200. The six-match average above weights the five repeated bluff-heavy runs more heavily. No held-out configurations or unused confirmation/final seeds were opened.

**Profiling and the two changes**

The champion was profiled in the unmodified official Docker recipe on a fresh Linux runner. The trace contained 4,021 decisions and 4,023 POST requests from an already consumed bluff-heavy half. Exclusive times below are non-overlapping profile categories; they include instrumentation and are excluded from the speed gate.

| Component | Profiled exclusive seconds |
|---|---:|
| Other framework/dispatch overhead | 2.717227 |
| Rollout generation/helpers | 0.995365 |
| Parsing/serialization | 0.296473 |
| HTTP protocol processing | 1.164056 |
| Range features/weights | 0.295413 |
| Hand evaluation | 3.390266 |
| Idle/poll | 0.307418 |

Startup import was 0.755207s unprofiled and 1.032688s profiled. Unprofiled replay used 63,296 rollouts; profiling changed pacing to 62,724. Replay charged-equivalent time (2.262681s versus 5.027498s) is diagnostic, not an official scored match.

1. Add pinned `httptools==0.8.0`; Uvicorn selects its native HTTP parser. Installed footprint: 1,803,887 bytes. Both parsers were observed, not inferred from requirements.
2. Return the already primitive `/act` payload using `JSONResponse`, avoiding FastAPI recursive encoding. Profiled `jsonable_encoder` cumulative time was approximately 0.112s.

Both changes are outside the policy computation timer. The evaluator, rollout implementation, parameters, range conditioning, RNG and action-selection source are byte-identical to the champion. The two changes were measured together; their individual contributions were not isolated in this batch. The candidate adds a runtime-file Docker allowlist and four response tests. Research files are excluded from the image and ZIP.

**Equivalence and timing evidence**

All 12,063 controlled decision comparisons passed: 4,021 observations under each of full-budget, half-budget and pacing-boundary clock inputs. Compared exact actions, legal amounts, equity/uncertainty outputs, actual samples, cached rollout streams, RNG states, and opponent memory. A separate full protocol replay also produced identical response-byte hashes. This proves equivalence on the tested inputs with identical clock readings, not all possible observations.

Natural-clock scored runs differed in 99 of 12,000 matched hand action traces. Actual rollout counts below also differ. The unchanged wall-clock pacing makes real elapsed time an input; source equality and controlled checks do not imply bit-identical live trajectories. All per-match profit-difference intervals cross zero.

| Seed / opponent | Order | Baseline half times (s) | Candidate half times (s) | Baseline rollouts | Candidate rollouts | Delta BB/deal [official paired-deal 95% interval] |
|---|---|---|---|---|---|---|
| b03-runtime-13 / bluffy_1 | baseline then candidate | 2.665820, 2.942795 | 2.049626, 2.257423 | 63144 / 62580 | 63204 / 62428 | +0.0140 [-0.1022, +0.1302] |
| b03-runtime-37 / bluffy_1 | candidate then baseline | 2.528226, 2.342974 | 2.497638, 1.996586 | 62292 / 63120 | 62008 / 63156 | -0.0590 [-0.2130, +0.0950] |
| b03-runtime-73 / bluffy_1 | baseline then candidate | 2.730062, 2.489177 | 2.168405, 2.004367 | 62032 / 62484 | 62460 / 62556 | +0.0440 [-0.0144, +0.1024] |
| b02-confirm-29 / bluffy_1 | candidate then baseline | 2.686613, 3.028298 | 2.153674, 2.298578 | 62740 / 62800 | 62780 / 63168 | -0.0375 [-0.1190, +0.0440] |
| b02-confirm-61 / bluffy_1 | baseline then candidate | 3.202339, 2.316500 | 1.940624, 1.829945 | 61768 / 62992 | 61672 / 63396 | +0.0050 [-0.0530, +0.0630] |
| b03-screen-23 / range_aware_2 | candidate then baseline | 2.262231, 2.185636 | 2.117489, 2.236684 | 49088 / 50072 | 49072 / 49980 | +0.0340 [-0.0376, +0.1056] |

Each row used identical deals, frozen opponents and fresh bot/opponent processes between halves. Exactly 12 full official matches (24 scored halves) were run sequentially. The worst half was lower for the candidate within every matched repeat and both opponent families. One individual half regressed: range-aware half 2, 2.185636s to 2.236684s (+0.051048s). This did not exceed that baseline match's worst half (2.262231s); it remains evidence of residual variability.

| Seed | Champion BB/deal [official 95% CI] | Candidate BB/deal [official 95% CI] |
|---|---|---|
| b03-runtime-13 | +5.9555 [+4.9461, +6.9649] | +5.9695 [+4.9560, +6.9830] |
| b03-runtime-37 | +6.3405 [+5.3136, +7.3674] | +6.2815 [+5.2558, +7.3072] |
| b03-runtime-73 | +6.0080 [+4.9885, +7.0275] | +6.0520 [+5.0300, +7.0740] |
| b02-confirm-29 | +5.4810 [+4.4755, +6.4865] | +5.4435 [+4.4395, +6.4475] |
| b02-confirm-61 | +5.2630 [+4.2427, +6.2833] | +5.2680 [+4.2484, +6.2876] |
| b03-screen-23 | +1.0035 [+0.1232, +1.8838] | +1.0375 [+0.1538, +1.9212] |

**Environment, validation and remaining uncertainty**

Both benchmark images ran Python 3.12.16 (main, Nov  5 2026, 07:58:20) [GCC 14.2.0], FastAPI 0.156.1, Uvicorn 0.54.0, Starlette 1.10.0, Pydantic 2.14.3 and h11 0.16.0. CPU reported AMD EPYC 9V74 80-Core Processor; each bot had a one-CPU quota and 4 GiB memory, non-root execution, read-only filesystem, 512 MiB `/tmp`, no external network, and dropped capabilities. Judge and opponent ran in separate cgroups. Three-second CPU preflights ranged from 0.1% to 0.6% across the VM. This does not prove exclusive access to the physical host.

Across the 12 halves per version, startup-import median/worst was 0.610/0.633s for baseline and 0.598/0.625s for candidate. Core-computation median/worst was 4.332/4.694s versus 4.143/4.473s. Core time can exceed charged HTTP time because the judge subtracts per-request grace; these are different measurements. Complete per-half decision counts, samples, wall/charged times and cgroup counters are in `BATCH04.json` and the raw artifact.

Exact candidate commit passed **127 tests**, the official Docker build/startup/protocol smoke test, and supplementary restricted-container checks. The validated Docker image is the same immutable image used in all candidate matches. Both players in all matches had zero observed faults, exception fallbacks, judge errors, forfeits or bank exhaustion.

Earlier failures are preserved: the local Docker probe stalled, so measurements used Linux CI; initial unscored replay run 42433778162 failed in the client path, with original stderr unavailable. Failed-connection retry handling and failure logging were fixed before the successful profile. That failure consumed zero scored match slots. No Windows safety claim is made, and the historical Windows/Linux gap remains only partially explained. Profile and benchmark ran on different fresh runners; their absolute timings are not paired. Official-image transitive dependencies also differ from earlier host-based Batch 03 measurements.

**Reproduction and artifact identity**

Benchmark source: `ef4403900a7b0df755648bfc2631282056115088`. Profile source: `b317d760722b53cc257018dbc9c520ba92d3f21e`. Report generator SHA-256: `c66ab851b1b7f31f830deac1ba52a9a660af1b34969129ef0533774709c7df86`. Opponent source is frozen at `b725121` with exact configuration/file hashes in the preserved package manifests.

The following are the executed/reproducible commands; do not dispatch another benchmark within this capped batch. In a clean Linux checkout of the benchmark source:

```bash
python -m pip install -r requirements-dev.txt psutil==7.1.3
docker build -t poker-agent-base:local - < docker/Dockerfile.base
python tools/batch04.py bench
# Profiling was a separate run at the profile source:
python tools/batch04.py profile
```

The harness checked out the exact candidate and executed `python -m pytest -q`, `bash tools/check_build.sh`, and `python tools/check_container_reliability.py`; it then ran the untouched official judge with `--deals 1000 --seed <locked seed> --half 1|2 --logs --json <half.json>` and `judge_engine.py combine`. Exact launch commands, network/resource flags, order and frozen seeds are in `tools/batch04.py` and `experiments/BATCH04_PLAN.json`.

```powershell
gh run download 42434045945 --name batch04-profile --dir reports/batch04-profile
gh run download 42434610957 --name batch04-bench --dir reports/batch04-bench
.\.venv\Scripts\python.exe tools/report_batch04.py
```

Baseline image: `sha256:f1acdf5f810b1adc128cdc0db643fb88c9039525643bbc78e40dee0f796f8ff3`. Candidate image: `sha256:765c155c3f3bfb9508d12663e5f9f9b1f151ee78176278f9348f233c4cde3802`.

[Successful profile](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434045945), [exact-commit validation and all 12 matches](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42434610957). Full gates, source hashes, official per-match statistics, reliability counters and evidence-file SHA-256 hashes are preserved in `BATCH04.json`.

Submission ZIP: `Starfish-6e5b590.zip`, 40,637 bytes, SHA-256 `ae8e1de9360dfcef3ac60262a6cfb3b5e509601076f1c512daceeb2f39c04227`. Every archived file was verified against the exact candidate commit. Its adjacent manifest contains all file hashes. No submission form was posted; default branch and frozen fallback remain unchanged.

**Independent verification (handoff, November 7)**

The `batch04-bench` artifact was re-downloaded and every finding above was recomputed from the raw per-half judge JSON by `tools/verify_batch04_artifact.py`, which does not use `report_batch04.py`. The raw artifact zip (7,109,287 bytes) matches GitHub's recorded digest `sha256:0e15d8f9e66725bb0582a456d32ca4855284ebeb15239d5df55119c0e30ed1fa`; the artifact expires 2026-12-08. All 80 bench evidence hashes stored in `BATCH04.json` match the download; the two unmatched hashes belong to the separate profile artifact.

Confirmed: ledger of exactly 12 complete matches; 6/6 points for each version; every match verdict, mean and official 95% interval recomputed from `paired_bb`, and `paired_bb` rebuilt from the two halves' per-deal nets; worst charged half 2.497638s candidate versus 3.202339s baseline; bluff-heavy median 2.101650s versus 2.676216s (21.47%); all 24 halves below 4s; zero judge errors, skipped calls, timeouts or forfeits and zero reliability faults or fallbacks for either player; three equivalence modes of 4,021 decisions each with byte-identical baseline and candidate output files; identical protocol response hashes; 127 tests passed; official build log ends `ALL CHECKS PASSED`. All 61 archived candidate source files match `6e5b590` and all 16 baseline package files match `fd5c428` (line-ending normalized). Both image digests match their commits' image records. The 17 files in the submission ZIP match `6e5b590`.

Locally, the exact candidate worktree also passed 127 tests on Windows with Python 3.10.11 and 3.13. This local environment resolved Starlette 1.7.0 rather than the image's 1.10.0; Starlette is an unpinned transitive dependency.

**Desktop compatibility check**

One pre-registered, fresh-process full match on new seed `cursor-desktop-6e5b590-20261107-a`, run with the candidate's unmodified `tools/run_local_match.py`: frozen candidate worktree at `6e5b590` versus a read-only snapshot of the Desktop `heads-up-bundle` bot. Both sources were hashed before and after; the Desktop project was never written and its bot is byte-identical to the `ShortDeckAce-v2` snapshot used in earlier comparisons.

| Bot | Points | BB/paired deal [official 95% CI] | Charged halves (s) | Calls | Errors / timeouts / forfeits | Faults / fallbacks / log faults |
|---|---:|---|---|---|---|---|
| Starfish / ReveillePLO (`6e5b590`) | 1 | +1.799 [+0.861, +2.737] | 5.010, 4.835 | 4103, 4119 | 0 / 0 / 0 | 0 / 0 / 0 |
| TAMU Datathon Team / ShortDeckAce-v2 | 0 | −1.799 | 7.708, 7.404 | 3469, 3494 | 0 / 0 / 0 | not observable |

This is one match against one opponent; it is a compatibility check, not a strength estimate. An older Starfish (`f7941ca`, before range weighting) scored 3/5 points and +0.478 BB/deal against the same Desktop bot; the two are not a controlled comparison. Starfish's charged time is above the 4s engineering target but within the exact champion's earlier Windows range of 2.939–7.163s (Batch 03); the official Linux container measurement remains the relevant release number. The Desktop bot used 96% of its eight-second bank in half 1, and it suppresses its own decision exceptions. It ran under the candidate's interpreter, which includes `httptools`. Raw logs and hashes are in `BATCH04_VERIFY.json`.
