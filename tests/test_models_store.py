"""models.yaml store 与内置 catalog。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ssj.models_store import (
    add_profile,
    delete_profile,
    load_models_store,
    matches_pattern,
    set_default,
    validate_alias,
)


def test_init_seeds_ds_kimi_grok(tmp_path: Path) -> None:
    store = load_models_store(tmp_path)
    assert (tmp_path / 'models.yaml').is_file()
    assert set(store.list_aliases()) >= {'ds', 'kimi', 'grok', 'jev', 'glm', 'mimo'}
    assert store.default == 'ds'
    assert store.default_litellm() == 'deepseek/deepseek-chat'


def test_add_custom_alias(tmp_path: Path) -> None:
    store = load_models_store(tmp_path)
    add_profile(store, 'ds1017', 'deepseek/deepseek-chat', description='Oct build')
    store = load_models_store(tmp_path)
    assert store.get('ds1017') is not None
    assert store.get('ds1017').description == 'Oct build'


def test_use_and_del(tmp_path: Path) -> None:
    store = load_models_store(tmp_path)
    add_profile(store, 'fast', 'deepseek/deepseek-chat')
    set_default(store, 'fast')
    store = load_models_store(tmp_path)
    assert store.default == 'fast'
    set_default(store, 'ds')
    delete_profile(store, 'fast')
    store = load_models_store(tmp_path)
    assert 'fast' not in store.models


def test_cannot_del_default(tmp_path: Path) -> None:
    store = load_models_store(tmp_path)
    add_profile(store, 'mine', 'deepseek/deepseek-chat')
    set_default(store, 'mine')
    store = load_models_store(tmp_path)
    with pytest.raises(ValueError, match='default'):
        delete_profile(store, 'mine')


def test_cannot_del_builtin_without_force(tmp_path: Path) -> None:
    store = load_models_store(tmp_path)
    add_profile(store, 'extra', 'deepseek/deepseek-chat')
    set_default(store, 'extra')
    with pytest.raises(ValueError, match='built-in'):
        delete_profile(store, 'ds')


def test_legacy_config_model_migrates(tmp_path: Path) -> None:
    store = load_models_store(tmp_path, legacy_config_model='from-file')
    assert store.default in {'main', 'legacy'}
    assert store.default_litellm() == 'from-file'


def test_matches_pattern_wildcard() -> None:
    from ssj.models_store import ModelProfile

    p = ModelProfile('ds1017', 'deepseek/deepseek-chat', 'Oct snapshot')
    assert matches_pattern(p, '*ds*')
    assert not matches_pattern(p, '*grok*')


def test_validate_alias_rejects_bad() -> None:
    with pytest.raises(ValueError):
        validate_alias('DS')
    with pytest.raises(ValueError):
        validate_alias('9bad')
