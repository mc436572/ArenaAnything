"""Load ssj chat presets from YAML under chat_profiles_subdir (everything except --text)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CHAT_MAX_TOKENS = 4096
DEFAULT_CHAT_TIMEOUT = 60.0
DEFAULT_EVAL_MAX_TOKENS = 16
DEFAULT_EVAL_LIMIT = 0

_PROFILE_KEYS = frozenset(
    {
        'system_prompt',
        'system',
        'with_context',
        'timeout',
        'max_tokens',
        'limit',
    }
)


@dataclass
class ChatProfile:
    system_prompt: str | None = None
    with_context: bool = False
    timeout: float = DEFAULT_CHAT_TIMEOUT
    max_tokens: int = DEFAULT_CHAT_MAX_TOKENS
    limit: int = DEFAULT_EVAL_LIMIT


_EVAL_PROFILE_KEYS = _PROFILE_KEYS


@dataclass
class EvalRunOptions:
    system_prompt: str | None = None
    timeout: float = DEFAULT_CHAT_TIMEOUT
    max_tokens: int = DEFAULT_EVAL_MAX_TOKENS
    limit: int = DEFAULT_EVAL_LIMIT


def _normalize_profile_file_name(raw: str) -> str:
    name = raw.strip()
    if name.endswith(('.yaml', '.yml', '.json')):
        return name
    return f'{name}.yaml'


def builtin_chat_profiles_dir() -> Path:
    """Shipped presets (frozen in ssj-<ver>.tar.gz with the ssj package)."""
    return (Path(__file__).resolve().parent / 'chat-profiles').resolve()


def _candidate_profile_names(raw: str) -> list[str]:
    name = raw.strip()
    if name.endswith(('.yaml', '.yml', '.json')):
        return [name]
    return [f'{name}.yaml', f'{name}.yml', f'{name}.json']


def _find_profile_in_dir(base: Path, raw: str, candidates: list[str]) -> Path | None:
    root = base.resolve()
    for file_name in candidates:
        path = (root / file_name).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f'Profile path escapes chat-profiles directory: {raw!r}') from exc
        if path.is_file():
            return path
    return None


def resolve_chat_profile_path(profiles_dir: Path, raw: str) -> Path:
    """Instance chat-profiles override; else ssj built-in presets."""
    name = raw.strip()
    if not name:
        raise ValueError('Profile name cannot be empty')
    if name != Path(name).name:
        raise ValueError(
            f'Profile must be a file name only (e.g. example.yaml), not a path: {raw!r}'
        )
    if '..' in name or name.startswith('.'):
        raise ValueError(f'Invalid profile name: {raw!r}')

    candidates = _candidate_profile_names(name)
    found = _find_profile_in_dir(profiles_dir, name, candidates)
    if found is not None:
        return found

    builtin = builtin_chat_profiles_dir()
    found = _find_profile_in_dir(builtin, name, candidates)
    if found is not None:
        return found

    primary = _normalize_profile_file_name(name)
    raise FileNotFoundError(
        f'Chat profile not found: {primary} (in {profiles_dir.resolve()} or built-in {builtin})'
    )


def _coerce_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'true', '1', 'yes', 'on'}:
            return True
        if lowered in {'false', '0', 'no', 'off'}:
            return False
    raise ValueError(f'{field} must be a boolean, got {value!r}')


def _load_profile_data(path: Path) -> dict[str, Any]:
    with path.open(encoding='utf-8') as f:
        if path.suffix.lower() == '.json':
            loaded = json.load(f)
        else:
            loaded = yaml.safe_load(f)
    if not isinstance(loaded, dict):
        raise ValueError('Chat profile must be a YAML mapping (object)')
    return loaded


def load_chat_profile(path: Path) -> ChatProfile:
    data = _load_profile_data(path)

    unknown = set(data.keys()) - _PROFILE_KEYS - {'text'}
    if unknown:
        names = ', '.join(sorted(unknown))
        raise ValueError(f'Unknown chat profile keys: {names}')
    if 'text' in data:
        raise ValueError(
            'Chat profile must not include "text"; pass user input with --text on the command line'
        )

    system_raw = data.get('system_prompt', data.get('system'))
    system_prompt: str | None = None
    if system_raw is not None:
        system_prompt = str(system_raw).strip() or None

    with_context = False
    if 'with_context' in data:
        with_context = _coerce_bool(data['with_context'], field='with_context')

    timeout = DEFAULT_CHAT_TIMEOUT
    if 'timeout' in data:
        timeout = float(data['timeout'])
        if timeout <= 0:
            raise ValueError('timeout must be positive')

    max_tokens = DEFAULT_CHAT_MAX_TOKENS
    if 'max_tokens' in data:
        max_tokens = int(data['max_tokens'])
        if max_tokens <= 0:
            raise ValueError('max_tokens must be positive')

    limit = DEFAULT_EVAL_LIMIT
    if 'limit' in data:
        limit = int(data['limit'])
        if limit < 0:
            raise ValueError('limit must be >= 0')

    return ChatProfile(
        system_prompt=system_prompt,
        with_context=with_context,
        timeout=timeout,
        max_tokens=max_tokens,
        limit=limit,
    )


def default_eval_options() -> EvalRunOptions:
    return EvalRunOptions()


def load_eval_profile(path: Path) -> EvalRunOptions:
    """Preset for ssj eval (ignores with_context)."""
    data = _load_profile_data(path)

    if 'text' in data:
        raise ValueError(
            'Eval profile must not include "text"; choose the suite with --suite on the command line'
        )
    if 'suite' in data:
        raise ValueError(
            'Eval profile must not include "suite"; choose the test set with --suite on the command line'
        )

    unknown = set(data.keys()) - _EVAL_PROFILE_KEYS
    if unknown:
        names = ', '.join(sorted(unknown))
        raise ValueError(f'Unknown eval profile keys: {names}')

    system_raw = data.get('system_prompt', data.get('system'))
    system_prompt: str | None = None
    if system_raw is not None:
        system_prompt = str(system_raw).strip() or None

    timeout = DEFAULT_CHAT_TIMEOUT
    if 'timeout' in data:
        timeout = float(data['timeout'])
        if timeout <= 0:
            raise ValueError('timeout must be positive')

    max_tokens = DEFAULT_EVAL_MAX_TOKENS
    if 'max_tokens' in data:
        max_tokens = int(data['max_tokens'])
        if max_tokens <= 0:
            raise ValueError('max_tokens must be positive')

    limit = DEFAULT_EVAL_LIMIT
    if 'limit' in data:
        limit = int(data['limit'])
        if limit < 0:
            raise ValueError('limit must be >= 0')

    return EvalRunOptions(
        system_prompt=system_prompt,
        timeout=timeout,
        max_tokens=max_tokens,
        limit=limit,
    )


def merge_chat_options(
    profile: ChatProfile | None,
    *,
    system_prompt: str | None,
    system_prompt_set: bool,
    with_context: bool | None,
    timeout: float | None,
    max_tokens: int | None,
) -> ChatProfile:
    """CLI overrides profile when a flag was explicitly provided."""
    base = profile or ChatProfile()
    return ChatProfile(
        system_prompt=(
            (system_prompt or '').strip() or None
            if system_prompt_set
            else base.system_prompt
        ),
        with_context=with_context if with_context is not None else base.with_context,
        timeout=timeout if timeout is not None else base.timeout,
        max_tokens=max_tokens if max_tokens is not None else base.max_tokens,
    )
