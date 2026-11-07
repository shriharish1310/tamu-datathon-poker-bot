from advanced_policy import Policy
from policy_config import PolicyConfig
_policy = Policy(PolicyConfig(**{'name': 'range_130_budget25', 'range_blend': 1.3, 'caller_power': 0.0, 'adaptive_max': 0, 'boundary_sigma': 0.75, 'position': 'legacy', 'samples': (24, 32, 40, 64), 'compute_fraction': 0.25}))
new_half = _policy.new_half
choose_action = _policy.choose_action
on_hand_end = _policy.on_hand_end
