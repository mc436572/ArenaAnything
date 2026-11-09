"""内置模型代号（类似 Cursor 模型列表）：初始化时写入 models.yaml，用户可在此基础上 add 自定义代号。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    alias: str
    litellm: str
    description: str


# 首次 setup / init 时 seed 进 models.yaml；用户可用 ssj model add 增加 ds1017 等
BUILTIN_CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry('ds', 'deepseek/deepseek-chat', 'DeepSeek chat (V3)'),
    CatalogEntry('kimi', 'moonshot/kimi-k3.1-pro', 'Kimi K3.1 Pro (CN platform)'),
    CatalogEntry('grok', 'xai/grok-2-1212', 'xAI Grok 2'),
    CatalogEntry(
        'jev',
        'typesafe/jev-latest',
        'JEV direct (TypeSafe SystemOne / Decisions)',
    ),
    CatalogEntry('glm', 'zai/glm-4.7', 'Zhipu GLM 4.7'),
    CatalogEntry(
        'mimo',
        'openrouter/xiaomi/mimo-v2.6-flash',
        'MiMo V2.6 Flash via OpenRouter',
    ),
)

DEFAULT_ALIAS = 'ds'

BUILTIN_ALIASES: frozenset[str] = frozenset(e.alias for e in BUILTIN_CATALOG)
