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
FAULT_MARKER = "BOT_STRATEGY_FAULT"


def validate_diagnostics(value: object) -> dict:
    """Reject missing evidence rather than interpreting it as zero faults."""
    if not isinstance(value, dict):
        raise ValueError("Bot health response has no diagnostics object")
    for key in ("fault_events", "fallback_decisions"):
        if type(value.get(key)) is not int or value[key] < 0:
            raise ValueError(f"Invalid reliability counter: {key}")
    if type(value.get("disabled")) is not bool:
        raise ValueError("Invalid reliability latch")
    for key in ("last_fault_stage", "last_fault_type"):
        if key not in value or (value[key] is not None and not isinstance(value[key], str)):
            raise ValueError(f"Invalid reliability metadata: {key}")
    return {key: value[key] for key in ("fault_events", "fallback_decisions", "disabled",
                                       "last_fault_stage", "last_fault_type")}


def capture_diagnostics(port: int) -> dict:
    """Read counters after the official half finishes, while its server is alive."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
    try:
        conn.request("GET", "/")
        response = conn.getresponse()
        payload = response.read()
        if response.status != 200:
            raise ValueError(f"Diagnostics request returned HTTP {response.status}")
        health = json.loads(payload)
        if not isinstance(health, dict):
            raise ValueError("Bot health response is not an object")
        return validate_diagnostics(health.get("diagnostics"))
    finally:
        conn.close()


def scan_fault_log(path: Path) -> int:
    """Inspect closed log files independently of the bot's own counters."""
    content = path.read_text(encoding="utf-8")
    if "Application startup complete" not in content:
        raise ValueError(f"Missing startup evidence in bot log: {path}")
    return content.count(FAULT_MARKER)


def write_reliability(output: Path, evidence: dict) -> None:
    output.with_suffix(".reliability.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(port: int, process: subprocess.Popen, deadline: float) -> dict:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Server exited; inspect its report log.")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.25)
        try:
            conn.request("GET", "/")
            response = conn.getresponse()
            if response.status == 200:
                identity = json.loads(response.read())
                if not isinstance(identity, dict):
                    raise ValueError("Server health response must be an object")
                return {key: identity.get(key) for key in ("participant", "agent_name")}
        except OSError:
            pass
        finally:
            conn.close()
        time.sleep(0.05)
    raise TimeoutError("Server missed the official 15-second startup deadline.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    opponents = parser.add_mutually_exclusive_group()
    opponents.add_argument("--opponent", choices=OPPONENTS, default="random")
    opponents.add_argument("--opponent-dir", type=Path,
                           help="directory containing another compatible agent.py (served on loopback)")
    parser.add_argument("--deals", type=int, default=1000)
    parser.add_argument("--seed", default="http-holdout-202")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "http-match.json")
    parser.add_argument("--logs", action="store_true", help="save official per-hand action logs")
    args = parser.parse_args()
    if args.deals < 1:
        parser.error("--deals must be positive")
    if args.opponent_dir is not None:
        opponent_dir = args.opponent_dir.resolve()
        if not (opponent_dir / "agent.py").is_file():
            parser.error("--opponent-dir must contain agent.py")
        opponent_module = "agent"
    else:
        opponent_dir = ROOT / "baseline-bots"
        opponent_module = OPPONENTS[args.opponent]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    halves = []
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # Local loopback testing uses one shared token if the caller set one.
    for key in ("AGENT1_TOKEN", "AGENT2_TOKEN"):
        if environment.get("AGENT_TOKEN"):
            environment[key] = environment["AGENT_TOKEN"]
        else:
            environment.pop(key, None)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    evidence = {"schema": "bot-reliability-v1", "status": "running", "match_seed": args.seed,
                "num_deals": args.deals, "halves": []}
    write_reliability(output, evidence)
    try:
        for half in (1, 2):
            processes, logs, identities = [], [], []
            diagnostics = None
            failure = None
            ports = (free_port(), free_port())
            while ports[0] == ports[1]:
                ports = (ports[0], free_port())
            try:
                for index, (module, app_dir) in enumerate(
                    (("agent", ROOT), (opponent_module, opponent_dir))
                ):
                    log = open(output.with_suffix(f".half{half}.agent{index + 1}.log"), "w", encoding="utf-8")
                    logs.append(log)
                    env = {**environment, "PORT": str(ports[index])}
                    started = time.monotonic()
                    proc = subprocess.Popen(
                        [sys.executable, "-m", "uvicorn", f"{module}:app", "--app-dir", str(app_dir),
                         "--host", "127.0.0.1", "--port", str(ports[index]), "--no-access-log"],
                        cwd=app_dir, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                    )
                    processes.append(proc)
                    identity = ready(ports[index], proc, started + 15)
                    identities.append(identity)
                    print(f"half={half} server={module} identity={identity} "
                          f"startup={time.monotonic() - started:.3f}s", flush=True)
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
                diagnostics = capture_diagnostics(ports[0])
            except Exception as exc:
                failure = exc
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
            # Read stderr only after the process and its inherited output stream close.
            log_faults = None
            try:
                log_faults = scan_fault_log(output.with_suffix(f".half{half}.agent1.log"))
            except (OSError, UnicodeError, ValueError) as exc:
                failure = failure or exc
            half_evidence = {"half": half, "diagnostics": diagnostics,
                             "log_fault_events": log_faults, "agents": identities}
            if failure is not None:
                half_evidence["evidence_error"] = f"{type(failure).__name__}: {failure}"
            evidence["halves"].append(half_evidence)
            write_reliability(output, evidence)
            if failure is not None:
                raise failure
        subprocess.run(
            [sys.executable, "judge_engine.py", "combine", *map(str, halves), "--json", str(output)],
            cwd=ROOT, env=environment, check=True, creationflags=flags,
        )
        evidence["status"] = "complete"
    except Exception as exc:
        evidence["status"] = "failed"
        evidence["failure"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_reliability(output, evidence)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(f"{report['verdict']}: {report['mean_bb_per_deal']:+.3f} bb/paired deal; "
          f"95% CI={report['ci']}; report={output}", flush=True)
    for half, stats in enumerate(report["agent_stats"]["agent1"], 1):
        extra = evidence["halves"][half - 1]
        print(f"half={half} charged={stats['time_seconds']:.3f}s "
              f"errors={stats['errors']} timed_out={stats['timed_out']} "
              f"forfeited={stats['forfeited']} "
              f"strategy_faults={extra['diagnostics']['fault_events']} "
              f"fallbacks={extra['diagnostics']['fallback_decisions']} "
              f"log_faults={extra['log_fault_events']}", flush=True)


if __name__ == "__main__":
    main()
