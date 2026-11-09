from __future__ import annotations

import os
from pathlib import Path

import pytest

from ssj.model_list_labels import (
    KEYS_CONFIGURED,
    KEYS_MISSING,
    KEYS_UNKNOWN,
    TYPE_BUILTIN,
    TYPE_CUSTOM,
    profile_keys_label,
    profile_type_label,
)
from ssj.models_store import ModelProfile, load_models_store


def test_type_label() -> None:
    assert profile_type_label(ModelProfile('ds', 'x', builtin=True)) == TYPE_BUILTIN
    assert profile_type_label(ModelProfile('mine', 'x', builtin=False)) == TYPE_CUSTOM


def test_keys_label(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    (tmp_path / 'config.yaml').write_text('profile: dev\n', encoding='utf-8')
    assert profile_keys_label('deepseek/x') == KEYS_MISSING
    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=sk-abc\n', encoding='utf-8')
    from ssj.settings import load_settings

    load_settings()
    assert profile_keys_label('deepseek/x') == KEYS_CONFIGURED
    assert profile_keys_label('unknown/provider-x') == KEYS_UNKNOWN


def test_openrouter_typesafe_accepts_legacy_typesafe_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'config.yaml').write_text('profile: dev\n', encoding='utf-8')
    (tmp_path / 'models.yaml').write_text(
        'default: jev\nmodels:\n  jev:\n    litellm: openrouter/typesafe/jev-latest\n',
        encoding='utf-8',
    )
    (tmp_path / '.env').write_text(
        "TYPESAFE_API_KEY=sk-or-v1-abcdefghijklmnop\n",
        encoding='utf-8',
    )
    from ssj.settings import load_settings

    load_settings()
    assert profile_keys_label('openrouter/typesafe/jev-latest') == KEYS_CONFIGURED
    assert 'OPENROUTER_API_KEY=' in (tmp_path / '.env').read_text(encoding='utf-8')


def test_merge_adds_new_builtins(tmp_path: Path) -> None:
    (tmp_path / 'models.yaml').write_text(
        'default: ds\nmodels:\n  ds:\n    litellm: deepseek/deepseek-chat\n    builtin: true\n',
        encoding='utf-8',
    )
    store = load_models_store(tmp_path)
    assert 'jev' in store.models
    assert 'mimo' in store.models
