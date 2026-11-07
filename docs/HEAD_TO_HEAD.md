# Starfish vs Desktop ShortDeckAce-v2 — 2026-11-07

**Observed result: Starfish leads 3–2 official points.** One win, four chops, no losses.
Five independent match seeds, 1,000 duplicate deals per match: **10,000 played hands**.
Both bots used identical official game/evaluator rules. Both servers restarted between
halves, seats were swapped, matches ran sequentially, and source snapshots stayed frozen.
Both server identities were verified in every half. No strategy parameters were tuned.

| Seed | Starfish BB/paired deal | Official 95% CI | Verdict | Points Starfish / Desktop |
|---|---:|---|---|---|
| cmp-1103 | +0.4790 | [-0.4664, +1.4244] | CHOP | 0.5 / 0.5 |
| cmp-1201 | +0.0325 | [-0.8570, +0.9220] | CHOP | 0.5 / 0.5 |
| cmp-1301 | +0.5830 | [-0.3246, +1.4906] | CHOP | 0.5 / 0.5 |
| cmp-1409 | +0.1930 | [-0.6922, +1.0782] | CHOP | 0.5 / 0.5 |
| cmp-1511 | +1.1010 | [+0.1876, +2.0144] | AGENT1_WIN | 1 / 0 |

Starfish averaged **+0.4777 BB per paired deal**, with positive profit on all five
seeds. Four intervals cross zero, so the evidence supports an observed lead, not
a decisive or general tournament-strength claim. No pooled CI was computed.

| Runtime / reliability | Starfish | Desktop ShortDeckAce-v2 |
|---|---:|---:|
| Maximum charged time per half | 2.451947 s | 4.661887 s |
| Mean charged time per half | 2.060158 s | 4.095978 s |
| Judge errors / forfeits / bank exhaustion | 0 / 0 / 0 | 0 / 0 / 0 |
| Internal strategy faults / fallback decisions | 0 / 0 | Not observable |

These timings are from the same local Windows host, outside the tournament
container. Both bots remained under the official 8-second allowance. Starfish
also stayed below our stricter 4-second target in every half.

## Engineering comparison

The Desktop strategy catches every decision exception without logging it and
returns CHECK_CALL whenever legal, including when a bet must be paid. Therefore
zero judge errors cannot show that its intended strategy ran on every decision.
Starfish logs exceptions, records counters separately from strategy memory,
checks when free and otherwise folds; any fallback blocks its release gate.

Use Starfish as the current engineering base. The next strength improvement
should be measured against this frozen Desktop opponent as well as the simple
baselines, with fresh evaluation seeds. Do not select changes from these five
seeds and then present them as unseen validation.

[HEAD_TO_HEAD.json](HEAD_TO_HEAD.json) preserves official metrics, per-half
statistics, source hashes and environment details. Raw reports and the untouched
opponent snapshot remain local under `reports/starfish-vs-desktop-20261107/`.
The original Desktop files were not modified.

## Reproduce one full match

From this repository, with its pinned requirements installed:

```powershell
python tools/run_local_match.py --opponent-dir "$env:USERPROFILE\Desktop\heads-up-bundle" --deals 1000 --seed cmp-1103 --output reports/recheck-desktop.json --logs
```

This starts and stops both loopback servers automatically. A future run uses
whatever source is then in the Desktop directory; compare hashes to reproduce
this snapshot. Starfish adapts sample count to measured runtime, so changing
CPU load can change decisions even on the same shuffled deals.
