from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ssj.chat_profile import (
    load_chat_profile,
    merge_chat_options,
    resolve_chat_profile_path,
)


def test_load_profile_and_merge(tmp_path: Path) -> None:
    path = tmp_path / 'p.yaml'
    path.write_text(
        yaml.safe_dump(
            {
                'system_prompt': 'from file',
                'with_context': True,
                'timeout': 90,
                'max_tokens': 512,
            }
        ),
        encoding='utf-8',
    )
    prof = load_chat_profile(path)
    merged = merge_chat_options(
        prof,
        system_prompt=None,
        system_prompt_set=False,
        with_context=None,
        timeout=None,
        max_tokens=1024,
    )
    assert merged.system_prompt == 'from file'
    assert merged.with_context is True
    assert merged.timeout == 90
    assert merged.max_tokens == 1024


def test_rejects_text_in_profile(tmp_path: Path) -> None:
    path = tmp_path / 'bad.yaml'
    path.write_text('text: hi\n', encoding='utf-8')
    with pytest.raises(ValueError, match='must not include "text"'):
        load_chat_profile(path)


def test_resolve_profile_name_only(tmp_path: Path) -> None:
    prof_dir = tmp_path / 'chat-profiles'
    prof_dir.mkdir()
    (prof_dir / 'mine.yaml').write_text('{}\n', encoding='utf-8')
    resolved = resolve_chat_profile_path(prof_dir, 'mine.yaml')
    assert resolved == (prof_dir / 'mine.yaml').resolve()
    resolved2 = resolve_chat_profile_path(prof_dir, 'mine')
    assert resolved2 == resolved


def test_legacy_json_profile_still_loads(tmp_path: Path) -> None:
    prof_dir = tmp_path / 'chat-profiles'
    prof_dir.mkdir()
    (prof_dir / 'legacy.json').write_text('{"with_context": true}', encoding='utf-8')
    resolved = resolve_chat_profile_path(prof_dir, 'legacy.json')
    prof = load_chat_profile(resolved)
    assert prof.with_context is True


def test_rejects_path_in_profile_name(tmp_path: Path) -> None:
    prof_dir = tmp_path / 'chat-profiles'
    prof_dir.mkdir()
    with pytest.raises(ValueError, match='file name only'):
        resolve_chat_profile_path(prof_dir, 'chat-profiles/mine.yaml')


def test_resolve_builtin_when_instance_empty(tmp_path: Path) -> None:
    prof_dir = tmp_path / 'empty-profiles'
    prof_dir.mkdir()
    resolved = resolve_chat_profile_path(prof_dir, 'demo-profile')
    assert resolved.name == 'demo-profile.yaml'
    assert 'ssj' in resolved.parts and 'chat-profiles' in resolved.parts
