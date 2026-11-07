"""Freeze a policy configuration into a standalone bot folder for HTTP evaluation."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy_config import PolicyConfig, PROFILES

FILES = ("agent.py", "reliability.py", "advanced_policy.py", "baseline_strategy.py",
         "range_equity.py", "policy_config.py", "equity.py", "evaluator.py", "game.py", "requirements.txt")


def package(settings, target):
    # JSON represents tuples as lists. Emit the same frozen wrapper whether the
    # settings came from a dataclass in a local experiment or JSON in Linux CI.
    settings = replace(settings, samples=tuple(settings.samples))
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copyfile(ROOT / name, target / name)
    if settings.name == "baseline":
        wrapper = "from baseline_strategy import new_half, choose_action, on_hand_end\n"
    else:
        wrapper = ("from advanced_policy import Policy\nfrom policy_config import PolicyConfig\n"
                   f"_policy = Policy(PolicyConfig(**{settings.to_dict()!r}))\n"
                   "new_half = _policy.new_half\nchoose_action = _policy.choose_action\n"
                   "on_hand_end = _policy.on_hand_end\n")
    (target / "strategy.py").write_text(wrapper, encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}
    (target / "profile.json").write_text(json.dumps(
        {"settings": settings.to_dict(), "sha256": hashes}, indent=2) + "\n", encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--configs", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    profiles = dict(PROFILES)
    if args.configs:
        for data in json.loads(args.configs.read_text(encoding="utf-8")):
            settings = PolicyConfig(**data)
            profiles[settings.name] = settings
    print(package(profiles[args.profile], args.output))


if __name__ == "__main__":
    main()
