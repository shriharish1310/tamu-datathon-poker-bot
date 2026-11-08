# Current release: results and provenance

Starfish's public release uses the validated playing code from
`6e5b590bc922f047de670efdd5fd599f7459a75d` (`range_130_budget25`). Presentation and CI
documentation may have newer commits; the release-check workflow enforces
identical runtime, dependency, and Docker build files. The original release and
fallback remain frozen at their existing tags.

## Final generalization benchmark

Before opening the opponent pool, the candidate, equal configuration weights,
three seeds, 36-match count, and acceptance criteria were locked at
`a16e68f9139a638743c9d085a48bd68b54f7e51e`.
Each of 12 configurations had weight 1/12; each of its three seeds had weight 1/3.
Each full official match used 1,000 paired deals and fresh processes between
halves. All 36 matches ran sequentially with no training or parameter changes.

**36 wins, 0 chops, 0 losses; 36/36 official points.** Equally weighted points per
match: **1.000**. Mean profit: **+3.625069 BB/paired deal**. The 95% Student-t
interval across three common-seed clusters (df=2) is **[+2.499, +4.751]**.
The official confidence interval excluded zero in our favor in every match.

| Opponent configuration | W / C / L | Points / 3 | BB/paired deal | 95% interval across seeds | Worst charged half (s) |
|---|---:|---:|---:|---|---:|
| Tight 0 | 3 / 0 / 0 | 3 | +0.7870 | [+0.104, +1.470] | 2.665291 |
| Tight 1 | 3 / 0 / 0 | 3 | +1.4555 | [+0.711, +2.200] | 2.730839 |
| Loose 0 | 3 / 0 / 0 | 3 | +5.5525 | [+4.179, +6.926] | 3.129666 |
| Loose 1 | 3 / 0 / 0 | 3 | +5.9963 | [+3.682, +8.311] | 2.927139 |
| Aggressive 0 | 3 / 0 / 0 | 3 | +4.1217 | [+2.643, +5.600] | 3.474248 |
| Aggressive 1 | 3 / 0 / 0 | 3 | +3.6133 | [+2.220, +5.007] | 3.297395 |
| Selective value 0 | 3 / 0 / 0 | 3 | +1.2108 | [+0.213, +2.209] | 3.503644 |
| Selective value 1 | 3 / 0 / 0 | 3 | +2.9418 | [+1.768, +4.116] | 3.728515 |
| Bluff-heavy 0 | 3 / 0 / 0 | 3 | +8.2723 | [+5.413, +11.131] | 3.551146 |
| Bluff-heavy 1 | 3 / 0 / 0 | 3 | +6.2075 | [+5.074, +7.341] | 3.096035 |
| Range-aware 0 | 3 / 0 / 0 | 3 | +1.1513 | [+0.631, +1.671] | 2.982231 |
| Range-aware 1 | 3 / 0 / 0 | 3 | +2.1907 | [+0.867, +3.514] | 3.043312 |

These intervals describe variation across three seeds; they are **not** the
official per-match intervals and are not adjusted for multiple comparisons.
All 36 individual official intervals are preserved in the
[full evaluation report](https://github.com/shriharish1310/tamu-datathon-poker-bot/blob/b7e73d632069b9410fcc337b98250194fa5aa498/docs/FINAL_GENERALIZATION.md)
and [machine-readable results](https://github.com/shriharish1310/tamu-datathon-poker-bot/blob/b7e73d632069b9410fcc337b98250194fa5aa498/docs/FINAL_GENERALIZATION.json).

## Reliability and limits of the evidence

The candidate's 72 halves had median charged time **2.766622 s** and maximum
**3.728515 s**, all below our four-second engineering target. The official bank
is eight seconds. Observed bank exhaustion, judge errors, forfeits, internal
faults, exception fallbacks, and logged faults were all **zero** for both sides.
The candidate passed **127 tests**, the official Docker checks, and supplementary
container fault checks before the matches used that same immutable image.

The benchmark used Python 3.12.16, an AMD EPYC 7763 host, a one-CPU quota and
4 GiB per bot, read-only/non-root execution, and isolated local networking.
The host was not exclusively controlled. Prior Windows timing failures remain
part of development history; these Linux measurements do not establish a
cross-platform runtime guarantee.

The weakest measured matchups were Tight 0, Range-aware 0, and Selective value 0.
All remained profitable in this sample, but three seeds and six shared opponent
families cannot establish performance against independently designed teams.
**This is a benchmark result, not an official tournament placement.**

## Reproducible provenance

- Match-tested code: `6e5b590bc922f047de670efdd5fd599f7459a75d`.
- Evaluation harness: `aea0985877efe459579581dc7310fafffd51d2a9`.
- Original evaluated image: `sha256:802ea8bdafa7f5a249f290ab49867a6455e957090b5fc744da8d5c37968f4d75`.
- [Completed Docker checks and 36-match run](https://github.com/shriharish1310/tamu-datathon-poker-bot/actions/runs/42440992607).
- Original validated ZIP SHA-256: `ae8e1de9360dfcef3ac60262a6cfb3b5e509601076f1c512daceeb2f39c04227`.
- Frozen fallback: `fd5c428475eee98edb7c38bd1e7fc0870ddbf42d`.

Frozen policy settings: `range_blend=1.3`, `caller_power=0.0`, `adaptive_max=0`,
`boundary_sigma=0.75`, `position="legacy"`, street sample budgets `(24, 32, 40, 64)`,
and `compute_fraction=0.25`. Actual rollout counts respond to elapsed compute
pacing, so configured budgets alone do not prove behavioral or timing equality.

The consumed final pool is evaluation history. If it informs another strategy,
a new independent pool is required for that strategy's final evaluation.
The public presentation update changes no playing code and runs no new matches.

## Submission link

Submit **https://github.com/shriharish1310/tamu-datathon-poker-bot** in the
organizer's repository field. The observed form asks for an email and repository
URL, with no commit field. The default branch presents the current release.
Repository availability and successful checks do not establish that the form
was submitted or accepted; retain the organizer's confirmation receipt.
