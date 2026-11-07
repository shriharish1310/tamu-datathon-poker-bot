"""Fast strategy comparisons using the official game and duplicate scoring.

Development example:
    python tools/benchmark_strategy.py --deals 1000 --seed dev-a dev-b --opponent all

Keep a separate, untouched seed set for final validation, for example:
    python tools/benchmark_strategy.py --deals 1000 --seed holdout-a holdout-b --output results/holdout.json

This runs no HTTP server and deliberately does not enforce the judge's bank.
Its timings are computation measurements, not tournament compatibility checks.
Run judge_engine.py against real servers to validate the actual time bank.
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluator import warmup
import judge_engine
from game import (
    ACTION_TIMEOUT_SECONDS,
    AgentConfig,
    Action,
    Game,
    button_for_deal,
    make_deal,
)

OPPONENTS = ("calling", "half", "pot", "random")


def baseline_action(obs: Any, opponent: str, rng: random.Random) -> Action:
    """Exactly reproduce the four supplied baseline policies without servers."""
    if opponent == "calling":
        return Action.CHECK_CALL
    if opponent == "random":
        return rng.choice(obs.legal_actions)
    target = Action.RAISE_HALF if opponent == "half" else Action.RAISE_POT
    return target if target in obs.legal_actions else Action.CHECK_CALL


def paired_summary(first: list[int], second: list[int]) -> dict[str, Any]:
    """Delegate all scores/verdicts to the official judge; retain CLI field aliases.

    These synthetic result wrappers contain direct-simulation chip outcomes only.
    Their empty AgentStats are not a measured HTTP runtime or validity result.
    Real acceptance checks must read the official HTTP judge's saved JSON.
    """
    if not first or len(first) != len(second):
        raise ValueError("paired halves must have the same positive number of deals")
    halves = [
        judge_engine.HalfResult(
            half=half,
            match_seed="direct-simulation-score",
            num_deals=len(nets),
            agent1_seat=half - 1,
            nets_agent1=list(nets),
            nets_agent2=[-value for value in nets],
            stats_agent1=judge_engine.AgentStats(),
            stats_agent2=judge_engine.AgentStats(),
        )
        for half, nets in enumerate((first, second), 1)
    ]
    official = judge_engine.combine_halves(*halves).to_dict()
    verdict_alias = {
        judge_engine.AGENT1_WIN: "WIN",
        judge_engine.AGENT2_WIN: "LOSS",
        judge_engine.CHOP: "CHOP",
        judge_engine.BOTH_FORFEIT: "LOSS",
    }
    return {
        "mean_bb_per_paired_deal": official["mean_bb_per_deal"],
        "std_bb": official["std_bb"],
        "stderr_bb": official["stderr_bb"],
        "ci95_bb": official["ci"],
        "verdict": verdict_alias[official["verdict"]],
        "official_verdict": official["verdict"],
        "points": official["points"]["agent1"],
        "paired_bb": official["paired_bb"],
    }


def play_half(strategy: Any, opponent: str, deals: int, seed: str, seat: int) -> dict[str, Any]:
    """Play one fresh-memory half; only public observations reach the strategy."""
    config = AgentConfig(num_hands=deals)
    memory: dict[str, Any] = {}
    start = time.perf_counter()
    strategy.new_half(config, memory)
    init_seconds = time.perf_counter() - start
    # The official RandomBot explicitly uses the same fixed seed each half.
    opponent_rng = random.Random(0)
    pending: list[Any] = []
    nets: list[int] = []
    actions: Counter[str] = Counter()
    choose_seconds = callback_seconds = max_decision_seconds = 0.0
    callbacks = 0
    total_start = time.perf_counter()

    def deliver_results() -> None:
        nonlocal callback_seconds, callbacks
        if not pending:
            return
        callback_start = time.perf_counter()
        for result in pending:
            strategy.on_hand_end(result, memory)
            callbacks += 1
        pending.clear()
        callback_seconds += time.perf_counter() - callback_start

    for index in range(deals):
        game = Game(make_deal(seed, index), button_for_deal(index), hand_index=index)
        while not game.is_terminal:
            obs = game.observation(game.to_act)
            if game.to_act == seat:
                # The HTTP judge batches completed hands into the next /act.
                deliver_results()
                started = time.perf_counter()
                action = strategy.choose_action(obs, memory)
                elapsed = time.perf_counter() - started
                choose_seconds += elapsed
                max_decision_seconds = max(max_decision_seconds, elapsed)
                if not isinstance(action, Action) or action not in obs.legal_actions:
                    raise AssertionError(
                        f"Illegal strategy action {action!r}, hand={index}, "
                        f"seat={seat}, street={obs.street.name}, legal={obs.legal_actions}"
                    )
                actions[action.name] += 1
            else:
                action = baseline_action(obs, opponent, opponent_rng)
            game.apply(action)
        result = game.hand_result(seat)
        nets.append(result.my_net)
        pending.append(result)
    deliver_results()  # Equivalent to the judge's final /hand-end request.

    direct_seconds = init_seconds + choose_seconds + callback_seconds
    warnings = []
    if direct_seconds > config.time_bank_seconds:
        warnings.append("Direct computation alone exceeds the official half time bank.")
    if max_decision_seconds > ACTION_TIMEOUT_SECONDS:
        warnings.append("A direct decision exceeds the official per-request limit.")
    return {
        "seat": seat,
        "net_chips": sum(nets),
        "nets": nets,
        "decisions": sum(actions.values()),
        "actions": dict(actions),
        "hand_callbacks": callbacks,
        "new_half_seconds": init_seconds,
        "choose_action_seconds": choose_seconds,
        "on_hand_end_seconds": callback_seconds,
        "direct_compute_seconds": direct_seconds,
        "max_decision_ms": max_decision_seconds * 1000,
        "mean_decision_ms": choose_seconds * 1000 / max(1, sum(actions.values())),
        "half_wall_seconds": time.perf_counter() - total_start + init_seconds,
        "official_time_bank_seconds": config.time_bank_seconds,
        "warnings": warnings,
    }


def run_match(opponent: str, deals: int = 1000, seed: str = "dev-a", strategy: Any = None) -> dict[str, Any]:
    """Benchmark a complete duplicate match; raises immediately on bot errors."""
    if opponent not in OPPONENTS:
        raise ValueError(f"unknown opponent: {opponent}")
    if deals < 1:
        raise ValueError("deals must be positive")
    if strategy is None:
        strategy = importlib.import_module("strategy")
    warmup()  # Initialization must never be attributed to an in-game decision.
    halves = [play_half(strategy, opponent, deals, str(seed), seat) for seat in (0, 1)]
    return {
        "opponent": opponent,
        "seed": str(seed),
        "deals": deals,
        "hands": 2 * deals,
        "errors": 0,
        **paired_summary(halves[0]["nets"], halves[1]["nets"]),
        "halves": halves,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--deals", type=int, default=1000, help="duplicate deals per match")
    parser.add_argument("--seed", nargs="+", default=["dev-a"], help="one or more reproducible deal seeds")
    parser.add_argument("--opponent", choices=("all", *OPPONENTS), default="all")
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    if args.deals < 1:
        parser.error("--deals must be at least 1")
    opponents = OPPONENTS if args.opponent == "all" else (args.opponent,)
    reports = []
    print("Direct simulation: excludes HTTP overhead; no time-bank enforcement.", flush=True)
    for seed in args.seed:
        for opponent in opponents:
            result = run_match(opponent, args.deals, seed)
            reports.append(result)
            low, high = result["ci95_bb"]
            timing = "/".join(f"{half['direct_compute_seconds']:.3f}s" for half in result["halves"])
            print(
                f"seed={seed} vs {opponent:7s}: {result['verdict']:4s} "
                f"{result['mean_bb_per_paired_deal']:+.3f} bb/paired deal "
                f"CI=[{low:+.3f}, {high:+.3f}] compute={timing}",
                flush=True,
            )
            for half in result["halves"]:
                for warning in half["warnings"]:
                    print(f"  WARNING seat {half['seat']}: {warning}", flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "benchmark": "official-game-direct-simulation-v1",
            "timing_note": "Direct computation excludes HTTP and serialization. Bank not enforced. Verify with judge_engine.py.",
            "results": reports,
        }
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {args.output.resolve()}")


if __name__ == "__main__":
    main()
