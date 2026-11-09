"""model 字符串 → 本进程根 .env 里允许/需要的密钥名（LiteLLM 风格 provider/...）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvKeySpec:
    name: str
    required: bool
    hint: str = ''


@dataclass(frozen=True)
class _ProviderRule:
    prefix: str
    keys: tuple[EnvKeySpec, ...]


# 前缀越长越优先（同 model 串只匹配一条）
_PROVIDER_RULES: tuple[_ProviderRule, ...] = (
    _ProviderRule(
        'deepseek/',
        (
            EnvKeySpec('DEEPSEEK_API_KEY', True, 'DeepSeek 控制台 API key'),
            EnvKeySpec(
                'DEEPSEEK_API_BASE',
                False,
                '默认 https://api.deepseek.com/v1，一般不必改',
            ),
        ),
    ),
    _ProviderRule(
        'openrouter/',
        (
            EnvKeySpec('OPENROUTER_API_KEY', True, 'OpenRouter 控制台 API key'),
            EnvKeySpec(
                'OPENROUTER_API_BASE',
                False,
                '默认 https://openrouter.ai/api/v1，一般不必改',
            ),
        ),
    ),
    _ProviderRule(
        'moonshot/',
        (
            EnvKeySpec(
                'MOONSHOT_API_KEY',
                True,
                'Kimi（Moonshot）开放平台 API key；model 形如 moonshot/kimi-k2-...',
            ),
            EnvKeySpec(
                'MOONSHOT_API_BASE',
                False,
                '国内 https://api.moonshot.cn/v1；海外 https://api.moonshot.ai/v1（须与 Key 区域一致）',
            ),
        ),
    ),
    _ProviderRule(
        'openai/',
        (
            EnvKeySpec('OPENAI_API_KEY', True, 'OpenAI 或兼容网关的 API key'),
            EnvKeySpec(
                'OPENAI_API_BASE',
                False,
                '自定义 API 根 URL（本机 Ollama / vLLM 的 OpenAI 兼容端点）',
            ),
        ),
    ),
    _ProviderRule(
        'anthropic/',
        (
            EnvKeySpec('ANTHROPIC_API_KEY', True, 'Anthropic API key'),
            EnvKeySpec(
                'ANTHROPIC_API_BASE',
                False,
                '默认 https://api.anthropic.com/v1，一般不必改',
            ),
        ),
    ),
    _ProviderRule(
        'gemini/',
        (
            EnvKeySpec('GEMINI_API_KEY', True, 'Google AI / Gemini API key'),
            EnvKeySpec(
                'GEMINI_API_BASE',
                False,
                '默认 Google Generative Language API v1beta 根 URL',
            ),
        ),
    ),
    _ProviderRule(
        'ollama/',
        (
            EnvKeySpec(
                'OLLAMA_API_BASE',
                False,
                'Ollama 地址，默认 http://127.0.0.1:11434',
            ),
        ),
    ),
    _ProviderRule(
        'xai/',
        (
            EnvKeySpec('XAI_API_KEY', True, 'xAI Grok API key'),
            EnvKeySpec(
                'XAI_API_BASE',
                False,
                '默认 https://api.x.ai/v1，一般不必改',
            ),
        ),
    ),
    _ProviderRule(
        'typesafe/',
        (
            EnvKeySpec(
                'TYPESAFE_API_KEY',
                True,
                'TypeSafe / JEV API key（LiteLLM: typesafe/jev-…）',
            ),
            EnvKeySpec(
                'TYPESAFE_API_BASE',
                False,
                'TypeSafe API 根 URL，一般不必改',
            ),
        ),
    ),
    _ProviderRule(
        'zai/',
        (
            EnvKeySpec('ZAI_API_KEY', True, '智谱 Z.AI GLM API key'),
            EnvKeySpec(
                'ZAI_API_BASE',
                False,
                '默认 https://api.z.ai/api/paas/v4',
            ),
        ),
    ),
    _ProviderRule(
        'xiaomi_mimo/',
        (
            EnvKeySpec(
                'XIAOMI_MIMO_API_KEY',
                True,
                'MiMo 开放平台 API key',
            ),
            EnvKeySpec(
                'XIAOMI_MIMO_API_BASE',
                False,
                '默认 https://api.xiaomimimo.com/v1',
            ),
        ),
    ),
)

# openrouter/typesafe/jev-… 曾误配为 TYPESAFE_*（直连 TypeSafe）；LiteLLM 实际读 OPENROUTER_*。
_OPENROUTER_TYPESAFE_LEGACY: tuple[tuple[str, str], ...] = (
    ('OPENROUTER_API_KEY', 'TYPESAFE_API_KEY'),
    ('OPENROUTER_API_BASE', 'TYPESAFE_API_BASE'),
)


def is_openrouter_typesafe_model(model: str) -> bool:
    return model.strip().lower().startswith('openrouter/typesafe/')


def env_value_for_model(model: str, env_name: str) -> str:
    """Effective env value for a model, including legacy aliases for openrouter/typesafe/."""
    import os

    direct = os.environ.get(env_name, '').strip()
    if direct:
        return direct
    if is_openrouter_typesafe_model(model):
        for canonical, legacy in _OPENROUTER_TYPESAFE_LEGACY:
            if env_name == canonical:
                return os.environ.get(legacy, '').strip()
    return ''


def reconcile_legacy_openrouter_typesafe_env(
    *,
    env_path: Path,
    litellm_models: tuple[str, ...],
) -> bool:
    """If .env has TYPESAFE_* but profile uses openrouter/typesafe/, copy to OPENROUTER_*."""
    import os

    from ssj.settings import set_env_key

    if not env_path.is_file():
        return False
    changed = False
    for model in litellm_models:
        if not is_openrouter_typesafe_model(model):
            continue
        for canonical, legacy in _OPENROUTER_TYPESAFE_LEGACY:
            if os.environ.get(canonical, '').strip():
                continue
            legacy_val = os.environ.get(legacy, '').strip()
            if not legacy_val:
                continue
            set_env_key(canonical, legacy_val, model=model)
            os.environ[canonical] = legacy_val
            changed = True
    return changed


_UNKNOWN_HINT = (
    '未识别的 provider 前缀。请使用 deepseek/、openrouter/、moonshot/（Kimi）、'
    'openai/、anthropic/、gemini/、xai/、openrouter/（含 openrouter/typesafe/jev-…）、'
    'typesafe/（直连 TypeSafe API）、zai/（GLM）、'
    'xiaomi_mimo/、ollama/ 等形式，'
    '或参考 https://docs.litellm.ai/docs/providers'
)


def resolve_secrets_for_model(model: str) -> tuple[EnvKeySpec, ...]:
    normalized = model.strip().lower()
    matched: _ProviderRule | None = None
    for rule in _PROVIDER_RULES:
        if normalized.startswith(rule.prefix):
            if matched is None or len(rule.prefix) > len(matched.prefix):
                matched = rule
    if matched is not None:
        return matched.keys
    return ()


def known_model_prefixes() -> tuple[str, ...]:
    return tuple(rule.prefix for rule in _PROVIDER_RULES)


def all_registered_secret_names() -> frozenset[str]:
    names: set[str] = set()
    for rule in _PROVIDER_RULES:
        for spec in rule.keys:
            names.add(spec.name)
    return frozenset(names)


def allowed_key_names_for_model(model: str) -> frozenset[str]:
    return frozenset(spec.name for spec in resolve_secrets_for_model(model))


def validate_key_for_model(model: str, key: str) -> None:
    allowed = allowed_key_names_for_model(model)
    if not allowed:
        raise ValueError(
            f'Model {model!r} has no registered secrets. {_UNKNOWN_HINT}'
        )
    if key not in allowed:
        listed = ', '.join(sorted(allowed))
        raise ValueError(
            f'{key!r} is not used for model {model!r}. Allowed: {listed}'
        )


def secret_status(model: str) -> list[tuple[EnvKeySpec, str]]:
    """返回 (spec, display_value) 供 config show。"""
    import os

    from ssj.settings import mask_edges

    specs = resolve_secrets_for_model(model)
    if not specs:
        return []
    rows: list[tuple[EnvKeySpec, str]] = []
    for spec in specs:
        if env_value_for_model(model, spec.name):
            display = mask_edges(env_value_for_model(model, spec.name))
        elif spec.required:
            display = '[bold red](required, not set)[/bold red]'
        else:
            display = '(optional, not set)'
        rows.append((spec, display))
    return rows


def write_env_example(env_example_path: Path, model: str) -> None:
    specs = resolve_secrets_for_model(model)
    lines = [
        '# Generated for ssj — keys below match the default model profile',
        f'# litellm: {model}',
        '# Copy to .env and run: ssj model set <alias>',
        '',
    ]
    if not specs:
        lines.append(f'# {_UNKNOWN_HINT}')
        lines.append('')
    for spec in specs:
        tag = 'required' if spec.required else 'optional'
        if spec.hint:
            lines.append(f'# [{tag}] {spec.hint}')
        else:
            lines.append(f'# [{tag}]')
        lines.append(f'{spec.name}=')
        lines.append('')
    env_example_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
