"""Execute a locked list of fresh-process official HTTP comparison matches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.evaluate_suite import read_official, summarize


def fingerprint(folder):
    paths = sorted(folder.glob("*.py")) + [folder / "requirements.txt"]
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fail-fast", action="store_true", help="stop after any failed release gate")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    folder = args.output.resolve()
    if folder.exists():
        parser.error("Use a new output folder")
    (folder / "matches").mkdir(parents=True)
    folders = {str(Path(row[key]).resolve()) for row in plan for key in ("agent_dir", "opponent_dir") if key in row}
    hashes = {path: fingerprint(Path(path)) for path in folders}
    manifest = {"plan": plan, "sha256": hashes, "fresh_processes_each_half": True,
                "deals_per_match": 1000, "sequential": True,
                "official_scoring": True, "charged_runtime_target": 4.0}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    rows, status = [], "running"
    def save():
        groups = {name: summarize([r for r in rows if r["profile"] == name], 4.0)
                  for name in dict.fromkeys(r["profile"] for r in rows)}
        (folder / "summary.json").write_text(json.dumps({"status": status, "expected_matches": len(plan),
                   "matches": rows, "profiles": groups}, indent=2) + "\n", encoding="utf-8")
    try:
        for task in plan:
            for field in ("profile", "opponent", "seed"):
                if not re.fullmatch(r"[\w-]+", task[field], flags=re.ASCII):
                    raise ValueError("Invalid match label")
            if any(fingerprint(Path(path)) != expected for path, expected in hashes.items()):
                raise RuntimeError("Frozen bot source changed")
            output = folder / "matches" / f"{task['profile']}_{task['opponent']}_{task['seed']}.json"
            if output.exists():
                raise ValueError("Duplicate planned match")
            command = [sys.executable, "tools/run_local_match.py", "--agent-dir", task["agent_dir"],
                       "--deals", "1000", "--seed", task["seed"], "--output", str(output), "--logs"]
            if "opponent_dir" in task:
                command += ["--opponent-dir", task["opponent_dir"]]
            else:
                command += ["--opponent", task["opponent"]]
            print(f"[{len(rows)+1}/{len(plan)}] {task['profile']} vs {task['opponent']} {task['seed']}", flush=True)
            with output.with_suffix(".runner.log").open("w", encoding="utf-8") as log:
                subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"},
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=660,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if any(fingerprint(Path(path)) != expected for path, expected in hashes.items()):
                raise RuntimeError("Frozen bot source changed during match")
            row = read_official(output, task["seed"], 1000, task["opponent"], 4.0)
            row["profile"] = task["profile"]
            rows.append(row)
            save()
            print(f"  {row['verdict']} points={row['points']} BB/deal={row['mean_bb_per_deal']:+.4f} "
                  f"CI={[round(x,4) for x in row['ci']]} time={row['max_time_seconds']:.3f}s "
                  f"valid={row['bot_valid']}/{row['opponent_valid']} clean={row['reliability_clean']}", flush=True)
            if args.fail_fast and not (row["bot_valid"] and row["opponent_valid"]
                                      and row["runtime_target_met"] and row["reliability_clean"]):
                status = "stopped_release_gate"
                save()
                return 1
        status = "complete"
    except Exception:
        status = "failed"
        raise
    finally:
        save()
    if any(not (r["bot_valid"] and r["opponent_valid"] and r["runtime_target_met"] and r["reliability_clean"]) for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
