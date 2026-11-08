# Starfish: Range-Aware Poker Under Pressure

**Tagline:** A poker bot that combines probability, opponent adaptation, and selective bluffs within an eight-second time bank.

**Project link:** https://github.com/shriharish1310/tamu-datathon-poker-bot

This is prepared project copy for Devpost. It does not indicate that a Devpost
project or tournament entry has been submitted.

## Inspiration

Winning the most hands is not the same as winning at poker. A bot can collect
small pots and give everything back in a few expensive calls. We built Starfish
around a different objective: make profitable decisions against different
opponents while staying reliable under a strict time bank.

## What it does

Starfish plays heads-up Short Deck 5-card Pot-Limit Omaha in the TAMU Datathon
Heads Up challenge. It estimates hand equity, adjusts to observed opponent
behavior, and chooses between folding, checking/calling, half-pot raises, and
pot raises. It combines value betting with selective semi-bluffs and blocker
bluffs, rather than maximizing aggression or hand-win percentage.

Each decision uses the cards and betting information available at that moment.
The bot follows the official evaluator and action protocol, including Omaha's
requirement to use exactly two private cards and three community cards.

## How we built it

We built a modular Python strategy around the official tournament engine.
Monte Carlo rollouts estimate equity against sampled opponent holdings and
future boards. Range weighting makes a selective opponent's raise imply stronger
holdings than habitual aggression. Smoothed opponent statistics feed pot-odds
and expected-value heuristics.

The bot runs as a FastAPI/Uvicorn HTTP service. Cached calculations, bounded
simulation work, and a native HTTP parser reduce overhead without introducing
an external inference service. Legal-action checks, observable fault counters,
and Docker validation make reliability part of the release process.

We evaluated with the organizer's official points and confidence intervals,
paired deals, fresh processes between halves, and frozen opponent versions.
Candidate changes were tested against a frozen champion. The final bot retained
simulation and explicit decision rules; a learned preflop estimator did not
establish a practical improvement and was not promoted.

## Challenges we ran into

The main constraint was total decision time across a half, rather than speed on
one isolated hand. HTTP overhead and host variability mattered alongside hand
evaluation. Time-dependent rollout pacing also meant that making code faster
could change the number of simulations and therefore the decisions.

Statistical uncertainty created another challenge: a promising result on a
small seed set was not enough. We separated development from final validation,
used matched comparisons, and preserved rejected experiments instead of
selecting only favorable runs.

## Accomplishments that we're proud of

- **36/36 official match points** in our final benchmark: 36 wins, no chops or
  losses across 12 previously untouched opponent configurations and three new
  seeds each.
- **+3.625 big blinds per paired deal**, with an across-seed 95% interval of
  **[+2.499, +4.751]**, over 72,000 played hands.
- **Zero observed errors, internal faults, fallbacks, forfeits, or exhausted
  time banks** in that evaluation.
- A worst charged half of **3.729 seconds** in the measured Linux environment,
  below our four-second engineering target and the eight-second official bank.
- **127 passing tests**, official Docker startup/protocol checks, and published
  reproducible evidence.

These results describe our benchmark against six known opponent families, not
an organizer tournament ranking or a guarantee against other teams.

## What we learned

A more complex estimator is useful only if it improves full-match outcomes
within the compute budget. Accuracy, inference speed, bluff frequency, and
showdown wins are diagnostics; they cannot replace official points, profit,
uncertainty, and reliability. Freezing a strong baseline made it easier to
reject changes that looked attractive but did not earn their complexity.

## What's next for Starfish

Future work would test independently designed opponents, improve range
calibration, and revisit learned equity only with a new independent evaluation
pool. The release strategy remains frozen; these are research ideas, not
claimed features of the current bot.

## Built with

Python, FastAPI, Uvicorn, httptools, Docker, pytest, GitHub Actions, Monte Carlo
simulation, opponent modeling, and the official TAMU Datathon Heads Up engine.

## Attribution

Starfish builds on the
[official Heads Up starter repository](https://github.com/tamu-datathon-org/heads-up-bundle).
The official evaluator, rules, and judge determine match outcomes. Our work
adds the strategy, range-weighted equity, adaptation, runtime optimizations,
reliability checks, and evaluation tooling.
