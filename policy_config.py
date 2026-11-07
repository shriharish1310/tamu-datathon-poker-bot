"""Finite, predeclared experimental policy configurations (no trained model)."""
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class PolicyConfig:
    name: str = "baseline"
    range_blend: float = 0.0
    caller_power: float = 0.0
    adaptive_max: int = 0
    boundary_sigma: float = 0.75
    position: str = "legacy"
    samples: tuple[int, ...] = (24, 32, 40, 64)
    compute_fraction: float = 0.35

    def to_dict(self):
        return asdict(self)


BASE = PolicyConfig()
PROFILES = {p.name: p for p in (
    BASE,
    replace(BASE, name="range_light", range_blend=0.35),
    replace(BASE, name="range_medium", range_blend=0.70),
    replace(BASE, name="range_strong", range_blend=1.0),
    replace(BASE, name="callers_light", caller_power=0.5),
    replace(BASE, name="callers_standard", caller_power=1.0),
    replace(BASE, name="adaptive_96", adaptive_max=96, boundary_sigma=0.60),
    replace(BASE, name="adaptive_128", adaptive_max=128, boundary_sigma=1.0),
    replace(BASE, name="position_no_preflop", position="no_preflop"),
    replace(BASE, name="position_street_order", position="street_order"),
    replace(BASE, name="position_none", position="none"),
)}
