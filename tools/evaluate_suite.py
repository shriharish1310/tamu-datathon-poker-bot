"""Sequential evaluation matrix, aggregating only official judge JSON metrics.

Each match delegates scoring to judge_engine.py via run_local_match.py, with new
server processes in BOTH halves. Full action logs and source snapshots are kept.
No strategy is selected or tuned by this tool. Choose a new output directory for
each run; partial or stale results are never silently reused.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_local_match import validate_diagnostics

OPPONENTS = ("random", "calling", "half", "pot")
SOURCE_FILES = (
    "agent.py", "strategy.py", "reliability.py", "equity.py", "evaluator.py", "game.py",
    "advanced_policy.py", "baseline_strategy.py", "range_equity.py", "policy_config.py",
    "judge_engine.py", "requirements.txt", "tools/run_local_match.py",
    "tools/evaluate_suite.py", "baseline-bots/baseline_random.py",
    "baseline-bots/baseline_calling_station.py", "baseline-bots/baseline_always_half.py",
    "baseline-bots/baseline_always_pot.py",
)


def fingerprints() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def read_reliability(path: Path, seed: str, deals: int) -> dict:
    """Require both post-half counters and independently scanned process logs."""
    sidecar = path.with_suffix(".reliability.json")
    evidence = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or evidence.get("schema") != "bot-reliability-v1":
        raise ValueError(f"Wrong reliability schema: {sidecar}")
    if (evidence.get("status") != "complete" or str(evidence.get("match_seed")) != seed
            or type(evidence.get("num_deals")) is not int or evidence["num_deals"] != deals):
        raise ValueError(f"Incomplete or mismatched reliability evidence: {sidecar}")
    halves = evidence.get("halves")
    if not isinstance(halves, list) or len(halves) != 2:
        raise ValueError(f"Expected reliability evidence for two halves: {sidecar}")
    clean = True
    for expected, half in enumerate(halves, 1):
        if not isinstance(half, dict) or half.get("half") != expected or half.get("evidence_error"):
            raise ValueError(f"Wrong reliability half metadata: {sidecar}")
        diagnostics = validate_diagnostics(half.get("diagnostics"))
        if type(half.get("log_fault_events")) is not int or half["log_fault_events"] < 0:
            raise ValueError(f"Missing or invalid log fault count: {sidecar}")
        clean = clean and not (
            diagnostics["fault_events"] or diagnostics["fallback_decisions"]
            or diagnostics["disabled"] or half["log_fault_events"]
        )
    return {
        "halves": halves,
        "reliability_clean": bool(clean),
        "fault_events": sum(h["diagnostics"]["fault_events"] for h in halves),
        "fallback_decisions": sum(h["diagnostics"]["fallback_decisions"] for h in halves),
        "log_fault_events": sum(h["log_fault_events"] for h in halves),
    }


def read_official(path: Path, seed: str, deals: int, opponent: str, target: float) -> dict:
    """Validate complete official reports; never recompute the official verdict."""
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["kind"] != "match_result" or str(report["match_seed"]) != seed:
        raise ValueError(f"Wrong report kind or seed: {path}")
    if report["num_deals"] != deals or len(report["paired_bb"]) != deals:
        raise ValueError(f"Incomplete match: {path}")
    for half in (1, 2):
        half_path = path.with_suffix(f".half{half}.json")
        part = json.loads(half_path.read_text(encoding="utf-8"))
        if (part["half"] != half or str(part["match_seed"]) != seed
                or part["num_deals"] != deals or len(part["nets_agent1"]) != deals
                or part["agent1_seat"] != half - 1):
            raise ValueError(f"Wrong half metadata: {half_path}")
    # --logs must survive the official combine command for post-match diagnostics.
    if any(len(report["logs"][f"half{half}"]) != deals for half in (1, 2)):
        raise ValueError(f"Missing hand logs: {path}")
    ours, theirs = report["agent_stats"]["agent1"], report["agent_stats"]["agent2"]
    if len(ours) != 2 or len(theirs) != 2:
        raise ValueError(f"Expected two sets of agent statistics: {path}")
    clean = lambda halves: all(
        half["errors"] == 0 and not half["timed_out"] and not half["forfeited"]
        for half in halves
    )
    reliability = read_reliability(path, seed, deals)
    return {
        "opponent": opponent, "seed": seed, "num_deals": deals,
        "report": str(path.relative_to(path.parents[1])).replace("\\", "/"),
        "verdict": report["verdict"], "points": report["points"]["agent1"],
        "mean_bb_per_deal": report["mean_bb_per_deal"], "ci": report["ci"],
        "agent_stats": report["agent_stats"],
        "max_time_seconds": max(half["time_seconds"] for half in ours),
        "bot_valid": clean(ours), "opponent_valid": clean(theirs),
        "runtime_target_met": all(half["time_seconds"] < target for half in ours),
        "reliability_clean": reliability["reliability_clean"],
        "fault_events": reliability["fault_events"],
        "fallback_decisions": reliability["fallback_decisions"],
        "log_fault_events": reliability["log_fault_events"],
        "reliability_halves": reliability["halves"],
    }


def summarize(rows: list[dict], target: float) -> dict:
    """Aggregate official metrics, retaining per-match CIs instead of pooling them."""
    groups = []
    for opponent in dict.fromkeys(row["opponent"] for row in rows):
        selected = [row for row in rows if row["opponent"] == opponent]
        groups.append({
            "opponent": opponent, "matches": len(selected),
            "total_points": sum(row["points"] for row in selected),
            "average_points": statistics.mean(row["points"] for row in selected),
            "average_bb_per_deal": statistics.mean(row["mean_bb_per_deal"] for row in selected),
            "worst_match_bb_per_deal": min(row["mean_bb_per_deal"] for row in selected),
            "min_official_ci_lower": min(row["ci"][0] for row in selected),
            "max_time_seconds": max(row["max_time_seconds"] for row in selected),
            "bot_valid": all(row["bot_valid"] for row in selected),
            "opponents_valid": all(row["opponent_valid"] for row in selected),
            "runtime_target_met": all(row["runtime_target_met"] for row in selected),
            "reliability_clean": all(row["reliability_clean"] for row in selected),
            "fault_events": sum(row["fault_events"] for row in selected),
            "fallback_decisions": sum(row["fallback_decisions"] for row in selected),
            "log_fault_events": sum(row["log_fault_events"] for row in selected),
        })
    return {
        "matches_completed": len(rows),
        "hands_played": sum(2 * row["num_deals"] for row in rows),
        "total_points": sum(row["points"] for row in rows),
        "average_points": statistics.mean(row["points"] for row in rows) if rows else None,
        "runtime_target_seconds": target,
        "per_opponent": groups,
        "bot_valid": all(row["bot_valid"] for row in rows),
        "opponents_valid": all(row["opponent_valid"] for row in rows),
        "runtime_target_met": all(row["runtime_target_met"] for row in rows),
        "reliability_clean": bool(rows) and all(row["reliability_clean"] for row in rows),
        "fault_events": sum(row["fault_events"] for row in rows),
        "fallback_decisions": sum(row["fallback_decisions"] for row in rows),
        "log_fault_events": sum(row["log_fault_events"] for row in rows),
        "release_gates_passed": bool(rows) and all(
            row["bot_valid"] and row["opponent_valid"] and row["runtime_target_met"]
            and row["reliability_clean"] for row in rows
        ),
        "positive_average_each_opponent": bool(groups) and all(g["average_bb_per_deal"] > 0 for g in groups),
        "note": "CIs and verdicts are official per-match results. No pooled CI or new scoring formula is computed.",
    }


def write_report(folder: Path, payload: dict) -> None:
    summary = payload["summary"]
    summary["release_gates_passed"] = (
        payload["status"] == "complete"
        and summary["matches_completed"] == payload["expected_matches"]
        and summary["release_gates_passed"]
    )
    (folder / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = ["# Official baseline evaluation", "", f"Status: **{payload['status']}**.", "",
             f"Completed {summary['matches_completed']}/{payload['expected_matches']} matches; "
             f"{summary['hands_played']:,} hands; {summary['total_points']:g} total match points.", "",
             "| Opponent | Points | Mean BB/deal | Worst BB/deal | Lowest match CI bound | Max charged seconds | Faults / fallbacks |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for row in summary["per_opponent"]:
        lines.append(f"| {row['opponent']} | {row['total_points']:g}/{row['matches']} | "
                     f"{row['average_bb_per_deal']:+.3f} | {row['worst_match_bb_per_deal']:+.3f} | "
                     f"{row['min_official_ci_lower']:+.3f} | {row['max_time_seconds']:.3f} | "
                     f"{row['fault_events']} / {row['fallback_decisions']} |")
    lines += ["", "These are the official judge's metrics. The CI column is the minimum lower",
              "bound among individual matches, not a confidence interval on the pooled mean.", "",
              f"Bot validity: {summary['bot_valid']}; opponent validity: {summary['opponents_valid']}; "
              f"every bot half < {summary['runtime_target_seconds']:g}s: {summary['runtime_target_met']}.",
              f"Strategy reliability clean: {summary['reliability_clean']}; "
              f"independent stderr fault markers: {summary['log_fault_events']}.",
              f"Local runtime/validity/reliability gates passed: {summary['release_gates_passed']}.",
              "", "Fresh bot processes were used for both halves. All matches ran sequentially.",
              "HTTP timing is measured on this host, outside the restricted tournament container.",
              "The policy adapts sample count to measured runtime, so fixed deals do not guarantee",
              "identical decisions on differently loaded machines.", "",
              "Raw official JSON, per-hand logs and server logs are under `matches/`.",
              "Reliability sidecars preserve post-half counters and stderr fault-marker counts;",
              "any fallback or missing evidence fails the local release gate even if the judge awarded a win.",
              "The exact evaluated source snapshot is under `source/`; hashes are in `manifest.json`.",
              "", "This establishes baseline performance only. No candidate upgrade is selected",
              "and no claim is made about competitive opponents or unused holdout seeds."]
    (folder / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", default=["7", "19", "43", "101", "202"])
    parser.add_argument("--opponents", nargs="+", choices=OPPONENTS, default=list(OPPONENTS))
    parser.add_argument("--deals", type=int, default=1000)
    parser.add_argument("--runtime-target", type=float, default=4.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.deals < 1 or args.runtime_target <= 0:
        parser.error("deals and runtime target must be positive")
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.opponents)) != len(args.opponents):
        parser.error("seeds and opponents must be unique")
    # Seeds enter file names as well as judge arguments; keep them portable.
    if any(not seed or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in seed)
           for seed in args.seeds):
        parser.error("seeds must use letters, digits, hyphens or underscores")
    folder = args.output.resolve()
    if folder.exists() and any(folder.iterdir()):
        parser.error("output directory is not empty; use a new directory to avoid stale results")
    (folder / "matches").mkdir(parents=True, exist_ok=True)
    initial_hashes = fingerprints()
    manifest = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "interpreter": sys.executable,
        "packages": {name: version(name) for name in ("fastapi", "uvicorn", "starlette", "httpx")},
        "seeds": args.seeds, "opponents": args.opponents, "deals": args.deals,
        "runtime_target_seconds": args.runtime_target,
        "source_sha256": initial_hashes, "fresh_processes_per_half": True,
        "sequential_matches": True, "official_hand_logs": True,
        "strategy_reliability_evidence_required": True,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name in SOURCE_FILES:
        destination = folder / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    rows = []
    payload = {"status": "running", "expected_matches": len(args.seeds) * len(args.opponents),
               "manifest": "manifest.json", "matches": rows, "summary": summarize(rows, args.runtime_target)}
    environment = {**os.environ, "PYTHONUTF8": "1"}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        for opponent in args.opponents:
            for seed in args.seeds:
                if fingerprints() != initial_hashes:
                    raise RuntimeError("Evaluated source changed during the suite; results must not be mixed.")
                output = folder / "matches" / f"{opponent}_seed{seed}.json"
                print(f"[{len(rows)+1}/{payload['expected_matches']}] {opponent} seed={seed}", flush=True)
                with output.with_suffix(".runner.log").open("w", encoding="utf-8") as log:
                    subprocess.run(
                        [sys.executable, "tools/run_local_match.py", "--opponent", opponent,
                         "--deals", str(args.deals), "--seed", seed, "--output", str(output), "--logs"],
                        cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                        check=True, creationflags=flags,
                    )
                if fingerprints() != initial_hashes:
                    raise RuntimeError("Evaluated source changed while playing a match.")
                row = read_official(output, seed, args.deals, opponent, args.runtime_target)
                rows.append(row)
                payload["summary"] = summarize(rows, args.runtime_target)
                write_report(folder, payload)
                print(f"  {row['verdict']}: points={row['points']:g} BB/deal={row['mean_bb_per_deal']:+.3f} "
                      f"CI={row['ci']} max_time={row['max_time_seconds']:.3f}s "
                      f"valid={row['bot_valid'] and row['opponent_valid']} "
                      f"faults={row['fault_events']} fallbacks={row['fallback_decisions']} "
                      f"reliability_clean={row['reliability_clean']}", flush=True)
        payload["status"] = "complete"
    except Exception as exc:
        payload["status"] = "failed"
        payload["failure"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        payload["summary"] = summarize(rows, args.runtime_target)
        write_report(folder, payload)
    print(f"Finished: {payload['summary']['total_points']:g}/{len(rows)} points. {folder / 'SUMMARY.md'}", flush=True)
    if not payload["summary"]["release_gates_passed"]:
        print("RELEASE GATE FAILED: inspect validity, timing, and reliability evidence.", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
