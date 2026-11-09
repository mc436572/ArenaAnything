"""Session jsonl under <root>/session/ (semantic turns; traces hold raw HTTP)."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

ACTIVE_GLOBAL_NAME = '.active_global'
DEFAULT_GLOBAL_MAX_BYTES = 1_000_000
_HISTORY_ROLES = frozenset({'user', 'assistant'})


def session_dir(data_dir: Path) -> Path:
    path = data_dir / 'session'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _random_suffix(n: int = 8) -> str:
    return secrets.token_hex(n // 2) if n % 2 == 0 else secrets.token_hex((n + 1) // 2)[:n]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_ephemeral_session_path(data_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d')
    name = f'{stamp}_{_random_suffix(8)}.jsonl'
    return session_dir(data_dir) / name


def _new_global_path(data_dir: Path) -> Path:
    name = f'global_{_random_suffix(8)}.jsonl'
    return session_dir(data_dir) / name


def _read_active_global_name(data_dir: Path) -> str | None:
    pointer = session_dir(data_dir) / ACTIVE_GLOBAL_NAME
    if not pointer.is_file():
        return None
    name = pointer.read_text(encoding='utf-8').strip()
    return name or None


def _write_active_global_name(data_dir: Path, filename: str) -> None:
    pointer = session_dir(data_dir) / ACTIVE_GLOBAL_NAME
    pointer.write_text(filename + '\n', encoding='utf-8')


def resolve_global_session_path(
    data_dir: Path,
    *,
    max_bytes: int = DEFAULT_GLOBAL_MAX_BYTES,
) -> Path:
    """Current writable global segment; rotate when file size >= max_bytes."""
    sdir = session_dir(data_dir)
    active_name = _read_active_global_name(data_dir)
    if active_name:
        active_path = sdir / active_name
        if active_path.is_file() and active_path.stat().st_size < max_bytes:
            return active_path
        if active_path.is_file() and active_path.stat().st_size >= max_bytes:
            pass  # fall through to new segment

    new_path = _new_global_path(data_dir)
    new_path.touch()
    _write_active_global_name(data_dir, new_path.name)
    return new_path


def load_history_messages(session_path: Path) -> list[dict[str, str]]:
    if not session_path.is_file():
        return []
    history: list[dict[str, str]] = []
    with session_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = row.get('role')
            if role not in _HISTORY_ROLES:
                continue
            content = row.get('content')
            if content is None:
                continue
            history.append({'role': str(role), 'content': str(content)})
    return history


def build_api_messages(
    history: list[dict[str, str]],
    user_text: str,
    *,
    system_prompt: str | None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.extend(history)
    messages.append({'role': 'user', 'content': user_text})
    return messages


def append_turn(
    session_path: Path,
    *,
    user_text: str,
    assistant_text: str,
    trace_ref: str,
    system_prompt: str | None = None,
    model: str | None = None,
) -> None:
    session_path.parent.mkdir(parents=True, exist_ok=True)
    ts = _utc_now_iso()
    user_row: dict[str, object] = {
        'role': 'user',
        'content': user_text,
        'ts': ts,
        'trace_ref': trace_ref,
    }
    if system_prompt:
        user_row['system_prompt'] = system_prompt
    if model:
        user_row['model'] = model
    assistant_row: dict[str, object] = {
        'role': 'assistant',
        'content': assistant_text,
        'ts': ts,
        'trace_ref': trace_ref,
    }
    with session_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(user_row, ensure_ascii=False) + '\n')
        f.write(json.dumps(assistant_row, ensure_ascii=False) + '\n')
