"""进程根 models.yaml：代号 → LiteLLM model id，default 为当前 Agent 用的 profile。"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ssj.model_catalog import BUILTIN_CATALOG, BUILTIN_ALIASES, DEFAULT_ALIAS

MODELS_FILENAME = 'models.yaml'
_ALIAS_RE = re.compile(r'^[a-z][a-z0-9_-]*$')


@dataclass
class ModelProfile:
    alias: str
    litellm: str
    description: str = ''
    builtin: bool = False


@dataclass
class ModelsStore:
    path: Path
    default: str
    models: dict[str, ModelProfile]

    def default_profile(self) -> ModelProfile:
        prof = self.models.get(self.default)
        if prof is None:
            raise ValueError(f'Default model {self.default!r} is missing from models.yaml')
        return prof

    def default_litellm(self) -> str:
        return self.default_profile().litellm

    def get(self, alias: str) -> ModelProfile | None:
        return self.models.get(alias)

    def list_aliases(self) -> list[str]:
        return sorted(self.models.keys())


def validate_alias(alias: str) -> str:
    name = alias.strip()
    if not _ALIAS_RE.fullmatch(name):
        raise ValueError(
            f'Invalid alias {alias!r}. Use lowercase letters, digits, _ and - '
            '(must start with a letter).'
        )
    return name


def _profile_from_dict(alias: str, raw: object) -> ModelProfile | None:
    if not isinstance(raw, dict):
        return None
    litellm = str(raw.get('litellm') or '').strip()
    if not litellm:
        return None
    desc = str(raw.get('description') or '').strip()
    builtin = bool(raw.get('builtin', alias in BUILTIN_ALIASES))
    return ModelProfile(alias=alias, litellm=litellm, description=desc, builtin=builtin)


def _serialize_store(store: ModelsStore) -> dict:
    models_block: dict[str, dict] = {}
    for alias in sorted(store.models.keys()):
        p = store.models[alias]
        block: dict = {'litellm': p.litellm}
        if p.description:
            block['description'] = p.description
        if p.builtin:
            block['builtin'] = True
        models_block[alias] = block
    return {'default': store.default, 'models': models_block}


def write_models_store(path: Path, store: ModelsStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(_serialize_store(store), f, sort_keys=False, allow_unicode=True)


def _seed_from_catalog() -> dict[str, ModelProfile]:
    out: dict[str, ModelProfile] = {}
    for entry in BUILTIN_CATALOG:
        out[entry.alias] = ModelProfile(
            alias=entry.alias,
            litellm=entry.litellm,
            description=entry.description,
            builtin=True,
        )
    return out


def _migrate_legacy_model(litellm: str, models: dict[str, ModelProfile]) -> str:
    """若 config.yaml 里有过 model，对齐已有代号；否则写入 main/legacy 并设为 default。"""
    normalized = litellm.strip()
    if not normalized:
        return DEFAULT_ALIAS
    for prof in models.values():
        if prof.litellm == normalized:
            return prof.alias
    custom_alias = 'main' if 'main' not in models else 'legacy'
    models[custom_alias] = ModelProfile(
        alias=custom_alias,
        litellm=normalized,
        description='Migrated from config.yaml',
        builtin=False,
    )
    return custom_alias


def ensure_models_file(root: Path, *, legacy_config_model: str | None = None) -> Path:
    """创建或迁移 models.yaml；返回路径。"""
    path = root / MODELS_FILENAME
    if path.is_file():
        return path

    models = _seed_from_catalog()
    default = DEFAULT_ALIAS
    if legacy_config_model:
        default = _migrate_legacy_model(legacy_config_model, models)

    store = ModelsStore(path=path, default=default, models=models)
    write_models_store(path, store)
    return path


def load_models_store(root: Path, *, legacy_config_model: str | None = None) -> ModelsStore:
    path = root / MODELS_FILENAME
    if not path.is_file():
        ensure_models_file(root, legacy_config_model=legacy_config_model)
    with path.open(encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        data = {}

    default = str(data.get('default') or DEFAULT_ALIAS).strip() or DEFAULT_ALIAS
    raw_models = data.get('models')
    models: dict[str, ModelProfile] = {}
    if isinstance(raw_models, dict):
        for key, val in raw_models.items():
            if not isinstance(key, str):
                continue
            prof = _profile_from_dict(key, val)
            if prof is not None:
                models[key] = prof

    if not models:
        models = _seed_from_catalog()
        default = DEFAULT_ALIAS

    if default not in models:
        default = DEFAULT_ALIAS if DEFAULT_ALIAS in models else next(iter(models))

    changed = _merge_missing_builtins(models)
    changed = _sync_catalog_descriptions(models) or changed
    store = ModelsStore(path=path, default=default, models=models)
    if changed:
        write_models_store(path, store)
    return store


def _sync_catalog_descriptions(models: dict[str, ModelProfile]) -> bool:
    """Refresh built-in profile descriptions from catalog (e.g. locale updates)."""
    by_alias = {entry.alias: entry for entry in BUILTIN_CATALOG}
    changed = False
    for alias, prof in models.items():
        if not prof.builtin:
            continue
        entry = by_alias.get(alias)
        if entry is None or prof.description == entry.description:
            continue
        prof.description = entry.description
        changed = True
    return changed


def _merge_missing_builtins(models: dict[str, ModelProfile]) -> bool:
    """已有 models.yaml 时补全新增的内置 preset，不覆盖用户改过的条目。"""
    changed = False
    for entry in BUILTIN_CATALOG:
        if entry.alias in models:
            continue
        models[entry.alias] = ModelProfile(
            alias=entry.alias,
            litellm=entry.litellm,
            description=entry.description,
            builtin=True,
        )
        changed = True
    return changed


def add_profile(
    store: ModelsStore,
    alias: str,
    litellm: str,
    *,
    description: str = '',
) -> None:
    name = validate_alias(alias)
    lid = litellm.strip()
    if not lid:
        raise ValueError('LiteLLM model id cannot be empty.')
    if name in store.models:
        raise ValueError(
            f'Model {name!r} already exists. Use ssj model set {name} (existing preset).'
        )
    store.models[name] = ModelProfile(
        alias=name,
        litellm=lid,
        description=description.strip(),
        builtin=False,
    )
    write_models_store(store.path, store)


def delete_profile(store: ModelsStore, alias: str, *, force_builtin: bool = False) -> None:
    name = validate_alias(alias)
    prof = store.models.get(name)
    if prof is None:
        raise ValueError(f'Unknown model {name!r}.')
    if prof.builtin and not force_builtin:
        raise ValueError(
            f'{name!r} is a built-in preset. Pass --force to remove it.'
        )
    if name == store.default:
        raise ValueError(
            f'Cannot delete default model {name!r}. Run ssj model set <other> first.'
        )
    del store.models[name]
    write_models_store(store.path, store)


def set_default(store: ModelsStore, alias: str) -> None:
    name = validate_alias(alias)
    if name not in store.models:
        raise ValueError(f'Unknown model {name!r}.')
    store.default = name
    write_models_store(store.path, store)


def update_description(store: ModelsStore, alias: str, description: str) -> None:
    name = validate_alias(alias)
    prof = store.models.get(name)
    if prof is None:
        raise ValueError(f'Unknown model {name!r}.')
    prof.description = description.strip()
    write_models_store(store.path, store)


def update_profile(
    store: ModelsStore,
    alias: str,
    *,
    litellm: str | None = None,
    description: str | None = None,
) -> ModelProfile:
    """Update fields on an existing profile (does not change default)."""
    name = validate_alias(alias)
    prof = store.models.get(name)
    if prof is None:
        raise ValueError(f'Unknown model {name!r}. Run ssj model add for a new alias.')
    if litellm is not None:
        lid = litellm.strip()
        if not lid:
            raise ValueError('LiteLLM model id cannot be empty.')
        prof.litellm = lid
    if description is not None:
        prof.description = description.strip()
    write_models_store(store.path, store)
    return prof


def matches_pattern(profile: ModelProfile, pattern: str) -> bool:
    pat = pattern.strip()
    if not pat:
        return True
    pl = pat.lower()
    for field in (profile.alias, profile.litellm, profile.description):
        fl = field.lower()
        if fnmatch.fnmatch(fl, pl) or pl in fl:
            return True
    return False
