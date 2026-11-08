"""Build docs/BATCH04_VERIFY.json from local verification outputs (no matches are run).

Inputs (all gitignored under reports/):
  batch04-downloaded/           extracted batch04-bench artifact
  batch04-verify.json           output of tools/verify_batch04_artifact.py --json
  archive/batch04-bench-*.zip   raw artifact zip as served by GitHub
  archive/Starfish-6e5b590.zip  allowlisted submission ZIP
  desktop-match-6e5b590/        output of tools/desktop_check.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
GITHUB_DIGEST = "0e15d8f9e66725bb0582a456d32ca4855284ebeb15239d5df55119c0e30ed1fa"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verify = json.loads((REPORTS / "batch04-verify.json").read_text())
    raw_zip = next((REPORTS / "archive").glob("batch04-bench-run*.zip"))
    sub_zip = REPORTS / "archive" / "Starfish-6e5b590.zip"
    extracted = REPORTS / "batch04-downloaded"
    desk = REPORTS / "desktop-match-6e5b590"
    match = json.loads((desk / "match.json").read_text())
    rel = json.loads((desk / "match.reliability.json").read_text())
    plan = json.loads((desk / "plan.json").read_text())
    integrity = json.loads((desk / "integrity.json").read_text())

    out = {
        "schema": "starfish-batch04-handoff-verify-v1",
        "artifact": {
            "run": 42434610957, "artifact_id": 13599023177, "name": "batch04-bench",
            "expires_utc": "2026-12-08T01:41:10Z",
            "github_digest": GITHUB_DIGEST, "raw_zip_sha256": sha(raw_zip),
            "raw_zip_matches_github_digest": sha(raw_zip) == GITHUB_DIGEST,
            "raw_zip_bytes": raw_zip.stat().st_size,
            "file_sha256": {p.relative_to(extracted).as_posix(): sha(p)
                            for p in sorted(extracted.rglob("*")) if p.is_file()},
        },
        "independent_recomputation": {k: verify[k] for k in ("checks", "summary", "source_vs_git", "images")},
        "matches": [{k: m[k] for k in ("index", "profile", "opponent", "seed", "mean_bb", "ci95",
                                       "points_recomputed", "bot_half_seconds", "judge_counts", "reliability")}
                    for m in verify["matches"]],
        "submission_zip": {"name": sub_zip.name, "bytes": sub_zip.stat().st_size, "sha256": sha(sub_zip),
                           "commit": "6e5b590bc922f047de670efdd5fd599f7459a75d"},
        "desktop_check": {
            "plan": {k: plan[k] for k in ("locked_utc", "purpose", "candidate_commit", "desktop_sha256",
                                          "seed", "deals", "matches", "python", "notes")},
            "agent1": match["agent1_name"].split(" (")[0], "agent2": match["agent2_name"].split(" (")[0],
            "verdict": match["verdict"], "points": match["points"], "mean_bb_per_paired_deal": match["mean_bb_per_deal"],
            "official_ci95": match["ci"], "stderr_bb": match["stderr_bb"], "half_totals_chips": match["half_totals_chips"],
            "agent_stats": match["agent_stats"],
            "candidate_reliability": [{"half": h["half"], **h["diagnostics"], "log_fault_events": h["log_fault_events"]}
                                      for h in rel["halves"]],
            "opponent_fault_observability": "Desktop strategy catches decision exceptions and returns check/fold; "
                                            "judge errors cannot detect those, and it exposes no diagnostics counters",
            "integrity": {k: v for k, v in integrity.items() if k != "candidate_runtime_sha256"},
            "evidence_sha256": {p.name: sha(p) for p in sorted(desk.glob("match*")) if p.is_file()},
        },
    }
    (ROOT / "docs" / "BATCH04_VERIFY.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("wrote docs/BATCH04_VERIFY.json;", len(out["artifact"]["file_sha256"]), "artifact files hashed")


if __name__ == "__main__":
    main()
