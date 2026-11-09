"""ssj model — profiles (models.yaml), provider keys (.env), connectivity."""

from __future__ import annotations

import time
import click
from rich.panel import Panel
from rich.table import Table

from cli.console import CONSOLE
from ssj.profile_configure import catalog_default_model_id, configure_profile, prompt_model_id
from ssj.model_list_labels import (
    KEYS_CONFIGURED,
    KEYS_MISSING,
    profile_keys_label,
    profile_type_label,
)
from ssj.model_ping import PingError, ping_model
from ssj.model_secrets import _UNKNOWN_HINT, resolve_secrets_for_model
from ssj.models_store import (
    ModelProfile,
    add_profile,
    delete_profile,
    load_models_store,
    matches_pattern,
    set_default,
    validate_alias,
)
from ssj.settings import Settings, load_settings


@click.group(
    'model',
    context_settings={'help_option_names': ['-h', '--help']},
    no_args_is_help=True,
)
def model_group() -> None:
    """Model profiles, API keys, and connectivity for this ssj instance."""


def run_model_setup(
    ctx: click.Context,
    alias: str,
    *,
    interactive_default: bool = True,
) -> None:
    settings: Settings = ctx.obj['settings']
    store = load_models_store(settings.data_dir)
    name = validate_alias(alias)
    if name not in store.models:
        CONSOLE.print(
            f'[bold red]Unknown model {name!r}.[/bold red] '
            'Use [bold green]ssj model add[/bold green] for a new alias.'
        )
        raise SystemExit(1)

    configure_profile(store, name)
    store = load_models_store(settings.data_dir)

    if store.default == name:
        if interactive_default:
            CONSOLE.print(f'[dim]{name} is already the default model.[/dim]')
    elif interactive_default:
        if click.confirm(f'Set {name} as default model?', default=True):
            try:
                set_default(store, name)
            except ValueError as exc:
                CONSOLE.print(f'[bold red]{exc}[/bold red]')
                raise SystemExit(1) from exc
            settings = load_settings()
            ctx.obj['settings'] = settings
            CONSOLE.print(f'Default model: [bold green]{name}[/bold green]')
        else:
            CONSOLE.print(f'[dim]Default unchanged ({store.default}).[/dim]')
    else:
        try:
            set_default(store, name)
        except ValueError as exc:
            CONSOLE.print(f'[bold red]{exc}[/bold red]')
            raise SystemExit(1) from exc
        ctx.obj['settings'] = load_settings()


def run_setup_ping(prof: ModelProfile) -> int:
    if not _profile_keys_resolvable(prof.litellm):
        CONSOLE.print(
            '[yellow]Ping skipped — configure required API keys first '
            '([bold green]ssj model set[/bold green]).[/yellow]'
        )
        return 0
    return _ping_profile(prof, times=1, http_timeout=30.0)


@model_group.command('list')
@click.option('--all', 'show_all', is_flag=True, help='Show model id and secret hints.')
@click.argument('pattern', required=False)
@click.pass_context
def model_list(ctx: click.Context, show_all: bool, pattern: str | None) -> None:
    """List profiles. Optional shell pattern (e.g. *ds*)."""
    settings = ctx.obj['settings']
    store = load_models_store(settings.data_dir)
    rows = [p for p in store.models.values() if matches_pattern(p, pattern or '')]

    if not rows:
        CONSOLE.print('[yellow]No models match.[/yellow]')
        return

    rows.sort(key=lambda p: p.alias)
    table = Table(show_header=True, header_style='bold green')

    def _keys_style(label: str) -> str:
        if label == KEYS_CONFIGURED:
            return f'[green]{label}[/green]'
        if label == KEYS_MISSING:
            return f'[yellow]{label}[/yellow]'
        return f'[dim]{label}[/dim]'

    if show_all:
        table.add_column('Alias', style='cyan')
        table.add_column('Type')
        table.add_column('Keys')
        table.add_column('Default')
        table.add_column('Model id')
        table.add_column('Description', style='dim')
        table.add_column('Env', style='dim')
        for prof in rows:
            sec = resolve_secrets_for_model(prof.litellm)
            sec_hint = ', '.join(s.name for s in sec) if sec else '—'
            keys = profile_keys_label(prof.litellm)
            mark = '[bold green]*[/bold green]' if prof.alias == store.default else ''
            table.add_row(
                prof.alias,
                profile_type_label(prof),
                _keys_style(keys),
                mark,
                prof.litellm,
                prof.description or '—',
                sec_hint,
            )
        title = 'ssj model list --all'
    else:
        table.add_column('Alias', style='cyan')
        table.add_column('Type')
        table.add_column('Keys')
        table.add_column('Default')
        table.add_column('Description')
        for prof in rows:
            keys = profile_keys_label(prof.litellm)
            mark = '[bold green]*[/bold green]' if prof.alias == store.default else ''
            desc = prof.description or prof.litellm
            table.add_row(
                prof.alias,
                profile_type_label(prof),
                _keys_style(keys),
                mark,
                desc,
            )
        title = 'ssj model list'

    CONSOLE.print(Panel(table, title=f'[bold green]{title}[/bold green]', expand=False))


