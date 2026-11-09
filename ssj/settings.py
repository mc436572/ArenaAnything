"""SSaiyan / ssj 配置.

进程根在启动时定死：手工运行时根是当时的工作目录；若设置了 SSJ_ROOT，
它必须与工作目录相同。配置、密钥、traces 只相对这个根。
不读 ~/.ssj，不读 SSJ_DATA_DIR，不继承父进程的模型覆盖和 API key。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv, set_key

from ssj.model_catalog import DEFAULT_ALIAS
from ssj.model_secrets import (
    all_registered_secret_names,
    reconcile_legacy_openrouter_typesafe_env,
    write_env_example,
)
from ssj.models_store import ensure_models_file, load_models_store

PACKAGE_VERSION = '0.1.0'

DEFAULT_MODEL = 'deepseek/deepseek-chat'
DEFAULT_PROFILE = 'dev'
DEFAULT_MAX_STEPS = 20
DEFAULT_SANDBOX = 'local'
DEFAULT_CHAT_PROFILES_SUBDIR = 'chat-profiles'

# 只从本进程根的 .env 加载。父进程里已有的值先丢掉，避免串到别的 Agent。
_REGISTERED_SECRETS = all_registered_secret_names()
_IGNORED_INHERITED_KEYS = ('SSJ_DATA_DIR', 'SSJ_MODEL', *_REGISTERED_SECRETS)


class RootMismatchError(RuntimeError):
    """SSJ_ROOT、工作目录、config.yaml 所在目录不是同一个路径。"""


def resolve_root() -> Path:
    """解析并冻结本进程的根目录。"""
    cwd = Path.cwd().resolve()
    raw = os.environ.get('SSJ_ROOT', '').strip()
    if not raw:
        return cwd
    root = Path(raw).expanduser().resolve()
    if root != cwd:
        raise RootMismatchError(
            f'SSJ_ROOT ({root}) and working directory ({cwd}) differ. '
            'Refusing to start.'
        )
    return root


@dataclass
class Settings:
    data_dir: Path
    config_path: Path
    env_path: Path
    models_path: Path
    profile: str = DEFAULT_PROFILE
    model_alias: str = DEFAULT_ALIAS
    model: str = DEFAULT_MODEL
    max_steps: int = DEFAULT_MAX_STEPS
    sandbox: str = DEFAULT_SANDBOX
    trace_subdir: str = 'traces'
    chat_profiles_subdir: str = DEFAULT_CHAT_PROFILES_SUBDIR

    @property
    def trace_dir(self) -> Path:
        return self.data_dir / self.trace_subdir

    @property
    def chat_profiles_dir(self) -> Path:
        return self.data_dir / self.chat_profiles_subdir

    @property
    def session_dir(self) -> Path:
        return self.data_dir / 'session'


def _default_config_dict() -> dict:
    return {
        'profile': DEFAULT_PROFILE,
        'max_steps': DEFAULT_MAX_STEPS,
        'sandbox': DEFAULT_SANDBOX,
        'trace_subdir': 'traces',
        'chat_profiles_subdir': DEFAULT_CHAT_PROFILES_SUBDIR,
    }


def write_default_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        return
    with config_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(_default_config_dict(), f, sort_keys=False, allow_unicode=True)


CONFIG_YAML_KEYS = frozenset(
    {'profile', 'max_steps', 'sandbox', 'trace_subdir', 'chat_profiles_subdir'}
)


def update_config_field(config_path: Path, key: str, value: str) -> None:
    """Update one environment field in config.yaml."""
    name = key.strip()
    if name not in CONFIG_YAML_KEYS:
        allowed = ', '.join(sorted(CONFIG_YAML_KEYS))
        raise ValueError(f'Unknown config key {name!r}. Allowed: {allowed}')
    data: dict = {}
    if config_path.is_file():
        with config_path.open(encoding='utf-8') as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                data = dict(loaded)
    if name == 'max_steps':
        data[name] = int(value.strip())
    else:
        data[name] = value.strip()
    with config_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def write_default_env_example(env_example_path: Path, *, model: str = DEFAULT_MODEL) -> None:
    write_env_example(env_example_path, model)


def update_config_model(config_path: Path, model: str) -> None:
    """Legacy: 仅当旧脚本仍写 config model 时保留；新流程用 models.yaml。"""
    data: dict = {}
    if config_path.is_file():
        with config_path.open(encoding='utf-8') as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                data = loaded
    data['model'] = model.strip()
    with config_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def _assert_config_inside_root(root: Path) -> None:
    config_path = root / 'config.yaml'
    if not config_path.is_file():
        return
    config_dir = config_path.resolve().parent
    if config_dir != root:
        raise RootMismatchError(
            f'config.yaml is in {config_dir}, process root is {root}. '
            'Refusing to start.'
        )


def _drop_inherited_env() -> None:
    for key in _IGNORED_INHERITED_KEYS:
        os.environ.pop(key, None)


def init_data_dir() -> Settings:
    """在本进程根下创建 config.yaml、.env.example、traces/、session/。"""
    root = resolve_root()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / 'config.yaml'
    write_default_config(config_path)
    ensure_models_file(root)
    write_default_env_example(root / '.env.example', model=DEFAULT_MODEL)
    (root / 'traces').mkdir(parents=True, exist_ok=True)
    (root / 'session').mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    settings.chat_profiles_dir.mkdir(parents=True, exist_ok=True)
    return settings


def load_settings() -> Settings:
    root = resolve_root()
    _assert_config_inside_root(root)
    config_path = root / 'config.yaml'
    env_path = root / '.env'

    _drop_inherited_env()
    if env_path.is_file():
        load_dotenv(env_path, override=True)

    data: dict = {}
    if config_path.is_file():
        with config_path.open(encoding='utf-8') as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                data = loaded

    legacy_model = str(data.get('model') or '').strip() or None
    profile = data.get('profile') or DEFAULT_PROFILE
    max_steps = int(data.get('max_steps') or DEFAULT_MAX_STEPS)
    sandbox = str(data.get('sandbox') or DEFAULT_SANDBOX)
    trace_subdir = str(data.get('trace_subdir') or 'traces')
    chat_profiles_subdir = str(
        data.get('chat_profiles_subdir') or DEFAULT_CHAT_PROFILES_SUBDIR
    )

    store = load_models_store(root, legacy_config_model=legacy_model)
    reconcile_legacy_openrouter_typesafe_env(
        env_path=env_path,
        litellm_models=tuple(p.litellm for p in store.models.values()),
    )
    model_alias = store.default
    model = store.default_litellm()

    return Settings(
        data_dir=root,
        config_path=config_path,
        env_path=env_path,
        models_path=store.path,
        profile=str(profile),
        model_alias=str(model_alias),
        model=str(model),
        max_steps=max_steps,
        sandbox=sandbox,
        trace_subdir=trace_subdir,
        chat_profiles_subdir=chat_profiles_subdir,
    )


def chat_profiles_dir_for_root(root: Path) -> Path:
    """Resolve chat profile directory from config.yaml under root (no SSJ_ROOT check)."""
    subdir = DEFAULT_CHAT_PROFILES_SUBDIR
    config_path = root / 'config.yaml'
    if config_path.is_file():
        with config_path.open(encoding='utf-8') as f:
            loaded = yaml.safe_load(f)
        if isinstance(loaded, dict):
            raw = str(loaded.get('chat_profiles_subdir') or '').strip()
            if raw:
                subdir = raw
    return (root / subdir).resolve()


_ENV_KEY_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def set_env_key(name: str, value: str, *, model: str | None = None) -> Path:
    """把密钥写入本进程根的 .env。调用方不得把 value 打到终端或写进 argv。"""
    if not _ENV_KEY_NAME.fullmatch(name):
        raise ValueError(f'Invalid env key name: {name!r}')
    if not value.strip():
        raise ValueError('Empty secret, not written.')
    if model is not None:
        from ssj.model_secrets import validate_key_for_model

        validate_key_for_model(model, name)
    root = resolve_root()
    env_path = root / '.env'
    set_key(str(env_path), name, value.strip())
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass
    return env_path


def mask_edges(value: str, edge: int = 5) -> str:
    """两端各留 edge 个字符，中间用 *。短于等于 2*edge 时整段打码，避免露全。"""
    if len(value) <= edge * 2:
        return '*' * len(value)
    return value[:edge] + ('*' * (len(value) - edge * 2)) + value[-edge:]


def mask_secret(name: str) -> str:
    val = os.environ.get(name, '')
    if not val:
        return '(not set)'
    return mask_edges(val)
