"""Provider prefix → default API root and .env key names (OpenAI-compatible chat)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderRoute:
    prefix: str
    default_api_root: str
    api_key_env: str
    api_base_env: str | None = None


PROVIDER_ROUTES: tuple[ProviderRoute, ...] = (
    ProviderRoute(
        'xiaomi_mimo/',
        'https://api.xiaomimimo.com/v1',
        'XIAOMI_MIMO_API_KEY',
        'XIAOMI_MIMO_API_BASE',
    ),
    ProviderRoute('openrouter/', 'https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY', 'OPENROUTER_API_BASE'),
    ProviderRoute('deepseek/', 'https://api.deepseek.com/v1', 'DEEPSEEK_API_KEY', 'DEEPSEEK_API_BASE'),
    ProviderRoute('moonshot/', 'https://api.moonshot.cn/v1', 'MOONSHOT_API_KEY', 'MOONSHOT_API_BASE'),
    ProviderRoute(
        'anthropic/',
        'https://api.anthropic.com/v1',
        'ANTHROPIC_API_KEY',
        'ANTHROPIC_API_BASE',
    ),
    ProviderRoute(
        'gemini/',
        'https://generativelanguage.googleapis.com/v1beta',
        'GEMINI_API_KEY',
        'GEMINI_API_BASE',
    ),
    ProviderRoute('openai/', 'https://api.openai.com/v1', 'OPENAI_API_KEY', 'OPENAI_API_BASE'),
    ProviderRoute('xai/', 'https://api.x.ai/v1', 'XAI_API_KEY', 'XAI_API_BASE'),
    ProviderRoute('zai/', 'https://api.z.ai/api/paas/v4', 'ZAI_API_KEY', 'ZAI_API_BASE'),
    ProviderRoute(
        'typesafe/',
        'https://api.typesafe.ai',
        'TYPESAFE_API_KEY',
        'TYPESAFE_API_BASE',
    ),
    ProviderRoute('ollama/', 'http://127.0.0.1:11434/v1', 'OLLAMA_API_KEY', 'OLLAMA_API_BASE'),
)


def match_provider(model_id: str) -> tuple[ProviderRoute, str] | None:
    normalized = model_id.strip()
    lower = normalized.lower()
    matched: ProviderRoute | None = None
    for route in PROVIDER_ROUTES:
        if lower.startswith(route.prefix):
            if matched is None or len(route.prefix) > len(matched.prefix):
                matched = route
    if matched is None:
        return None
    api_model = normalized[len(matched.prefix) :]
    if not api_model:
        return None
    return matched, api_model


def resolved_api_root(model_id: str) -> str | None:
    matched = match_provider(model_id)
    if matched is None:
        return None
    route, _ = matched
    if route.api_base_env:
        override = os.environ.get(route.api_base_env, '').strip()
        if override:
            return override.rstrip('/')
    return route.default_api_root.rstrip('/')
