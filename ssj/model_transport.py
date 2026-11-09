"""LiteLLM model id → call transport (chat vs TypeSafe Decisions). Longest prefix wins.

JEV 有三层名字，不要混用：

| 层 | 存哪儿 | 示例 | 说明 |
|----|--------|------|------|
| profile alias | models.yaml | `jev` | `ssj model set jev` 配置的对象 |
| LiteLLM id | models.yaml `litellm` | **`typesafe/jev-latest`**（直连推荐） | 与 LiteLLM / ssj catalog 一致 |
| HTTP body `model` | 自动转换，勿手填 | **`jev-latest`**（直连 SystemOne） | 官网 POST …/v1/systemone 用的字段 |

OpenRouter 网关时：`litellm` 写 **`openrouter/typesafe/jev-latest`**（或带版本 tag），
wire **`typesafe/jev-latest`**（去掉 `openrouter/` 前缀，保留 `typesafe/…`）。

直连时勿把 `typesafe/jev-1.13` 当成 API 模型名：provider 剥前缀后会变成 `jev-1.13`，
SystemOne 不认；见 ``TYPESAFE_SYSTEMONE_WIRE_ALIASES`` 映射到 ``jev-latest``。
推荐始终配置 **`typesafe/jev-latest`**。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from ssj.model_ping import PingError, ping_error_from_http_status
from ssj.model_secrets import env_value_for_model
from ssj.provider_routing import match_provider, resolved_api_root

TransportKind = Literal['chat_openai', 'decisions']

ApiRootKind = Literal['openrouter', 'typesafe']

_PROBE_CHOICE_KEY = 'answer'
JEV_CHAT_BINARY_KEY = 'binary_judgment'

# SystemOne / OpenRouter Decisions 题面形状（与官网 Playground 一致，非 chat messages）
QuestionDict = dict[str, Any]


def build_systemone_state(
    *segments: str,
    system_prompt: str | None = None,
) -> list[str]:
    """``state``: 有序文本片段（可含 system + 用户题面）。"""
    state: list[str] = []
    sys_text = (system_prompt or '').strip()
    if sys_text:
        state.append(sys_text)
    for seg in segments:
        text = str(seg).strip()
        if text:
            state.append(text)
    return state if state else ['']


def build_noul_question(
    name: str,
    *,
    instructions: str,
    true_label: str,
    false_label: str,
) -> QuestionDict:
    return {
        name: {
            'type': 'noul',
            'instructions': instructions,
            'criteria': {
                'true': true_label,
                'false': false_label,
            },
        },
    }


def build_choice_question(
    name: str,
    *,
    instructions: str,
    criteria: dict[str, str],
) -> QuestionDict:
    """``criteria``: 选项 key → 说明（MCQ 时 key 为 A/B/C/D）。"""
    normalized = {str(k).strip(): str(v) for k, v in criteria.items() if str(k).strip()}
    if len(normalized) < 2:
        raise PingError('choice question needs at least two criteria options')
    return {
        name: {
            'type': 'choice',
            'instructions': instructions,
            'criteria': normalized,
        },
    }


def assemble_systemone_body(
    litellm_model: str,
    *,
    state: list[Any],
    questions: QuestionDict,
) -> dict[str, Any]:
    """完整 Decisions POST JSON（model + state + questions）。"""
    resolved = resolve_transport(litellm_model)
    if resolved.kind != 'decisions' or resolved.rule is None:
        raise PingError(f'Model {litellm_model!r} is not a decisions transport')
    rule = resolved.rule
    return {
        'model': decisions_payload_model(litellm_model, rule),
        'state': state,
        'questions': questions,
    }


def parse_choice_answer(
    data: dict[str, Any],
    question_name: str,
    *,
    allowed_keys: frozenset[str] | None = None,
) -> str:
    answers = data.get('answers')
    if not isinstance(answers, dict):
        return ''
    block = answers.get(question_name)
    if not isinstance(block, dict):
        return ''
    choice = block.get('choice')
    if choice is None:
        return ''
    letter = str(choice).strip().upper()
    if allowed_keys and letter in allowed_keys:
        return letter
    raw = str(choice).strip()
    if allowed_keys:
        for key in allowed_keys:
            if raw == key or raw.upper() == key.upper():
                return key.upper() if len(key) == 1 else key
    return raw


@dataclass(frozen=True)
class TransportRule:
    prefix: str
    kind: TransportKind
    decisions_path: str
    api_root_kind: ApiRootKind


# 前缀越长越优先（与 provider_routing / model_secrets 一致）
TRANSPORT_RULES: tuple[TransportRule, ...] = (
    TransportRule(
        'openrouter/typesafe/jev',
        'decisions',
        '/alpha/decisions',
        'openrouter',
    ),
    TransportRule(
        'typesafe/jev',
        'decisions',
        '/v1/systemone',
        'typesafe',
    ),
)

_DEFAULT_KIND: TransportKind = 'chat_openai'


@dataclass(frozen=True)
class ResolvedTransport:
    kind: TransportKind
    rule: TransportRule | None


def resolve_transport(litellm_model: str) -> ResolvedTransport:
    lower = litellm_model.strip().lower()
    matched: TransportRule | None = None
    for rule in TRANSPORT_RULES:
        if lower.startswith(rule.prefix):
            if matched is None or len(rule.prefix) > len(matched.prefix):
                matched = rule
    if matched is None:
        return ResolvedTransport(_DEFAULT_KIND, None)
    return ResolvedTransport(matched.kind, matched)


def _api_model_id(litellm_model: str) -> str:
    matched = match_provider(litellm_model)
    if matched is not None:
        _, model_id = matched
        return model_id
    parts = litellm_model.strip().split('/', 1)
    return parts[-1]


# catalog / 文档推荐的 JEV LiteLLM id（models.yaml & BUILTIN_CATALOG）
JEV_LITELLM_DIRECT = 'typesafe/jev-latest'
JEV_LITELLM_OPENROUTER = 'openrouter/typesafe/jev-latest'

# SystemOne 直连：LiteLLM 剥前缀后的 suffix → 官网 body.model（Playground 默认 jev-latest）
TYPESAFE_SYSTEMONE_WIRE_ALIASES: dict[str, str] = {
    'jev-1.13': 'jev-latest',
    'jev-1.13.0': 'jev-latest',
    'jev-1.14': 'jev-latest',
    'jev-1.14.0': 'jev-latest',
}


def _typesafe_systemone_wire_model(litellm_suffix: str) -> str:
    """``typesafe/<suffix>`` profile → SystemOne ``model`` field."""
    return TYPESAFE_SYSTEMONE_WIRE_ALIASES.get(litellm_suffix, litellm_suffix)


def _openrouter_decisions_wire_model(litellm_model: str) -> str:
    """``openrouter/typesafe/…`` → OpenRouter body.model（保留 typesafe/ 前缀）。"""
    stripped = litellm_model.strip()
    prefix = 'openrouter/'
    if stripped.lower().startswith(prefix):
        return stripped[len(prefix) :]
    return _api_model_id(litellm_model)


def decisions_payload_model(litellm_model: str, rule: TransportRule) -> str:
    """Map models.yaml ``litellm`` to Decisions HTTP body ``model``."""
    if rule.api_root_kind == 'openrouter':
        return _openrouter_decisions_wire_model(litellm_model)
    return _typesafe_systemone_wire_model(_api_model_id(litellm_model))


def _openrouter_decisions_root(litellm_model: str) -> str:
    root = (resolved_api_root(litellm_model) or 'https://openrouter.ai/api/v1').rstrip('/')
    if root.endswith('/chat/completions'):
        root = root[: -len('/chat/completions')]
    if root.endswith('/v1'):
        root = root[: -len('/v1')]
    return root.rstrip('/')


def _typesafe_decisions_root(litellm_model: str) -> str:
    return (resolved_api_root(litellm_model) or 'https://api.typesafe.ai').rstrip('/')


def decisions_url(litellm_model: str, rule: TransportRule) -> str:
    if rule.api_root_kind == 'openrouter':
        return f'{_openrouter_decisions_root(litellm_model)}{rule.decisions_path}'
    return f'{_typesafe_decisions_root(litellm_model)}{rule.decisions_path}'


def _decisions_api_key(litellm_model: str, rule: TransportRule) -> str:
    if rule.api_root_kind == 'openrouter':
        key = env_value_for_model(litellm_model, 'OPENROUTER_API_KEY')
        if key:
            return key
        raise PingError('Missing OPENROUTER_API_KEY')
    key = env_value_for_model(litellm_model, 'TYPESAFE_API_KEY')
    if key:
        return key
    raise PingError('Missing TYPESAFE_API_KEY')


def _decisions_headers(litellm_model: str, api_key: str, rule: TransportRule) -> dict[str, str]:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    if rule.api_root_kind == 'openrouter':
        headers.setdefault('HTTP-Referer', 'https://github.com/mc436572/ArenaAnything')
        headers.setdefault('X-Title', 'ssj')
    return headers


def post_decisions_raw(
    litellm_model: str,
    *,
    state: list[Any],
    questions: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    resolved = resolve_transport(litellm_model)
    if resolved.kind != 'decisions' or resolved.rule is None:
        raise PingError(f'Model {litellm_model!r} is not a decisions transport')
    rule = resolved.rule
    url = decisions_url(litellm_model, rule)
    api_key = _decisions_api_key(litellm_model, rule)
    payload = assemble_systemone_body(litellm_model, state=state, questions=questions)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers=_decisions_headers(litellm_model, api_key, rule),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise PingError(f'Request timed out after {timeout}s') from exc
    except httpx.HTTPStatusError as exc:
        raise ping_error_from_http_status(exc) from exc
    except httpx.HTTPError as exc:
        raise PingError(str(exc)) from exc
    if not isinstance(data, dict):
        raise PingError(f'Unexpected decisions response: {data!r}')
    return data


def _format_answer_summary(answers: dict[str, Any], question_key: str) -> str:
    block = answers.get(question_key)
    if not isinstance(block, dict):
        raise PingError(f'Missing answers[{question_key!r}] in {answers!r}')
    if 'noul' in block:
        return f'noul={float(block["noul"]):.4f}'
    if 'choice' in block:
        choice = block.get('choice')
        probs = block.get('probabilities')
        if isinstance(probs, dict) and choice in probs:
            return f'choice={choice} p={float(probs[choice]):.4f}'
        return f'choice={choice}'
    if 'score' in block:
        return f'score={block.get("score")}'
    raise PingError(f'Unrecognized answer shape: {block!r}')


def format_jev_binary_answer(data: dict[str, Any], question_key: str = JEV_CHAT_BINARY_KEY) -> str:
    """Map Decisions noul/choice to 是/否 for CLI display."""
    answers = data.get('answers')
    if not isinstance(answers, dict):
        raise PingError(f'No answers in response: {data!r}')
    block = answers.get(question_key)
    if not isinstance(block, dict):
        raise PingError(f'Missing answers[{question_key!r}] in {answers!r}')
    if 'choice' in block:
        raw = str(block.get('choice') or '').strip().lower()
        if raw in {'true', 'yes', '是'}:
            return '是'
        if raw in {'false', 'no', '否'}:
            return '否'
        raise PingError(f'Unexpected binary choice: {block!r}')
    if 'noul' in block:
        score = float(block['noul'])
        label = '是' if score >= 0.5 else '否'
        return f'{label}（noul={score:.4f}）'
    raise PingError(f'Unrecognized binary answer shape: {block!r}')


def jev_binary_decision_from_text(
    litellm_model: str,
    user_text: str,
    *,
    system_prompt: str | None = None,
    timeout: float = 60.0,
) -> tuple[str, dict[str, Any]]:
    """Wrap free-form user text as SystemOne state + fixed noul yes/no question."""
    text = str(user_text or '').strip()
    if not text:
        raise PingError('Question text is empty')
    state = build_systemone_state(text, system_prompt=system_prompt)
    questions = build_noul_question(
        JEV_CHAT_BINARY_KEY,
        instructions=(
            '根据 state 中的陈述或问题，判断其答案是否应为「是」。'
            '仅做二元判断，不要展开解释。'
        ),
        true_label='是',
        false_label='否',
    )
    data = post_decisions_raw(
        litellm_model,
        state=state,
        questions=questions,
        timeout=timeout,
    )
    if not isinstance(data, dict):
        raise PingError(f'Unexpected decisions response: {data!r}')
    display = format_jev_binary_answer(data, JEV_CHAT_BINARY_KEY)
    return display, data


def ping_decisions(litellm_model: str, *, timeout: float = 30.0) -> str:
    data = post_decisions_raw(
        litellm_model,
        state=build_systemone_state('ssj connectivity ping: reply with a confidence score.'),
        questions=build_noul_question(
            'ping_ok',
            instructions='Is this message a simple connectivity or ping check?',
            true_label='It is a ping or connectivity test',
            false_label='It is something else',
        ),
        timeout=timeout,
    )
    answers = data.get('answers')
    if not isinstance(answers, dict):
        raise PingError(f'No answers in response: {data!r}')
    return _format_answer_summary(answers, 'ping_ok')


def probe_item_via_decisions(
    litellm_model: str,
    item: dict[str, Any],
    *,
    system_prompt: str | None = None,
    timeout: float = 60.0,
) -> str:
    prompt = str(item.get('prompt') or '')
    choices = item.get('choices')
    if not isinstance(choices, dict) or not choices:
        raise PingError('Decisions eval requires probe items with a choices dict')
    criteria = {str(k).strip().upper(): str(v) for k, v in choices.items() if k}
    data = post_decisions_raw(
        litellm_model,
        state=build_systemone_state(prompt, system_prompt=system_prompt),
        questions=build_choice_question(
            _PROBE_CHOICE_KEY,
            instructions=(
                'Which option letter (A, B, C, or D) is the single best answer '
                'to the question in the state?'
            ),
            criteria=criteria,
        ),
        timeout=timeout,
    )
    return parse_choice_answer(
        data,
        _PROBE_CHOICE_KEY,
        allowed_keys=frozenset(criteria.keys()),
    )
