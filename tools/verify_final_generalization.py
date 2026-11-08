"""Independently evaluate FINAL_GENERALIZATION_LOCK.json gates from raw judge output.

Does not import tools/report_final_generalization.py. Recomputes each match from paired_bb,
then applies the locked weighting (1/12 per configuration, 1/3 per seed) and gates.

Usage: python tools/verify_final_generalization.py reports/final-generalization-downloaded LOCK.json [--json out]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

T_975_DF2 = 4.302652729911275
Z = 1.96


def tci(values: list[float]) -> tuple[float, float, float]:
    m = statistics.fmean(values)
    h = T_975_DF2 * statistics.stdev(values) / math.sqrt(len(values))
    return m, m - h, m + h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact", type=Path)
    ap.add_argument("lock", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    root, lock = a.artifact, json.loads(a.lock.read_text())
    acc = lock["acceptance"]
    ledger = json.loads((root / "match-ledger.json").read_text())
    bench = json.loads((root / "benchmark.json").read_text())
    by_index = {m["match_index"]: m for m in bench["matches"]}

    rows = []
    for e in ledger:
        rpt = root / by_index[e["index"]]["report"]
        m = json.loads(rpt.read_text())
        rel = json.loads(rpt.with_suffix(".reliability.json").read_text())
        p = m["paired_bb"]
        mean = statistics.fmean(p)
        half = Z * statistics.stdev(p) / math.sqrt(len(p))
        lo, hi = mean - half, mean + half
        pts = 1.0 if lo > 0 else 0.0 if hi < 0 else 0.5
        st = m["agent_stats"]
        judge_bad = {side: sum(int(h[k]) for h in st[side] for k in ("errors", "skipped_calls", "timed_out", "forfeited"))
                     for side in ("agent1", "agent2")}
        exhausted = any(h["time_seconds"] >= acc["official_time_bank_seconds"] for side in st for h in st[side])
        rel_bad = sum(hv["diagnostics"]["fault_events"] + hv["diagnostics"]["fallback_decisions"]
                      + hv["opponent_diagnostics"]["fault_events"] + hv["opponent_diagnostics"]["fallback_decisions"]
                      + hv["log_fault_events"] + hv["opponent_log_fault_events"]
                      + int(hv["diagnostics"]["disabled"]) + int(hv["opponent_diagnostics"]["disabled"])
                      for hv in rel["halves"])
        rows.append({
            "index": e["index"], "opponent": e["opponent"], "seed": e["seed"], "status": e["status"],
            "deals": len(p), "mean_bb": mean, "ci95": [lo, hi], "points": pts,
            "matches_report": abs(mean - m["mean_bb_per_deal"]) < 1e-9 and pts == m["points"]["agent1"]
            and abs(lo - m["ci"][0]) < 1e-9,
            "bot_half_seconds": [h["time_seconds"] for h in st["agent1"]],
            "opp_half_seconds": [h["time_seconds"] for h in st["agent2"]],
            "judge_bad": judge_bad, "bank_exhausted": exhausted, "reliability_bad": rel_bad,
            "agent1": m["agent1_name"].split(" (")[0], "agent2": m["agent2_name"].split(" (")[0],
        })

    seeds = lock["seeds"]
    cfg = defaultdict(dict)
    for r in rows:
        cfg[r["opponent"]][r["seed"]] = r
    per_cfg = {}
    for name, d in sorted(cfg.items()):
        bbs = [d[s]["mean_bb"] for s in seeds]
        m, lo, hi = tci(bbs)
        per_cfg[name] = {"points": sum(d[s]["points"] for s in seeds), "mean_bb": m, "min_bb": min(bbs),
                         "max_bb": max(bbs), "t95_df2": [lo, hi],
                         "official_cis": {s: [round(x, 4) for x in d[s]["ci95"]] for s in seeds}}
    eq_points = statistics.fmean(v["points"] / len(seeds) for v in per_cfg.values())
    round_means = [statistics.fmean(cfg[c][s]["mean_bb"] for c in cfg) for s in seeds]
    agg_m, agg_lo, agg_hi = tci(round_means)
    max_half = max(t for r in rows for t in r["bot_half_seconds"])
    gates = {
        "complete_match_slots": (sum(r["status"] == "complete" for r in rows), sum(r["status"] == "complete" for r in rows) == acc["complete_match_slots"]),
        "equally_weighted_points": (eq_points, eq_points >= acc["minimum_equally_weighted_points"]),
        "min_points_per_configuration": (min(v["points"] for v in per_cfg.values()), min(v["points"] for v in per_cfg.values()) >= acc["minimum_points_per_configuration"]),
        "positive_mean_bb_every_configuration": (min(v["mean_bb"] for v in per_cfg.values()), all(v["mean_bb"] > 0 for v in per_cfg.values())),
        "aggregate_profit_seed_t_ci95": ([agg_m, agg_lo, agg_hi], agg_lo > 0),
        "candidate_max_charged_half": (max_half, max_half < acc["candidate_max_charged_half_strictly_below_seconds"]),
        "zero_faults_errors_forfeits_exhaustion": (
            sum(r["judge_bad"]["agent1"] + r["judge_bad"]["agent2"] + r["reliability_bad"] + int(r["bank_exhausted"]) for r in rows),
            all(r["judge_bad"]["agent1"] == 0 and r["judge_bad"]["agent2"] == 0 and r["reliability_bad"] == 0 and not r["bank_exhausted"] for r in rows)),
        "raw_recomputation_matches_reports": (sum(r["matches_report"] for r in rows), all(r["matches_report"] for r in rows)),
        "all_1000_deals": (None, all(r["deals"] == lock["paired_deals_per_match"] for r in rows)),
        "seed_round_means": (round_means, None),
    }
    out = {"candidate_commit": bench["candidate_commit"], "candidate_image": bench["candidate_image"],
           "gates": gates, "all_pass": all(v[1] for k, v in gates.items() if v[1] is not None),
           "per_configuration": per_cfg, "matches": rows}
    if a.json:
        a.json.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gates": gates, "all_pass": out["all_pass"]}, indent=1, default=lambda x: round(x, 6)))
    print(f"{'configuration':22s} pts   meanBB    min      max      t95(df2)")
    for k, v in per_cfg.items():
        print(f"{k:22s} {v['points']:.1f}  {v['mean_bb']:+.4f}  {v['min_bb']:+.4f}  {v['max_bb']:+.4f}  [{v['t95_df2'][0]:+.3f}, {v['t95_df2'][1]:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
