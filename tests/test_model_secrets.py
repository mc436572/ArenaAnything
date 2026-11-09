"""model → .env 密钥清单。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ssj.model_secrets import (
    resolve_secrets_for_model,
    secret_status,
    validate_key_for_model,
    write_env_example,
)
from ssj.settings import load_settings, set_env_key


def test_deepseek_key_and_optional_base() -> None:
    specs = resolve_secrets_for_model('deepseek/deepseek-chat')
    assert [s.name for s in specs] == ['DEEPSEEK_API_KEY', 'DEEPSEEK_API_BASE']
    validate_key_for_model('deepseek/deepseek-chat', 'DEEPSEEK_API_KEY')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        validate_key_for_model('deepseek/deepseek-chat', 'OPENAI_API_KEY')


def test_openai_allows_base_url() -> None:
    names = {s.name for s in resolve_secrets_for_model('openai/gpt-4o')}
    assert names == {'OPENAI_API_KEY', 'OPENAI_API_BASE'}


def test_jev_glm_mimo_keys() -> None:
    jev = {s.name for s in resolve_secrets_for_model('typesafe/jev-latest')}
    assert 'TYPESAFE_API_KEY' in jev
    glm = {s.name for s in resolve_secrets_for_model('zai/glm-4.7')}
    assert 'ZAI_API_KEY' in glm
    xm = {s.name for s in resolve_secrets_for_model('xiaomi_mimo/mimo-v2.6-flash')}
    assert xm == {'XIAOMI_MIMO_API_KEY', 'XIAOMI_MIMO_API_BASE'}
    grok = {s.name for s in resolve_secrets_for_model('xai/grok-2-1212')}
    assert grok == {'XAI_API_KEY', 'XAI_API_BASE'}
    claude = {s.name for s in resolve_secrets_for_model('anthropic/claude-sonnet-4')}
    assert claude == {'ANTHROPIC_API_KEY', 'ANTHROPIC_API_BASE'}
    gem = {s.name for s in resolve_secrets_for_model('gemini/gemini-2.0-flash')}
    assert gem == {'GEMINI_API_KEY', 'GEMINI_API_BASE'}


def test_openrouter_and_moonshot_keys() -> None:
    or_keys = {s.name for s in resolve_secrets_for_model('openrouter/anthropic/claude-sonnet-4')}
    assert or_keys == {'OPENROUTER_API_KEY', 'OPENROUTER_API_BASE'}
    jev_or = {s.name for s in resolve_secrets_for_model('openrouter/typesafe/jev-latest')}
    assert jev_or == {'OPENROUTER_API_KEY', 'OPENROUTER_API_BASE'}
    kimi_keys = {s.name for s in resolve_secrets_for_model('moonshot/kimi-k2-turbo-preview')}
    assert kimi_keys == {'MOONSHOT_API_KEY', 'MOONSHOT_API_BASE'}
    validate_key_for_model('openrouter/x', 'OPENROUTER_API_KEY')
    validate_key_for_model('moonshot/x', 'MOONSHOT_API_KEY')


def test_env_example_lists_model_keys(tmp_path: Path) -> None:
    path = tmp_path / '.env.example'
    write_env_example(path, 'deepseek/deepseek-chat')
    text = path.read_text(encoding='utf-8')
    assert 'DEEPSEEK_API_KEY=' in text
    assert 'deepseek/deepseek-chat' in text


def test_secret_status_marks_required_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'config.yaml').write_text('model: deepseek/x\n', encoding='utf-8')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    load_settings()
    rows = secret_status('deepseek/x')
    assert len(rows) == 2
    assert 'required, not set' in rows[0][1]

    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=sk-abcdefghijklmnop\n', encoding='utf-8')
    load_settings()
    rows2 = secret_status('deepseek/x')
    assert 'sk-ab' in rows2[0][1] and 'mnop' in rows2[0][1]


def test_set_rejects_wrong_key_for_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match='Allowed'):
        set_env_key('OPENAI_API_KEY', 'x', model='deepseek/deepseek-chat')
