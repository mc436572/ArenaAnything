from __future__ import annotations

from ssj.eval_case_env import eval_run_overrides_from_env


def test_overrides_empty_without_env(monkeypatch) -> None:
    monkeypatch.delenv('SSJ_EVAL_TEMPERATURE', raising=False)
    monkeypatch.delenv('SSJ_EVAL_TIMEOUT', raising=False)
    monkeypatch.delenv('SSJ_EVAL_PROBE_LIMIT', raising=False)
    o = eval_run_overrides_from_env()
    assert o.temperature is None
    assert o.timeout is None
    assert o.probe_limit is None


def test_overrides_parse_case_run_env(monkeypatch) -> None:
    monkeypatch.setenv('SSJ_EVAL_TEMPERATURE', '0')
    monkeypatch.setenv('SSJ_EVAL_TIMEOUT', '90')
    monkeypatch.setenv('SSJ_EVAL_PROBE_LIMIT', '5')
    o = eval_run_overrides_from_env()
    assert o.temperature == 0.0
    assert o.timeout == 90.0
    assert o.probe_limit == 5
