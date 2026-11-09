from __future__ import annotations

from pathlib import Path

from ssj.session_store import (
    ACTIVE_GLOBAL_NAME,
    build_api_messages,
    load_history_messages,
    resolve_global_session_path,
)


def test_build_api_messages_with_system() -> None:
    msgs = build_api_messages([], 'hi', system_prompt='You are terse.')
    assert msgs == [
        {'role': 'system', 'content': 'You are terse.'},
        {'role': 'user', 'content': 'hi'},
    ]


def test_global_rotation_on_size(tmp_path: Path) -> None:
    first = resolve_global_session_path(tmp_path, max_bytes=100)
    first.write_text('x' * 120 + '\n', encoding='utf-8')
    pointer = tmp_path / 'session' / ACTIVE_GLOBAL_NAME
    pointer.write_text(first.name + '\n', encoding='utf-8')

    second = resolve_global_session_path(tmp_path, max_bytes=100)
    assert second != first
    assert second.name.startswith('global_')
    assert pointer.read_text(encoding='utf-8').strip() == second.name


def test_load_history_skips_system_prompt_field_rows(tmp_path: Path) -> None:
    path = tmp_path / 's.jsonl'
    path.write_text(
        '{"role":"user","content":"a","system_prompt":"sys"}\n'
        '{"role":"assistant","content":"b"}\n',
        encoding='utf-8',
    )
    assert load_history_messages(path) == [
        {'role': 'user', 'content': 'a'},
        {'role': 'assistant', 'content': 'b'},
    ]