@model_group.command('add')
@click.argument('alias')
@click.pass_context
def model_add(ctx: click.Context, alias: str) -> None:
    """Add a new profile interactively (alias only on the command line)."""
    store = load_models_store(ctx.obj['settings'].data_dir)
    try:
        name = validate_alias(alias)
    except ValueError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc

    if name in store.models:
        prof = store.models[name]
        CONSOLE.print(
            f'[yellow]{name}[/yellow] is already in your model list ({prof.litellm}).\n'
            f'To configure keys and default, run: ssj model set {name}'
        )
        raise SystemExit(1)

    model_id = prompt_model_id(catalog_default_model_id(name) or '')

    desc = click.prompt('Short description (optional)', default='', show_default=False).strip()

    try:
        add_profile(store, name, model_id, description=desc)
    except ValueError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc
    CONSOLE.print(f'Added [green]{name}[/green] → {model_id}')
    ctx.invoke(model_set, alias=name)


@model_group.command('del')
@click.argument('alias')
@click.option('--force', is_flag=True, help='Remove a built-in preset.')
@click.pass_context
def model_del(ctx: click.Context, alias: str, force: bool) -> None:
    """Remove a profile (not the default)."""
    settings = ctx.obj['settings']
    store = load_models_store(settings.data_dir)
    try:
        delete_profile(store, alias, force_builtin=force)
    except ValueError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc
    CONSOLE.print(f'[bold yellow]Removed {validate_alias(alias)}.[/bold yellow]')


@model_group.command('set')
@click.argument('alias')
@click.pass_context
def model_set(ctx: click.Context, alias: str) -> None:
    """Interactive: model id, API base, and keys for one profile."""
    run_model_setup(ctx, alias, interactive_default=True)


@model_group.command('ping')
@click.option('-m', '--model', 'alias', help='Profile alias to ping.')
@click.option(
    '-t',
    '--times',
    type=int,
    default=1,
    show_default=True,
    help='Repeat count (0 = until Ctrl+C).',
)
@click.option(
    '--timeout',
    'http_timeout',
    type=float,
    default=30.0,
    show_default=True,
    help='Per-request HTTP timeout (seconds).',
)
@click.pass_context
def model_ping(
    ctx: click.Context,
    alias: str | None,
    times: int,
    http_timeout: float,
) -> None:
    """Ping one profile: default model without -m, or the alias given with -m."""
    settings = ctx.obj['settings']
    store = load_models_store(settings.data_dir)

    if times < 0:
        CONSOLE.print('[bold red]-t/--times must be >= 0.[/bold red]')
        raise SystemExit(1)

    prof = _resolve_ping_profile(store, alias)
    raise SystemExit(_ping_profile(prof, times=times, http_timeout=http_timeout))


