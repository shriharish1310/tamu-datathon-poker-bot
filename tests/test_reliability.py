"""Fault injection for the reliable strategy adapter and observable fallbacks."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import reliability
import strategy
from game import Action, AgentConfig, Game, make_deal


def _memory():
    memory = {}
    reliability.new_half(AgentConfig(), memory)
    return memory


def _observation(owed: bool = True):
    game = Game(make_deal("reliability-faults", 0), button_seat=0)
    if not owed:
        game.apply(Action.CHECK_CALL)  # big blind may now check for free
    return game.observation(game.to_act)


def _result():
    game = Game(make_deal("reliability-faults", 0), button_seat=0)
    game.apply(Action.FOLD)
    return game.hand_result(0)


def _fault_logs(caplog):
    return [record for record in caplog.records if "BOT_STRATEGY_FAULT" in record.getMessage()]


@pytest.mark.parametrize("owed,expected", [(True, Action.FOLD), (False, Action.CHECK_CALL)])
def test_exception_returns_safe_legal_action_and_logs_traceback(monkeypatch, caplog, owed, expected):
    memory, obs = _memory(), _observation(owed)

    def broken(observation, state):
        state["partially_updated"] = True
        raise RuntimeError("injected equity failure")

    monkeypatch.setattr(strategy, "choose_action", broken)
    with caplog.at_level(logging.ERROR):
        action = reliability.choose_action(obs, memory)
    assert action == expected and action in obs.legal_actions
    diagnostics = reliability.diagnostics(memory)
    assert diagnostics["fault_events"] == 1
    assert diagnostics["fallback_decisions"] == 1
    assert diagnostics["disabled"] is True
    assert diagnostics["last_fault_stage"] == "choose_action"
    assert diagnostics["last_fault_type"] == "RuntimeError"
    records = _fault_logs(caplog)
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert records[0].exc_info[0] is RuntimeError
    assert "injected equity failure" in caplog.text
    assert "Traceback" in caplog.text


def test_fault_latches_without_reentering_corrupted_strategy_or_logging_repeatedly(monkeypatch, caplog):
    memory, calls = _memory(), {"choose": 0, "end": 0}

    def broken(obs, state):
        calls["choose"] += 1
        raise ValueError("state became inconsistent")

    def unexpected_callback(result, state):
        calls["end"] += 1
        raise AssertionError("disabled policy must not receive callbacks")

    monkeypatch.setattr(strategy, "choose_action", broken)
    monkeypatch.setattr(strategy, "on_hand_end", unexpected_callback)
    with caplog.at_level(logging.ERROR):
        assert reliability.choose_action(_observation(), memory) == Action.FOLD
        for _ in range(8):
            assert reliability.choose_action(_observation(False), memory) == Action.CHECK_CALL
            reliability.on_hand_end(_result(), memory)
    assert calls == {"choose": 1, "end": 0}
    assert len(_fault_logs(caplog)) == 1
    assert reliability.diagnostics(memory)["fault_events"] == 1
    assert reliability.diagnostics(memory)["fallback_decisions"] == 9


@pytest.mark.parametrize("invalid", [True, 1, None, "CHECK_CALL", Action.FOLD])
def test_invalid_policy_return_is_observed_even_when_python_equality_would_accept_it(monkeypatch, invalid):
    # Action is an IntEnum: both True and integer 1 compare equal to CHECK_CALL.
    # They must still be rejected before the server serializes a malformed action.
    memory, obs = _memory(), _observation(False)
    assert Action.FOLD not in obs.legal_actions
    monkeypatch.setattr(strategy, "choose_action", lambda *_: invalid)
    assert reliability.choose_action(obs, memory) == Action.CHECK_CALL
    diagnostics = reliability.diagnostics(memory)
    assert diagnostics["fault_events"] == 1
    assert diagnostics["fallback_decisions"] == 1
    assert diagnostics["disabled"] is True


def test_hand_end_exception_latches_before_the_next_decision(monkeypatch, caplog):
    memory = _memory()

    def broken(result, state):
        raise LookupError("injected opponent update failure")

    monkeypatch.setattr(strategy, "on_hand_end", broken)
    with caplog.at_level(logging.ERROR):
        reliability.on_hand_end(_result(), memory)
    diagnostics = reliability.diagnostics(memory)
    assert diagnostics["fault_events"] == 1
    assert diagnostics["fallback_decisions"] == 0
    assert diagnostics["last_fault_stage"] == "on_hand_end"
    assert diagnostics["last_fault_type"] == "LookupError"
    assert len(_fault_logs(caplog)) == 1
    assert reliability.choose_action(_observation(), memory) == Action.FOLD
    assert reliability.diagnostics(memory)["fallback_decisions"] == 1


def test_initialization_exception_still_allows_observable_safe_decisions(monkeypatch, caplog):
    memory = {"old_half_marker": "must disappear"}

    def broken(config, state):
        state.clear()
        state["incomplete_initialization"] = True
        raise RuntimeError("injected initialization failure")

    monkeypatch.setattr(strategy, "new_half", broken)
    with caplog.at_level(logging.ERROR):
        reliability.new_half(AgentConfig(), memory)
    assert "old_half_marker" not in memory
    diagnostics = reliability.diagnostics(memory)
    assert diagnostics["disabled"] is True
    assert diagnostics["fault_events"] == 1
    assert diagnostics["last_fault_stage"] == "new_half"
    assert reliability.choose_action(_observation(), memory) == Action.FOLD
    assert len(_fault_logs(caplog)) == 1


def test_new_half_clears_fault_latch_and_old_learning_in_same_dictionary(monkeypatch):
    memory = _memory()
    real_choose = strategy.choose_action

    def broken(*args):
        raise ArithmeticError("injected")

    monkeypatch.setattr(strategy, "choose_action", broken)
    reliability.choose_action(_observation(), memory)
    memory["old_half_marker"] = 99
    reliability.new_half(AgentConfig(), memory)
    assert "old_half_marker" not in memory
    diagnostics = reliability.diagnostics(memory)
    assert diagnostics["fault_events"] == diagnostics["fallback_decisions"] == 0
    assert diagnostics["disabled"] is False
    assert diagnostics["last_fault_stage"] is None
    assert diagnostics["last_fault_type"] is None
    monkeypatch.setattr(strategy, "choose_action", real_choose)
    assert reliability.choose_action(_observation(), memory) in _observation().legal_actions
    assert reliability.diagnostics(memory)["fault_events"] == 0


@pytest.mark.parametrize("exit_signal", [KeyboardInterrupt, SystemExit])
def test_process_control_exceptions_are_not_swallowed(monkeypatch, exit_signal):
    memory = _memory()

    def interrupted(*args):
        raise exit_signal()

    monkeypatch.setattr(strategy, "choose_action", interrupted)
    with pytest.raises(exit_signal):
        reliability.choose_action(_observation(), memory)
    assert reliability.diagnostics(memory)["fault_events"] == 0


def test_healthy_policy_action_and_callback_behavior_are_preserved(monkeypatch):
    memory, observed = _memory(), []
    obs, result = _observation(), _result()
    forwarded = []

    def choose(observation, state):
        assert observation is obs
        forwarded.append(state)
        state["callback_marker"] = "set during choose"
        observed.append("choose")
        return Action.RAISE_POT

    def hand_end(finished, state):
        assert finished is result and state is forwarded[0]
        assert state["callback_marker"] == "set during choose"
        observed.append("end")

    monkeypatch.setattr(strategy, "choose_action", choose)
    monkeypatch.setattr(strategy, "on_hand_end", hand_end)
    assert reliability.choose_action(obs, memory) == Action.RAISE_POT
    reliability.on_hand_end(result, memory)
    assert observed == ["choose", "end"]
    diagnostics = reliability.diagnostics(memory)
    assert diagnostics["fault_events"] == diagnostics["fallback_decisions"] == 0
    assert diagnostics["disabled"] is False


def test_http_adapter_reports_fallback_without_changing_official_action_reply(monkeypatch, caplog):
    from fastapi.testclient import TestClient

    spec = importlib.util.spec_from_file_location("reliability_agent_under_test", ROOT / "agent.py")
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    agent.TOKEN = "reliability-test-token"
    auth = {"X-Agent-Token": agent.TOKEN}

    def broken(*args):
        raise RuntimeError("HTTP fault injection")

    monkeypatch.setattr(strategy, "choose_action", broken)
    with TestClient(agent.app) as client, caplog.at_level(logging.ERROR):
        assert client.post("/new-half", json={"config": AgentConfig().to_dict()}, headers=auth).status_code == 200
        response = client.post("/act", json={"observation": _observation().to_dict(), "hand_results": []}, headers=auth)
        assert response.status_code == 200
        assert response.json() == {"action": "FOLD", "hand_end_errors": []}
        health = client.get("/").json()
        assert health["participant"] and health["agent_name"]
        assert health["diagnostics"]["fault_events"] == 1
        assert health["diagnostics"]["fallback_decisions"] == 1
        assert health["diagnostics"]["disabled"] is True
        # A completed hand after fallback cannot crash opponent-model updates.
        assert client.post("/hand-end", json={"results": [_result().to_dict()]}, headers=auth).json() == {
            "ok": True, "hand_end_errors": [],
        }
    assert len(_fault_logs(caplog)) == 1
