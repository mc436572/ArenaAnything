"""Run a static multiple-choice probe suite against one chat model."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ProbeProgressFn = Callable[[int, int, str, dict[str, Any]], None]

from ssj.model_chat_params import effective_chat_temperature
from ssj.model_ping import PingError
from ssj.model_reply import chat_probe_reply, parse_choice_letter, parse_mcq_choice, parse_probe_reply
from ssj.model_transport import probe_item_via_decisions, resolve_transport
from ssj.session_store import build_api_messages


def _normalize_expected_answer(item: dict[str, Any], raw: object) -> str:
    """Letter MCQ vs 是/否 vs 0/1."""
    mode = str(item.get('parse') or 'letter').strip().lower()
    s = str(raw or '').strip()
    if mode in ('one_zero', 'one-zero', 'binary_10'):
        if s in ('0', '1'):
            return s
        return s
    if mode in ('yes_no', 'yes-no', 'binary_zh'):
        if s in ('1', '是'):
            return '是'
        if s in ('0', '否'):
            return '否'
        return s
    return s.upper()


def score_item(item: dict[str, Any], reply: str, *, litellm_model: str = '') -> dict[str, Any]:
    mode = str(item.get('parse') or 'letter').strip().lower()
    if mode in ('one_zero', 'one-zero', 'binary_10', 'yes_no', 'yes-no', 'binary_zh'):
        parsed = parse_probe_reply(item, litellm_model, reply)
    elif litellm_model:
        parsed = parse_mcq_choice(litellm_model, reply)
    else:
        parsed = parse_choice_letter(reply)
    answer = _normalize_expected_answer(item, item.get('answer'))
    return {
        'id': item.get('id'),
        'answer': answer,
        'parsed': parsed,
        'correct': parsed is not None and parsed == answer,
        'reply': reply,
    }


def run_probe_suite(
    items: list[dict[str, Any]],
    litellm_model: str,
    *,
    complete: Callable[..., str] | None = None,
    system_prompt: str | None = None,
    temperature: float = 0,
    timeout: float = 60.0,
    max_tokens: int = 16,
    on_progress: ProbeProgressFn | None = None,
) -> dict[str, Any]:
    """Score each item in file order. A failed call counts as wrong."""
    call = complete or chat_probe_reply
    wire_temperature = effective_chat_temperature(litellm_model, temperature)
    rows: list[dict[str, Any]] = []
    total = len(items)
    for index, item in enumerate(items, start=1):
        prompt = str(item.get('prompt') or '')
        messages = build_api_messages([], prompt, system_prompt=system_prompt)
        started = time.perf_counter()
        error: str | None = None
        reply = ''
        try:
            if resolve_transport(litellm_model).kind == 'decisions':
                reply = probe_item_via_decisions(
                    litellm_model,
                    item,
                    system_prompt=system_prompt,
                    timeout=timeout,
                )
            else:
                reply = call(
                    litellm_model,
                    messages,
                    max_tokens=max_tokens,
                    temperature=wire_temperature,
                    timeout=timeout,
                )
        except PingError as exc:
            error = str(exc)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        row = score_item(item, reply, litellm_model=litellm_model)
        row['latency_ms'] = elapsed_ms
        if error:
            row['error'] = error
            row['correct'] = False
        rows.append(row)
        if on_progress is not None:
            item_id = str(item.get('id') or index)
            on_progress(index, total, item_id, row)

    n = len(rows)
    correct = sum(1 for row in rows if row['correct'])
    duration_sec = round(
        sum(float(row.get('latency_ms') or 0) for row in rows) / 1000.0,
        2,
    )
    throughput = round(n / duration_sec, 3) if duration_sec > 0 and n else 0.0
    return {
        'n': n,
        'correct': correct,
        'accuracy': (correct / n) if n else 0.0,
        'temperature': wire_temperature,
        'litellm_model': litellm_model,
        'duration_sec': duration_sec,
        'throughput': throughput,
        'items': rows,
    }


def write_probe_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def default_report_path(root: Path, suite: str, alias: str, *, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%SZ')
    safe_alias = re.sub(r'[^A-Za-z0-9._-]+', '_', alias.strip() or 'model')
    return root / 'reports' / f'eval-{suite}-{safe_alias}-{stamp}.json'