def _resolve_ping_profile(store, alias: str | None) -> ModelProfile:
    if alias:
        try:
            name = validate_alias(alias)
        except ValueError as exc:
            CONSOLE.print(f'[bold red]{exc}[/bold red]')
            raise SystemExit(1) from exc
        prof = store.models.get(name)
        if prof is None:
            CONSOLE.print(
                f'[bold red]Unknown model {name!r}.[/bold red] '
                'Run [bold green]ssj model list[/bold green] to see aliases.'
            )
            raise SystemExit(1)
        return prof

    default_name = (store.default or '').strip()
    if not default_name:
        CONSOLE.print(
            '[bold red]No default model is set.[/bold red] '
            'Run [bold green]ssj model set <alias>[/bold green] and mark it as default, '
            'or [bold green]ssj model ping -m <alias>[/bold green].'
        )
        raise SystemExit(1)
    try:
        name = validate_alias(default_name)
    except ValueError as exc:
        CONSOLE.print(f'[bold red]Invalid default in models.yaml:[/bold red] {exc}')
        raise SystemExit(1) from exc
    prof = store.models.get(name)
    if prof is None:
        CONSOLE.print(
            f'[bold red]Default model {name!r} is missing from models.yaml.[/bold red] '
            f'Run [bold green]ssj model set {name}[/bold green] or fix the default entry.'
        )
        raise SystemExit(1)
    return prof


def _profile_keys_resolvable(litellm: str) -> bool:
    specs = resolve_secrets_for_model(litellm)
    if not specs:
        return False
    missing = [
        s.name
        for s in specs
        if s.required and not _env_has_for_model(litellm, s.name)
    ]
    return not missing


def _ping_profile(prof: ModelProfile, *, times: int, http_timeout: float) -> int:
    name = prof.alias
    if not _profile_keys_resolvable(prof.litellm):
        specs = resolve_secrets_for_model(prof.litellm)
        if not specs:
            CONSOLE.print(f'[bold red]{name}:[/bold red] {_UNKNOWN_HINT}')
            return 1
        missing = [
            s.name
            for s in specs
            if s.required and not _env_has_for_model(prof.litellm, s.name)
        ]
        CONSOLE.print(
            f'[bold red]{name}:[/bold red] missing keys: '
            + ', '.join(missing)
            + '. Run [bold green]ssj model set <alias>[/bold green].'
        )
        return 1

    infinite = times == 0
    label = 'until stopped' if infinite else str(times)
    CONSOLE.print(
        f'[bold]Ping[/bold] [cyan]{name}[/cyan] ({prof.litellm}) — {label} request(s), '
        f'HTTP timeout {http_timeout}s'
    )

    latencies: list[float] = []
    failures = 0
    seq = 0
    try:
        while infinite or seq < times:
            seq += 1
            started = time.perf_counter()
            try:
                if seq == 1 and len(latencies) == 0 and failures == 0:
                    with CONSOLE.status(f'  #{seq} …', spinner='dots'):
                        reply = ping_model(prof.litellm, timeout=http_timeout)
                else:
                    reply = ping_model(prof.litellm, timeout=http_timeout)
            except PingError as exc:
                elapsed = time.perf_counter() - started
                failures += 1
                CONSOLE.print(f'  #{seq}: [red]failed[/red] ({elapsed:.3f}s) — {exc}')
                if not infinite and seq >= times:
                    break
                continue

            elapsed = time.perf_counter() - started
            latencies.append(elapsed)
            snippet = (reply or '').replace('\n', ' ')[:80]
            CONSOLE.print(f'  #{seq}: [green]ok[/green] ({elapsed:.3f}s) — {snippet}')
            if not infinite and seq >= times:
                break
    except KeyboardInterrupt:
        CONSOLE.print('[yellow]Stopped.[/yellow]')

    sent = seq
    received = len(latencies)
    stats = Table(show_header=True, header_style='bold green')
    stats.add_column('Metric', style='cyan')
    stats.add_column('Value', justify='right')
    stats.add_row('sent', str(sent))
    stats.add_row('received', str(received))
    stats.add_row('failed', str(failures))
    if latencies:
        lo = min(latencies)
        hi = max(latencies)
        avg = sum(latencies) / len(latencies)
        total = sum(latencies)
        stats.add_row('min (s)', f'{lo:.3f}')
        stats.add_row('avg (s)', f'{avg:.3f}')
        stats.add_row('max (s)', f'{hi:.3f}')
        stats.add_row('total (s)', f'{total:.3f}')
    CONSOLE.print(
        Panel(
            stats,
            title=f'[bold green]{name} ping statistics[/bold green]',
            expand=False,
        )
    )
    return 1 if failures and not latencies else (1 if failures else 0)


def _env_has_for_model(litellm: str, key: str) -> bool:
    from ssj.model_secrets import env_value_for_model

    return bool(env_value_for_model(litellm, key))
