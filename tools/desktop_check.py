"""One fresh-process full match: frozen candidate worktree vs a frozen Desktop bot snapshot.

Writes plan.json before the match, runs the candidate's unmodified tools/run_local_match.py,
then re-verifies every source hash. Never writes into the Desktop project.

Usage:
  python tools/desktop_check.py --candidate C:/.../starfish-rc-6e5b590 --python C:/.../.venv-rc/Scripts/python.exe
      --desktop C:/Users/shrih/Desktop/heads-up-bundle --seed <seed> --out reports/desktop-match-6e5b590
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

DESKTOP_FILES = ("agent.py", "strategy.py", "game.py", "evaluator.py", "requirements.txt")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def candidate_state(repo: Path) -> dict:
    files = git(repo, "ls-files").splitlines()
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "status_porcelain": git(repo, "status", "--porcelain", "--untracked-files=no"),
        "tracked_sha256": {f: sha(repo / f) for f in files},
    }


def desktop_state(root: Path) -> dict:
    return {f: sha(root / f) for f in DESKTOP_FILES}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--desktop", type=Path, required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--deals", type=int, default=1000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists():
        raise SystemExit(f"{out} exists; never overwrite a started match")
    out.mkdir(parents=True)
    snapshot = out / "opponent-snapshot"
    snapshot.mkdir()
    for f in DESKTOP_FILES:
        shutil.copy2(a.desktop / f, snapshot / f)
        os.chmod(snapshot / f, stat.S_IREAD)

    cand_before = candidate_state(a.candidate)
    if cand_before["status_porcelain"]:
        raise SystemExit("candidate worktree has tracked modifications")
    desk_before = desktop_state(a.desktop)
    snap_before = desktop_state(snapshot)
    if desk_before != snap_before:
        raise SystemExit("snapshot does not match Desktop sources")
    freeze = subprocess.check_output([str(a.python), "-m", "pip", "freeze"], text=True).split()
    version = subprocess.check_output([str(a.python), "-c", "import sys,platform;print(sys.version);print(platform.platform())"], text=True).splitlines()
    match_out = out / "match.json"
    command = [str(a.python), "tools/run_local_match.py", "--agent-dir", str(a.candidate),
               "--opponent-dir", str(snapshot), "--deals", str(a.deals), "--seed", a.seed,
               "--output", str(match_out), "--logs"]
    plan = {
        "schema": "starfish-desktop-check-v1",
        "locked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "Single fresh-process local compatibility/strength check; not a release gate, not a holdout",
        "candidate_commit": cand_before["head"], "desktop_source": str(a.desktop),
        "desktop_sha256": desk_before, "seed": a.seed, "deals": a.deals, "matches": 1,
        "command": command, "cwd": str(a.candidate), "python": version, "pip_freeze": freeze,
        "notes": [
            "Both servers launched by run_local_match.py with the candidate venv interpreter",
            "Opponent runs from a read-only snapshot copy; Desktop project is never written",
            "Host HTTP on Windows, not the official Linux container; timings are not official",
        ],
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    proc = subprocess.run(command, cwd=a.candidate, capture_output=True, text=True)
    (out / "run.stdout.log").write_text(proc.stdout, encoding="utf-8")
    (out / "run.stderr.log").write_text(proc.stderr, encoding="utf-8")

    cand_after = candidate_state(a.candidate)
    post = {
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "run_returncode": proc.returncode,
        "candidate_head_unchanged": cand_after["head"] == cand_before["head"],
        "candidate_clean_after": cand_after["status_porcelain"] == "",
        "candidate_tracked_unchanged": cand_after["tracked_sha256"] == cand_before["tracked_sha256"],
        "desktop_unchanged": desktop_state(a.desktop) == desk_before,
        "snapshot_unchanged": desktop_state(snapshot) == snap_before,
        "candidate_tracked_files": len(cand_before["tracked_sha256"]),
        "candidate_runtime_sha256": {k: v for k, v in cand_before["tracked_sha256"].items() if "/" not in k and k.endswith((".py", ".txt"))},
    }
    (out / "integrity.json").write_text(json.dumps(post, indent=2) + "\n", encoding="utf-8")
    print(proc.stdout)
    print(proc.stderr[-4000:], file=sys.stderr)
    print(json.dumps({k: v for k, v in post.items() if k != "candidate_runtime_sha256"}, indent=2))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
