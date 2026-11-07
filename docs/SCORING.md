# Confirmed tournament objective and evaluation scorecard

Verified 2026-11-07 against the user-provided Heads Up Participant Guide,
page 11, sections 6.2 and 6.3, and the official judge implementation.
PDF source: organizer's Heads Up Participant Guide, supplied by the participant.

## Official ranking

Every bot plays each other bot exactly once in a round robin.

1. Rank by total match points: win = 1, chop = 0.5, loss = 0.
2. Break equal-point ties by average big blinds won per deal across all matches.

Each match has 1,000 duplicated deals played in two fresh-process halves,
with seats swapped: 2,000 played hands. For deal i, let
X_i = (net_chips_half1_i + net_chips_half2_i) / big_blind.
The judge reports mean(X), with CI = mean(X) +/- 1.96 * sample_std(X) / sqrt(N).
An interval strictly above zero wins; strictly below zero loses;
including or touching zero chops. A forfeit overrides chip profit.

BB/100 = 50 * mean(X). Both confidence bounds also multiply by 50.
For 400 net chips over 2,000 hands with a 2-chip blind, mean(X) = 0.2,
and BB/100 = +10.

## Evaluation policy

- Primary: official match points against a diverse, equally weighted pool.
- Tie-break: average official BB/deal; also report conventional BB/100.
- Always expose results per opponent, confidence intervals, and worst losses.
- Runtime/validity gate: no crashes, illegal actions, forfeits or bank exhaustion;
  target strictly less than 4 charged seconds in every half (official limit 8).
- Use the official judge's verdict and JSON fields directly. The quick direct
  benchmark also delegates scoring to judge_engine.combine_halves; no separate
  scoring implementation is maintained. Validate the opponents as well as our bot.
- Opponent pool: random, tight/selective, loose/passive, aggressive, and frozen
  previous versions. The current four organizer baselines alone are insufficient.
- Compare candidate/current on identical deals and opponent policies, swapping
  seats and resetting state. Keep development and final holdout seeds separate.
- Estimate candidate improvement from matched per-deal or independent match-block
  differences; do not infer a difference CI by comparing two separate CIs.
- Screen cheaply, then evaluate promising versions on predefined unseen seeds.
  A difference interval crossing zero is inconclusive. Avoid repeatedly inspecting
  an expanding nominal 95% interval until it first becomes positive.
- Track bluffing, fold rate, and showdown success only as diagnostics.

Because match points saturate at one per opponent, extra profit against one weak
bot cannot replace a lost match point elsewhere. Profit still matters for the
documented standings tie-break. Final decisions should consider both criteria.

## Additional guide findings

- Page 1: team registration is mandatory; one person on multiple teams invalidates
  the team's registration. Reading the form link does not register a team.
- Page 11: 1 CPU, 4 GB RAM, no network; image adds at most 3 GB above the base;
  build must complete within 30 minutes.
- Page 13: latest successful build is used; a failed replacement leaves the
  earlier working submission in place.
- Page 13: the deadline remains an unfilled placeholder in this PDF.
- Page 14: settings may change; updated official game.py is the source of truth
  for numerical game settings.

The PDF's commands `python test_agent.py` do not run the current pytest-style
test functions by themselves. Use `python -m pytest test_agent.py tests -q`,
plus the official Docker build/smoke check before submission.
