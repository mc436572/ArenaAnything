"""ssj chat — single-turn or global-context chat with session + traces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

from cli.console import CONSOLE
from ssj.model_ping import PingError, chat_openai_compatible_raw
from ssj.model_reply import extract_chat_reply_text
from ssj.model_transport import jev_binary_decision_from_text, resolve_transport
from ssj.session_store import (
    append_turn,
    build_api_messages,
    load_history_messages,
    new_ephemeral_session_path,
    resolve_global_session_path,
)
from ssj.chat_profile import (
    DEFAULT_CHAT_MAX_TOKENS,
    DEFAULT_CHAT_TIMEOUT,
    load_chat_profile,
    merge_chat_options,
    resolve_chat_profile_path,
)
from ssj.settings import Settings


def _write_trace(
    trace_dir: Path,
    *,
    model: str,
    messages: list[dict[str, str]],
    response_data: dict,
) -> Path:
    trace_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    name = f'chat-{stamp}.json'
    path = trace_dir / name
    payload = {
        'model': model,
        'request_messages': messages,
        'response': response_data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def run_chat(
    settings: Settings,
    *,
    text: str,
    with_context: bool,
    system_prompt: str | None,
    timeout: float,
    max_tokens: int,
) -> None:
    user_text = text.strip()
    if not user_text:
        CONSOLE.print('[bold red]--text cannot be empty.[/bold red]')
        raise SystemExit(1)

    system = (system_prompt or '').strip() or None
    model = settings.model

    if resolve_transport(model).kind == 'decisions':
        run_jev_binary_chat(
            settings,
            user_text=user_text,
            system_prompt=system,
            timeout=timeout,
            with_context=with_context,
        )
        return

    if with_context:
        session_path = resolve_global_session_path(settings.data_dir)
    else:
        session_path = new_ephemeral_session_path(settings.data_dir)

    history = load_history_messages(session_path) if with_context else []
    messages = build_api_messages(history, user_text, system_prompt=system)

    try:
        _, raw = chat_openai_compatible_raw(
            model,
            messages,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        assistant_text = extract_chat_reply_text(model, raw)
    except PingError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc

    trace_path = _write_trace(
        settings.trace_dir,
        model=model,
        messages=messages,
        response_data=raw,
    )
    trace_ref = trace_path.relative_to(settings.data_dir).as_posix()

    append_turn(
        session_path,
        user_text=user_text,
        assistant_text=assistant_text,
        trace_ref=trace_ref,
        system_prompt=system,
        model=model,
    )

    CONSOLE.print(assistant_text)


def run_jev_binary_chat(
    settings: Settings,
    *,
    user_text: str,
    system_prompt: str | None,
    timeout: float,
    with_context: bool,
) -> None:
    """JEV: --text is the question/statement; response is forced 是/否 (SystemOne noul)."""
    model = settings.model
    CONSOLE.print(
        '[dim]JEV 二元问答：--text 为待判断内容，无需也不接受用户答案；'
        '非 OpenAI chat。[/dim]'
    )
    if with_context:
        CONSOLE.print(
            '[dim yellow]--with-context 对 JEV 无效（Decisions 不使用 chat session）。[/dim yellow]'
        )

    try:
        assistant_text, raw = jev_binary_decision_from_text(
            model,
            user_text,
            system_prompt=system_prompt,
            timeout=timeout,
        )
    except PingError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc

    trace_path = _write_trace(
        settings.trace_dir,
        model=model,
        messages=[{'role': 'user', 'content': user_text}],
        response_data=raw,
    )
    trace_ref = trace_path.relative_to(settings.data_dir).as_posix()
    session_path = new_ephemeral_session_path(settings.data_dir)
    append_turn(
        session_path,
        user_text=user_text,
        assistant_text=assistant_text,
        trace_ref=trace_ref,
        system_prompt=system_prompt,
        model=model,
    )
    CONSOLE.print(assistant_text)


@click.command(
    'chat',
    context_settings={'help_option_names': ['-h', '--help']},
)
@click.option(
    '--text',
    required=True,
    help='Chat 模型：本回合用户消息。JEV 模型：待二元判断的问题或陈述（系统封装为 Decisions，返还是/否）。',
)
@click.option(
    '--with-profile',
    'profile_name',
    default=None,
    help='Chat preset file name under chat_profiles_subdir (e.g. example.yaml). '
    '--text stays on the CLI.',
)
@click.option(
    '--system-prompt',
    default=None,
    help='Optional system message prepended for this request only.',
)
@click.option(
    '--with-context',
    is_flag=True,
    default=None,
    help='Read/write the active global session segment under session/.',
)
@click.option(
    '--timeout',
    type=float,
    default=None,
    help=f'HTTP timeout in seconds (default {DEFAULT_CHAT_TIMEOUT}, or from profile).',
)
@click.option(
    '--max-tokens',
    type=int,
    default=None,
    help=f'Max completion tokens (default {DEFAULT_CHAT_MAX_TOKENS}, or from profile).',
)
@click.pass_context
def chat_cmd(
    ctx: click.Context,
    text: str,
    profile_name: str | None,
    system_prompt: str | None,
    with_context: bool | None,
    timeout: float | None,
    max_tokens: int | None,
) -> None:
    """Chat with the default model (JEV: binary 是/否 via SystemOne, not chat/completions)."""
    settings: Settings = ctx.obj['settings']
    profile = None
    if profile_name is not None:
        try:
            resolved = resolve_chat_profile_path(
                settings.chat_profiles_dir,
                profile_name,
            )
            profile = load_chat_profile(resolved)
        except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
            CONSOLE.print(f'[bold red]{exc}[/bold red]')
            raise SystemExit(1) from exc

    system_prompt_set = (
        ctx.get_parameter_source('system_prompt')  # type: ignore[attr-defined]
        == click.core.ParameterSource.COMMANDLINE
    )
    opts = merge_chat_options(
        profile,
        system_prompt=system_prompt,
        system_prompt_set=system_prompt_set,
        with_context=with_context,
        timeout=timeout,
        max_tokens=max_tokens,
    )
    run_chat(
        settings,
        text=text,
        with_context=opts.with_context,
        system_prompt=opts.system_prompt,
        timeout=opts.timeout,
        max_tokens=opts.max_tokens,
    )
