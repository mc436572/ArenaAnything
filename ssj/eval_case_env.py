"""Arena-injected eval run params (from case.yaml ``run:``). Manual ``ssj eval`` omits these env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalRunOverrides:
    """Non-None fields override chat profile / probe_runner defaults."""

    temperature: float | None = None
    timeout: float | None = None
    probe_limit: int | None = None


def _parse_float(name: str) -> float | None:
    if name not in os.environ:
        return None
    raw = os.environ.get(name, '').strip()
    if not raw:
        return None
    return float(raw)


def _parse_int(name: str) -> int | None:
    if name not in os.environ:
        return None
    raw = os.environ.get(name, '').strip()
    if not raw:
        return None
    return int(raw)


def eval_run_overrides_from_env() -> EvalRunOverrides:
    return EvalRunOverrides(
        temperature=_parse_float('SSJ_EVAL_TEMPERATURE'),
        timeout=_parse_float('SSJ_EVAL_TIMEOUT'),
        probe_limit=_parse_int('SSJ_EVAL_PROBE_LIMIT'),
    )
