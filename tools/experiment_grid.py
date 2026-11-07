"""Sequential policy experiments, using official games and official scoring.

Direct screening does NOT enforce HTTP/time banks. Validate finalists through
run_local_match.py with fresh server processes. No test seed enters a policy.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from advanced_policy import Policy, build_policy
import baseline_strategy
from evaluator import warmup
from game import Action, AgentConfig, Game, button_for_deal, make_deal
from policy_config import PolicyConfig, PROFILES
from tools.benchmark_strategy import baseline_action, paired_summary

SOURCES = ("advanced_policy.py", "baseline_strategy.py", "range_equity.py", "policy_config.py",
           "equity.py", "evaluator.py", "game.py", "judge_engine.py", "tools/experiment_grid.py")


class Baseline:
    def __init__(self, name):
        self.name = name
    def new_half(self, config, memory):
        memory["rng"] = random.Random(0)
    def choose_action(self, obs, memory):
        return baseline_action(obs, self.name, memory["rng"])
    def on_hand_end(self, result, memory):
        pass


def import_desktop(path):
    source = path / "strategy.py"
    for name in ("game.py", "evaluator.py"):
        if (path / name).read_bytes().replace(b"\r\n", b"\n") != (ROOT / name).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError("Opponent rules differ: " + name)
    spec = importlib.util.spec_from_file_location("frozen_desktop_strategy", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def half(candidate, opponent, deals, seat):
    agents = (candidate, opponent)
    memories, pending = ({}, {}), ([], [])
    compute, max_action, decisions = [0.0, 0.0], [0.0, 0.0], [0, 0]
    config = AgentConfig(num_hands=len(deals))
    for agent, memory in zip(agents, memories):
        agent.new_half(config, memory)
    nets = []
    def deliver(index):
        start = perf_counter()
        for result in pending[index]:
            agents[index].on_hand_end(result, memories[index])
        pending[index].clear()
        compute[index] += perf_counter() - start
    for index, deal in enumerate(deals):
        game = Game(deal, button_for_deal(index), index)
        while not game.is_terminal:
            player = 0 if game.to_act == seat else 1
            deliver(player)
            observation = game.observation(game.to_act)
            started = perf_counter()
            action = agents[player].choose_action(observation, memories[player])
            elapsed = perf_counter() - started
            compute[player] += elapsed
            max_action[player] = max(max_action[player], elapsed)
            decisions[player] += 1
            if not isinstance(action, Action) or action not in observation.legal_actions:
                raise ValueError(f"Illegal action by player {player}: {action!r}")
            game.apply(action)
        for player in (0, 1):
            pending[player].append(game.hand_result(seat if player == 0 else 1 - seat))
        nets.append(game.hand_result(seat).my_net)
    for player in (0, 1):
        deliver(player)
    return {"nets": nets, "compute_seconds": compute, "max_action_seconds": max_action,
            "decisions": decisions, "diagnostics": dict(memories[0].get("experiment", {}))}


def match(candidate, opponent, deals):
    halves = [half(candidate, opponent, deals, seat) for seat in (0, 1)]
    score = paired_summary(halves[0]["nets"], halves[1]["nets"])
    return {**score, "halves": halves}


def aggregates(rows):
    summary = []
    for name in dict.fromkeys(r["profile"] for r in rows):
        group = [r for r in rows if r["profile"] == name]
        opponents = {}
        for opponent in dict.fromkeys(r["opponent"] for r in group):
            subset = [r for r in group if r["opponent"] == opponent]
            opponents[opponent] = {"points": sum(r["points"] for r in subset), "matches": len(subset),
                                  "bb_per_deal": sum(r["mean_bb_per_paired_deal"] for r in subset) / len(subset)}
        summary.append({"profile": name, "points": sum(r["points"] for r in group),
                        "matches": len(group), "by_opponent": opponents,
                        "max_compute_half": max(h["compute_seconds"][0] for r in group for h in r["halves"]),
                        "max_action_ms": 1000 * max(h["max_action_seconds"][0] for r in group for h in r["halves"])})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="+", default=list(PROFILES))
    parser.add_argument("--configs", type=Path)
    parser.add_argument("--opponents", nargs="+", default=["desktop", "frozen", "pot"])
    parser.add_argument("--desktop-dir", type=Path)
    parser.add_argument("--seeds", nargs="+", required=True)
    parser.add_argument("--deals", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.configs:
        for raw in json.loads(args.configs.read_text(encoding="utf-8")):
            raw["samples"] = tuple(raw.get("samples", (24, 32, 40, 64)))
            settings = PolicyConfig(**raw)
            PROFILES[settings.name] = settings
    for name in args.profiles:
        if name not in PROFILES:
            parser.error("Unknown profile: " + name)
    if "desktop" in args.opponents and not args.desktop_dir:
        parser.error("--desktop-dir is required for the desktop opponent")
    opponents = {name: Baseline(name) for name in ("random", "calling", "half", "pot")}
    opponents["frozen"] = baseline_strategy
    if args.desktop_dir:
        opponents["desktop"] = import_desktop(args.desktop_dir)
    if any(name not in opponents for name in args.opponents) or args.deals < 1:
        parser.error("Invalid opponents or deals")
    if args.output.exists():
        parser.error("Use a new output folder")
    args.output.mkdir(parents=True)
    (args.output / "matches").mkdir()
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}
    manifest = {"purpose": "Development screen; not official HTTP acceptance", "deals": args.deals,
                "seeds": args.seeds, "profiles": [PROFILES[n].to_dict() for n in args.profiles],
                "opponents": args.opponents, "source_sha256": hashes, "python": sys.version,
                "platform": platform.platform(), "sequential": True,
                "timing_note": "Direct compute only; HTTP and bank enforcement omitted."}
    if args.desktop_dir:
        manifest["desktop_sha256"] = hashlib.sha256((args.desktop_dir / "strategy.py").read_bytes()).hexdigest()
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    rows, status = [], "running"
    warmup()
    deals = {seed: [make_deal(seed, i) for i in range(args.deals)] for seed in args.seeds}
    total = len(args.seeds) * len(args.opponents) * len(args.profiles)
    try:
        for seed in args.seeds:
            for name in args.profiles:
                candidate = build_policy(name)
                for opponent in args.opponents:
                    if any(hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != h for n, h in hashes.items()):
                        raise RuntimeError("Experiment source changed during run")
                    result = match(candidate, opponents[opponent], deals[seed])
                    result.update(profile=name, opponent=opponent, seed=seed, deals=args.deals)
                    (args.output / "matches" / f"{name}_{opponent}_{seed}.json").write_text(
                        json.dumps(result) + "\n", encoding="utf-8")
                    row = {k: v for k, v in result.items() if k != "paired_bb"}
                    row["halves"] = [{k: v for k, v in h.items() if k != "nets"} for h in result["halves"]]
                    rows.append(row)
                    print(f"[{len(rows)}/{total}] {name:24s} vs {opponent:7s} "
                          f"{result['official_verdict']:10s} {result['mean_bb_per_paired_deal']:+.3f} "
                          f"CI={[round(v,3) for v in result['ci95_bb']]} "
                          f"compute={max(h['compute_seconds'][0] for h in result['halves']):.3f}s", flush=True)
                    (args.output / "summary.json").write_text(json.dumps(
                        {"status": status, "matches": rows, "summary": aggregates(rows)}, indent=2) + "\n", encoding="utf-8")
        status = "complete"
    finally:
        (args.output / "summary.json").write_text(json.dumps(
            {"status": status if len(rows) == total else "failed", "matches": rows,
             "summary": aggregates(rows)}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
