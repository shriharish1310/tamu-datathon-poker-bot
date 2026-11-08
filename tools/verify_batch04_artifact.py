"""Independently re-derive Batch 04 findings from the raw batch04-bench artifact.

Does not import tools/report_batch04.py. Recomputes verdicts, CIs, charged times,
error/forfeit counts and reliability counters from per-half official judge JSON,
and checks archived sources against git blobs at the recorded commits.

Usage: python tools/verify_batch04_artifact.py reports/batch04-downloaded [--json out.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

CANDIDATE = "6e5b590bc922f047de670efdd5fd599f7459a75d"
BASELINE = "fd5c428475eee98edb7c38bd1e7fc0870ddbf42d"
Z = 1.96


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(commit: str, rel: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"{commit}:{rel}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def compare_tree(root: Path, commit: str, skip_parts=("__pycache__",)) -> dict:
    same, differ, missing = [], [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(s in p.parts for s in skip_parts):
            continue
        rel = p.relative_to(root).as_posix()
        blob = git_blob(commit, rel)
        if blob is None:
            missing.append(rel)
        elif normalize(blob) == normalize(p.read_bytes()):
            same.append(rel)
        else:
            differ.append(rel)
    return {"commit": commit, "identical": len(same), "differ": differ, "not_in_commit": missing}


def match_stats(paired: list[float]) -> tuple[float, float, float]:
    n = len(paired)
    mean = sum(paired) / n
    sd = statistics.stdev(paired)
    half = Z * sd / math.sqrt(n)
    return mean, mean - half, mean + half


def verdict(lo: float, hi: float) -> float:
    if lo > 0:
        return 1.0
    if hi < 0:
        return 0.0
    return 0.5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    root: Path = a.artifact
    bench = json.loads((root / "benchmark.json").read_text())
    ledger = json.loads((root / "match-ledger.json").read_text())
    out: dict = {"artifact": str(root), "checks": {}, "matches": []}
    checks = out["checks"]

    checks["status_complete"] = bench["status"] == "complete"
    checks["candidate_commit"] = bench["candidate_commit"] == CANDIDATE
    checks["ledger_12_complete"] = len(ledger) == 12 and all(e["status"] == "complete" for e in ledger)
    for prof, commit in (("baseline", BASELINE), ("candidate", CANDIDATE)):
        img = json.loads((root / f"{prof}-image.json").read_text())
        checks[f"{prof}_image_commit"] = img["commit"] == commit
        checks[f"{prof}_image_matches_benchmark"] = img["image"] == bench["images"][prof]
    out["images"] = bench["images"]

    per_prof: dict[str, dict] = {}
    for entry, summary in zip(ledger, bench["matches"]):
        prof = entry["profile"]
        stem = f"{entry['index']:02d}_{prof}_{entry['opponent']}_{entry['seed']}"
        m = json.loads((root / "matches" / f"{stem}.json").read_text())
        rel = json.loads((root / "matches" / f"{stem}.reliability.json").read_text())
        halves = [json.loads((root / "matches" / f"{stem}.half{h}.json").read_text()) for h in (1, 2)]

        paired = m["paired_bb"]
        mean, lo, hi = match_stats(paired)
        pts = verdict(lo, hi)
        # judge_engine.combine: paired_bb[d] = (half1 net + half2 net) / BIG_BLIND, BIG_BLIND = 2 chips.
        h1, h2 = halves[0]["nets_agent1"], halves[1]["nets_agent1"]
        repaired = [(x + y) / 2 for x, y in zip(h1, h2)]
        bot_times = [h["agent_stats"]["agent1"]["time_seconds"] for h in halves]
        opp_times = [h["agent_stats"]["agent2"]["time_seconds"] for h in halves]
        errs = {
            side: {
                k: sum(int(h["agent_stats"][side][k]) for h in halves)
                for k in ("errors", "skipped_calls", "timed_out", "forfeited")
            }
            for side in ("agent1", "agent2")
        }
        counters = {"bot_fault_events": 0, "bot_fallbacks": 0, "opp_fault_events": 0,
                    "opp_fallbacks": 0, "log_fault_events": 0, "opp_log_fault_events": 0, "disabled": False}
        for hv in rel["halves"]:
            counters["bot_fault_events"] += hv["diagnostics"]["fault_events"]
            counters["bot_fallbacks"] += hv["diagnostics"]["fallback_decisions"]
            counters["opp_fault_events"] += hv["opponent_diagnostics"]["fault_events"]
            counters["opp_fallbacks"] += hv["opponent_diagnostics"]["fallback_decisions"]
            counters["log_fault_events"] += hv["log_fault_events"]
            counters["opp_log_fault_events"] += hv["opponent_log_fault_events"]
            counters["disabled"] |= hv["diagnostics"]["disabled"] or hv["opponent_diagnostics"]["disabled"]
        row = {
            "index": entry["index"], "profile": prof, "opponent": entry["opponent"], "seed": entry["seed"],
            "deals": len(paired), "mean_bb": round(mean, 6), "ci95": [round(lo, 4), round(hi, 4)],
            "points_recomputed": pts, "points_reported": m["points"]["agent1"],
            "mean_matches_report": abs(mean - m["mean_bb_per_deal"]) < 1e-9,
            "ci_matches_report": abs(lo - m["ci"][0]) < 1e-9 and abs(hi - m["ci"][1]) < 1e-9,
            "summary_matches_raw": abs(summary["mean_bb_per_deal"] - m["mean_bb_per_deal"]) < 1e-9
            and summary["max_time_seconds"] == max(bot_times) and summary["seed"] == entry["seed"],
            "pairing_reconstructed": max(abs(x - y) for x, y in zip(repaired, paired)) < 1e-9,
            "bot_half_seconds": bot_times, "opp_half_seconds": opp_times,
            "bot_calls": [h["agent_stats"]["agent1"]["calls"] for h in halves],
            "judge_counts": errs, "reliability": counters,
        }
        out["matches"].append(row)
        p = per_prof.setdefault(prof, {"points": 0.0, "matches": 0, "half_times": [], "bluffy_half_times": [],
                                       "bb": [], "errors": 0, "opp_errors": 0, "faults": 0, "fallbacks": 0})
        p["points"] += pts
        p["matches"] += 1
        p["half_times"] += bot_times
        if entry["opponent"] == "bluffy_1":
            p["bluffy_half_times"] += bot_times
        p["bb"].append(mean)
        p["errors"] += sum(errs["agent1"].values())
        p["opp_errors"] += sum(errs["agent2"].values())
        p["faults"] += counters["bot_fault_events"] + counters["opp_fault_events"] + counters["log_fault_events"] + counters["opp_log_fault_events"]
        p["fallbacks"] += counters["bot_fallbacks"] + counters["opp_fallbacks"]

    summary = {}
    for prof, p in per_prof.items():
        summary[prof] = {
            "points": f"{p['points']:g}/{p['matches']}",
            "mean_bb_per_match": round(sum(p["bb"]) / len(p["bb"]), 6),
            "worst_charged_half": max(p["half_times"]),
            "bluffy_median_half": statistics.median(p["bluffy_half_times"]),
            "halves_below_4s": sum(t < 4.0 for t in p["half_times"]),
            "halves_total": len(p["half_times"]),
            "judge_errors_timeouts_forfeits_bot": p["errors"],
            "judge_errors_timeouts_forfeits_opp": p["opp_errors"],
            "reliability_fault_events": p["faults"],
            "reliability_fallbacks": p["fallbacks"],
        }
    b, c = summary["baseline"]["bluffy_median_half"], summary["candidate"]["bluffy_median_half"]
    summary["bluffy_median_reduction_pct"] = round(100 * (b - c) / b, 2)
    out["summary"] = summary

    checks["all_points_recomputed_match_report"] = all(r["points_recomputed"] == r["points_reported"] for r in out["matches"])
    checks["all_means_cis_match_report"] = all(r["mean_matches_report"] and r["ci_matches_report"] for r in out["matches"])
    checks["benchmark_summary_matches_raw"] = all(r["summary_matches_raw"] for r in out["matches"])
    checks["paired_bb_reconstructed_from_halves"] = all(r["pairing_reconstructed"] for r in out["matches"])
    checks["all_1000_deals"] = all(r["deals"] == 1000 for r in out["matches"])

    eq = json.loads((root / "equivalence.json").read_text())
    checks["equivalence_passed"] = eq["passed"] and eq["protocol_passed"]
    checks["equivalence_modes_4021_each"] = {c_["mode"]: c_["decisions"] for c_ in eq["comparisons"]}
    for mode in ("full", "half", "boundary"):
        checks[f"equivalence_{mode}_raw_files_identical"] = sha256(root / f"baseline-equivalence-{mode}.json") == sha256(root / f"candidate-equivalence-{mode}.json")
    tests_log = (root / "candidate-tests.log").read_text()
    checks["tests_log_tail"] = [ln for ln in tests_log.splitlines() if "passed" in ln][-1]
    rel_c = json.loads((root / "candidate-container-reliability.json").read_text())
    checks["container_reliability_keys"] = sorted(rel_c)[:12]
    build_log = (root / "candidate-official-build.log").read_text().strip().splitlines()
    checks["official_build_log_tail"] = build_log[-3:]

    out["source_vs_git"] = {
        "candidate-source": compare_tree(root / "candidate-source", CANDIDATE),
        "packages/baseline": compare_tree(root / "packages" / "baseline", BASELINE),
    }
    text = json.dumps(out, indent=2, default=str)
    if a.json:
        a.json.write_text(text)
    print(json.dumps({"checks": checks, "summary": summary, "source_vs_git": out["source_vs_git"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
