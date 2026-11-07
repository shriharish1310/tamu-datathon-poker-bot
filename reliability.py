"""Observable, conservative protection around the tournament strategy callbacks.

A strategy fault disables the core for the remainder of the half. This avoids
reusing partially mutated state or repeatedly spending time on the same failure.
The legal fallback preserves eligibility; ANY fault/fallback fails our release
checks. This cannot recover from process death or interrupt a hanging callback.
"""

from __future__ import annotations

import logging

import strategy
from game import Action, AgentConfig, HandResult, Observation

LOGGER = logging.getLogger("poker.reliability")
CORE_KEY = "_strategy"
STATE_KEY = "_reliability"


def _fresh_diagnostics() -> dict:
    return {"fault_events": 0, "fallback_decisions": 0, "disabled": False,
            "last_fault_stage": None, "last_fault_type": None}


def diagnostics(memory: dict) -> dict:
    """Return counters only: never expose cards, opponent data, or core state."""
    return dict(memory.get(STATE_KEY, _fresh_diagnostics()))


def _record_fault(memory: dict, stage: str, exc: Exception) -> None:
    state = memory[STATE_KEY]
    # Latch before logging so even a logging failure cannot re-enter the core.
    state["disabled"] = True
    state["fault_events"] += 1
    state["last_fault_stage"] = stage
    state["last_fault_type"] = type(exc).__name__
    LOGGER.error("BOT_STRATEGY_FAULT stage=%s exception_type=%s; disabled for this half",
                 stage, type(exc).__name__, exc_info=True)


def _fallback(obs: Observation, memory: dict) -> Action:
    memory[STATE_KEY]["fallback_decisions"] += 1
    if obs.to_call == 0 and Action.CHECK_CALL in obs.legal_actions:
        return Action.CHECK_CALL
    if Action.FOLD in obs.legal_actions:
        return Action.FOLD
    if Action.CHECK_CALL in obs.legal_actions:
        return Action.CHECK_CALL
    # The official engine always offers check/call. Do not invent a raise when
    # a malformed observation offers no conservative action.
    raise ValueError("No conservative legal fallback is available")


def new_half(config: AgentConfig, memory: dict) -> None:
    memory.clear()
    # The core can clear/corrupt its own state without erasing fault evidence.
    memory[CORE_KEY] = {}
    memory[STATE_KEY] = _fresh_diagnostics()
    try:
        strategy.new_half(config, memory[CORE_KEY])
    except Exception as exc:
        _record_fault(memory, "new_half", exc)


def choose_action(obs: Observation, memory: dict) -> Action:
    if memory[STATE_KEY]["disabled"]:
        return _fallback(obs, memory)
    try:
        action = strategy.choose_action(obs, memory[CORE_KEY])
        # IntEnum equality alone accepts bools/ints, which the HTTP judge rejects.
        if not isinstance(action, Action) or action not in obs.legal_actions:
            raise ValueError(f"Strategy returned an invalid action: {action!r}")
        return action
    except Exception as exc:
        _record_fault(memory, "choose_action", exc)
        return _fallback(obs, memory)


def on_hand_end(result: HandResult, memory: dict) -> None:
    if memory[STATE_KEY]["disabled"]:
        return
    try:
        strategy.on_hand_end(result, memory[CORE_KEY])
    except Exception as exc:
        _record_fault(memory, "on_hand_end", exc)
