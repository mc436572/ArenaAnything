"""Fast model ping via OpenAI-compatible HTTP (no litellm import on the hot path)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from ssj.provider_routing import ProviderRoute, match_provider, resolved_api_root

_PING_USER = 'Reply with exactly: pong'


class PingError(RuntimeError):
    pass


class PingUnsupported(PingError):
    pass


def ping_error_from_http_status(exc: httpx.HTTPStatusError, *, body_limit: int = 800) -> PingError:
    body = exc.response.text[:body_limit]
    code = exc.response.status_code
    lower = body.lower()
    hint = ''
    if code == 403 and ('region' in lower or 'geo restriction' in lower):
        hint = (
            ' — OpenRouter 地区限制：当前 IP 不可用该模型。'
            '可换 VPN/代理，或 `ssj model set jev` 改为 typesafe/jev-* 直连 + TYPESAFE_API_KEY。'
        )
    return PingError(f'HTTP {code}: {body}{hint}')


def _chat_completions_url(api_root: str) -> str:
    root = api_root.rstrip('/')
    if root.endswith('/chat/completions'):
        return root
    if root.endswith('/v1') or root.endswith('/beta'):
        return f'{root}/chat/completions'
    return f'{root}/v1/chat/completions'


def _extract_message(litellm_model: str, data: dict[str, Any]) -> str:
    from ssj.model_reply import extract_chat_reply_text

    try:
        return extract_chat_reply_text(litellm_model, data)
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise PingError(f'Unexpected API response shape: {data!r}') from exc


def chat_openai_compatible_raw(
    litellm_model: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 32,
    temperature: float | None = None,
    timeout: float = 30.0,
) -> tuple[str, dict[str, Any]]:
    """One completion; returns (assistant text, parsed JSON body)."""
    matched = match_provider(litellm_model)
    if matched is None:
        raise PingUnsupported(f'No fast ping handler for {litellm_model!r}')

    rule, model_id = matched
    route: ProviderRoute = rule
    api_key = os.environ.get(route.api_key_env, '').strip()
    if not api_key and route.prefix != 'ollama/':
        raise PingError(f'Missing env {route.api_key_env}')

    api_root = resolved_api_root(litellm_model) or route.default_api_root

    url = _chat_completions_url(api_root)
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    if route.prefix == 'openrouter/':
        headers.setdefault('HTTP-Referer', 'https://github.com/mc436572/ArenaAnything')
        headers.setdefault('X-Title', 'ssj')

    from ssj.model_chat_params import effective_chat_temperature

    temperature = effective_chat_temperature(litellm_model, temperature)

    payload: dict[str, Any] = {
        'model': model_id,
        'messages': messages,
        'max_tokens': max_tokens,
    }
    if temperature is not None:
        payload['temperature'] = temperature

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise PingError(f'Request timed out after {timeout}s') from exc
    except httpx.HTTPStatusError as exc:
        raise ping_error_from_http_status(exc) from exc
    except httpx.HTTPError as exc:
        raise PingError(str(exc)) from exc

    return _extract_message(litellm_model, data), data


def chat_openai_compatible(
    litellm_model: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 32,
    temperature: float | None = None,
    timeout: float = 30.0,
) -> str:
    """One OpenAI-compatible chat completion. Returns assistant text."""
    text, _ = chat_openai_compatible_raw(
        litellm_model,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    return text


def ping_openai_compatible(
    litellm_model: str,
    *,
    timeout: float = 30.0,
) -> str:
    return chat_openai_compatible(
        litellm_model,
        [{'role': 'user', 'content': _PING_USER}],
        max_tokens=32,
        timeout=timeout,
    )


def ping_model(litellm_model: str, *, timeout: float = 30.0) -> str:
    """Return model reply text; prefers httpx, falls back to litellm if needed."""
    from ssj.model_transport import ping_decisions, resolve_transport

    if resolve_transport(litellm_model).kind == 'decisions':
        return ping_decisions(litellm_model, timeout=timeout)
    try:
        return ping_openai_compatible(litellm_model, timeout=timeout)
    except PingUnsupported:
        return _ping_via_litellm(litellm_model, timeout=timeout)


def _ping_via_litellm(litellm_model: str, *, timeout: float) -> str:
    try:
        import litellm
    except ImportError as exc:
        raise PingError('litellm is not installed; pip install -e .') from exc

    litellm.suppress_debug_info = True
    try:
        response = litellm.completion(
            model=litellm_model,
            messages=[{'role': 'user', 'content': _PING_USER}],
            max_tokens=32,
            timeout=timeout,
            request_timeout=timeout,
        )
    except Exception as exc:
        raise PingError(str(exc)) from exc

    try:
        return (response.choices[0].message.content or '').strip()
    except (AttributeError, IndexError, TypeError):
        return str(response)
