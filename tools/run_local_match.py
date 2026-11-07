"""Run the official HTTP judge, restarting both servers between duplicate halves."""

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OPPONENTS = {"calling": "baseline_calling_station", "random": "baseline_random",
             "half": "baseline_always_half", "pot": "baseline_always_pot"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(port: int, process: subprocess.Popen, deadline: float) -> None:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Server exited; inspect its report log.")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.25)
        try:
            conn.request("GET", "/")
            if conn.getresponse().status == 200:
                return
        except OSError:
            pass
        finally:
            conn.close()
        time.sleep(0.05)
    raise TimeoutError("Server missed the official 15-second startup deadline.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opponent", choices=OPPONENTS, default="random")
    parser.add_argument("--deals", type=int, default=1000)
    parser.add_argument("--seed", default="http-holdout-202")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "http-match.json")
    parser.add_argument("--logs", action="store_true", help="save official per-hand action logs")
    args = parser.parse_args()
    if args.deals < 1:
        parser.error("--deals must be positive")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    halves = []
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    # Local loopback testing uses one shared token if the caller set one.
    for key in ("AGENT1_TOKEN", "AGENT2_TOKEN"):
        if environment.get("AGENT_TOKEN"):
            environment[key] = environment["AGENT_TOKEN"]
        else:
            environment.pop(key, None)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    for half in (1, 2):
        processes, logs = [], []
        ports = (free_port(), free_port())
        while ports[0] == ports[1]:
            ports = (ports[0], free_port())
        try:
            for index, (module, app_dir) in enumerate(
                (("agent", ROOT), (OPPONENTS[args.opponent], ROOT / "baseline-bots"))
            ):
                log = open(output.with_suffix(f".half{half}.agent{index + 1}.log"), "w", encoding="utf-8")
                logs.append(log)
                env = {**environment, "PORT": str(ports[index])}
                started = time.monotonic()
                proc = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", f"{module}:app", "--app-dir", str(app_dir),
                     "--host", "127.0.0.1", "--port", str(ports[index]), "--no-access-log"],
                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                )
                processes.append(proc)
                ready(ports[index], proc, started + 15)
                print(f"half={half} server={module} startup={time.monotonic() - started:.3f}s", flush=True)
            half_file = output.with_suffix(f".half{half}.json")
            halves.append(half_file)
            judge_command = [sys.executable, "judge_engine.py", "--agent1", f"http://127.0.0.1:{ports[0]}",
                 "--agent2", f"http://127.0.0.1:{ports[1]}", "--half", str(half),
                 "--seed", args.seed, "--deals", str(args.deals), "--json", str(half_file)]
            if args.logs:
                judge_command.append("--logs")
            subprocess.run(
                judge_command,
                cwd=ROOT, env=environment, check=True, timeout=max(120, args.deals * 0.3),
                creationflags=flags,
            )
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for log in logs:
                log.close()
    subprocess.run(
        [sys.executable, "judge_engine.py", "combine", *map(str, halves), "--json", str(output)],
        cwd=ROOT, env=environment, check=True, creationflags=flags,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    print(f"{report['verdict']}: {report['mean_bb_per_deal']:+.3f} bb/paired deal; "
          f"95% CI={report['ci']}; report={output}", flush=True)
    for half, stats in enumerate(report["agent_stats"]["agent1"], 1):
        print(f"half={half} charged={stats['time_seconds']:.3f}s "
              f"errors={stats['errors']} timed_out={stats['timed_out']} "
              f"forfeited={stats['forfeited']}", flush=True)


if __name__ == "__main__":
    main()
