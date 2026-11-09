"""Per-model chat reply extraction and MCQ parsing (plugin-style rules, longest prefix).

Add a model family by appending to ``REPLY_EXTRACTOR_RULES`` / ``CHOICE_PARSER_RULES``.
Each rule: ``prefix`` (lowercase litellm id) + handler callable.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

ChatResponseJson = dict[str, Any]
ExtractorFn = Callable[[ChatResponseJson], str]
ParserFn = Callable[[str], str | None]

_BRACKET_LETTER = re.compile(r'\[\s*([A-Da-d])\s*\]')
_LETTER = re.compile(r'(?:答案|answer|选项)?\s*[:：]?\s*([A-Da-d])\b')
# 是/否二分类；避免把「不是」误收成「是」
_YES_NO_STRICT = re.compile(
    r'(?:答案|answer)?\s*[:：]?\s*(不是|否|对|错|是|yes|no)\b',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReplyExtractorRule:
    prefix: str
    extract: ExtractorFn


@dataclass(frozen=True)
class ChoiceParserRule:
    prefix: str
    parse: ParserFn


def _first_message(data: ChatResponseJson) -> dict[str, Any]:
    choices = data['choices']
    msg = choices[0]['message']
    if not isinstance(msg, dict):
        raise KeyError('message must be a dict')
    return msg


def extract_content_only(data: ChatResponseJson) -> str:
    """OpenAI-compatible: ``choices[0].message.content`` only."""
    content = _first_message(data).get('content')
    if content is None:
        return ''
    return str(content).strip()


def extract_openrouter_reasoning_fallback(data: ChatResponseJson) -> str:
    """MiMo 等：content 为空时用 ``message.reasoning``（eval 需配合足够 max_tokens）。"""
    msg = _first_message(data)
    content = str(msg.get('content') or '').strip()
    if content:
        return content
    reasoning = msg.get('reasoning')
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return ''


def parse_mcq_standard(text: str) -> str | None:
    """Bracket / 答案：B / 单字母等通用 MCQ 解析。"""
    raw = (text or '').strip()
    if not raw:
        return None
    bracket = _BRACKET_LETTER.search(raw)
    if bracket:
        return bracket.group(1).upper()
    match = _LETTER.search(raw)
    if match:
        return match.group(1).upper()
    compact = re.sub(r'\s+', '', raw)
    if len(compact) == 1 and compact.upper() in 'ABCD':
        return compact.upper()
    return None


def parse_yes_no_zh(text: str) -> str | None:
    """Parse 是/否 for binary probes; returns '是' or '否'."""
    raw = (text or '').strip()
    if not raw:
        return None
    compact = re.sub(r'\s+', '', raw)
    if compact in ('是', '否'):
        return compact
    # Single char line: 是/否
    if len(compact) == 1:
        if compact == '是':
            return '是'
        if compact == '否':
            return '否'
    m = _YES_NO_STRICT.search(raw)
    if m:
        tok = m.group(1).lower()
        if tok in ('是', 'yes', '对'):
            return '是'
        if tok in ('否', 'no', '错'):
            return '否'
        if tok == '不是':
            return '否'
    # Last resort: line containing only 是/否
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) == 1:
        last = lines[0]
        if last == '是' or (last.endswith('是') and '不是' not in last):
            return '是'
        if last == '否' or last.endswith('否'):
            return '否'
    return None


def parse_one_zero(text: str) -> str | None:
    """Parse a single line 0 or 1 (jsonl gold-compatible)."""
    raw = (text or '').strip()
    if not raw:
        return None
    compact = re.sub(r'\s+', '', raw)
    if compact in ('0', '1'):
        return compact
    m = re.search(r'(?:答案|answer)?\s*[:：]?\s*([01])\b', raw)
    if m:
        return m.group(1)
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) == 1 and lines[0] in ('0', '1'):
        return lines[0]
    return None


def parse_mimo_mcq(text: str) -> str | None:
    """MiMo：先是/否，再 A–D；长 reasoning 再试末尾若干行。"""
    for parser in (parse_one_zero, parse_yes_no_zh, parse_mcq_standard):
        hit = parser(text)
        if hit:
            return hit
    tail = '\n'.join((text or '').strip().splitlines()[-8:])
    for parser in (parse_one_zero, parse_yes_no_zh, parse_mcq_standard):
        hit = parser(tail)
        if hit:
            return hit
    return None


# 前缀越长越优先（与 model_transport / provider_routing 一致）
REPLY_EXTRACTOR_RULES: tuple[ReplyExtractorRule, ...] = (
    ReplyExtractorRule('openrouter/xiaomi/mimo', extract_openrouter_reasoning_fallback),
)

CHOICE_PARSER_RULES: tuple[ChoiceParserRule, ...] = (
    ChoiceParserRule('openrouter/xiaomi/mimo', parse_mimo_mcq),
)

_DEFAULT_EXTRACTOR: ExtractorFn = extract_content_only
_DEFAULT_PARSER: ParserFn = parse_mcq_standard


def _resolve_rule(litellm_model: str, rules: tuple[Any, ...]) -> Any | None:
    lower = litellm_model.strip().lower()
    matched = None
    best_len = -1
    for rule in rules:
        prefix = rule.prefix.lower()
        if lower.startswith(prefix) and len(prefix) > best_len:
            matched = rule
            best_len = len(prefix)
    return matched


def resolve_reply_extractor(litellm_model: str) -> ExtractorFn:
    rule = _resolve_rule(litellm_model, REPLY_EXTRACTOR_RULES)
    return rule.extract if rule is not None else _DEFAULT_EXTRACTOR


def resolve_choice_parser(litellm_model: str) -> ParserFn:
    rule = _resolve_rule(litellm_model, CHOICE_PARSER_RULES)
    return rule.parse if rule is not None else _DEFAULT_PARSER


def extract_chat_reply_text(litellm_model: str, response_json: ChatResponseJson) -> str:
    """Map provider JSON → plain text for scoring."""
    try:
        return resolve_reply_extractor(litellm_model)(response_json)
    except (KeyError, IndexError, TypeError):
        return ''


def parse_mcq_choice(litellm_model: str, text: str) -> str | None:
    """Map model text → A–D letter (MiMo 路径内会先试是/否)。"""
    return resolve_choice_parser(litellm_model)(text)


def parse_probe_reply(
    item: dict[str, Any],
    litellm_model: str,
    text: str,
) -> str | None:
    """Dispatch by item['parse']: letter (default) vs yes_no vs one_zero."""
    mode = str(item.get('parse') or 'letter').strip().lower()
    if mode in ('one_zero', 'one-zero', 'binary_10'):
        return parse_one_zero(text)
    if mode in ('yes_no', 'yes-no', 'binary_zh'):
        return parse_yes_no_zh(text)
    return parse_mcq_choice(litellm_model, text)


def chat_probe_reply(
    litellm_model: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 32,
    temperature: float | None = None,
    timeout: float = 30.0,
) -> str:
    """One chat completion with model-specific reply extraction."""
    from ssj.model_ping import chat_openai_compatible_raw

    _, raw = chat_openai_compatible_raw(
        litellm_model,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    return extract_chat_reply_text(litellm_model, raw)


# 兼容旧名
parse_choice_letter = parse_mcq_standard
