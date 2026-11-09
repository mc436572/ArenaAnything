"""ssj config — instance environment (process root, paths, config.yaml)."""

from __future__ import annotations

import re
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from cli.console import CONSOLE
from ssj.model_secrets import _UNKNOWN_HINT, secret_status
from ssj.models_store import load_models_store
from ssj.settings import (
    CONFIG_YAML_KEYS,
    Settings,
    init_data_dir,
    load_settings,
    update_config_field,
)

_INSTANCE_DIR_RE = re.compile(r'^ssj-(?P<profile>[a-z][a-z0-9_-]*)$')


@click.group(
    'config',
    context_settings={'help_option_names': ['-h', '--help']},
    no_args_is_help=True,
)
def config_group() -> None:
    """Instance environment: process root, paths, and config.yaml."""


def run_config_init(ctx: click.Context) -> Settings:
    """Ensure dirs and config.yaml exist (used by ssj setup step 1)."""
    settings = init_data_dir()
    (settings.data_dir / 'reports').mkdir(exist_ok=True)
    ctx.obj['settings'] = settings
    CONSOLE.print(
        f'[dim]root[/dim] {settings.data_dir}\n'
        f'[dim]trace[/dim] {settings.trace_dir}'
    )
    return settings


def infer_instance_profile(data_dir: Path, store) -> str | None:
    match = _INSTANCE_DIR_RE.match(data_dir.name)
    if not match:
        return None
    candidate = match.group('profile')
    if candidate in store.models:
        return candidate
    return None


def run_setup(ctx: click.Context) -> None:
    """One-stop: environment (config) → model profile → ping default."""
    from ssj.model_cmd import run_model_setup, run_setup_ping

    CONSOLE.print('[bold]1/3 Environment[/bold] (config)')
    settings = run_config_init(ctx)

    store = load_models_store(settings.data_dir)
    alias = infer_instance_profile(settings.data_dir, store) or store.default
    if alias not in store.models:
        alias = click.prompt('Profile to configure', default=store.default).strip()
    if not alias:
        CONSOLE.print('[bold red]Profile alias cannot be empty.[/bold red]')
        raise SystemExit(1)

    CONSOLE.print(f'[bold]2/3 Model[/bold] [cyan]{alias}[/cyan]')
    run_model_setup(ctx, alias, interactive_default=False)

    settings = load_settings()
    ctx.obj['settings'] = settings
    store = load_models_store(settings.data_dir)
    prof = store.models[store.default]

    CONSOLE.print('[bold]3/3 Ping[/bold]')
    code = run_setup_ping(prof)
    if code == 0:
        CONSOLE.print('[bold green]Setup complete.[/bold green]')
    raise SystemExit(code)


@config_group.command('set')
@click.argument('key', required=False)
@click.argument('value', required=False)
@click.pass_context
def config_set(ctx: click.Context, key: str | None, value: str | None) -> None:
    """Set config.yaml field: profile, max_steps, sandbox, trace_subdir, chat_profiles_subdir."""
    settings: Settings = ctx.obj['settings']
    if not settings.config_path.is_file():
        CONSOLE.print(
            '[bold red]No config.yaml in the process root.[/bold red] '
            'Run [bold green]ssj setup[/bold green] first.'
        )
        raise SystemExit(1)

    chosen = _pick_config_key(key)
    if value is None:
        current = _current_config_value(settings, chosen)
        default = str(current) if current is not None else ''
        value = click.prompt(chosen, default=default, type=str).strip()
    if not value.strip() and chosen != 'profile':
        CONSOLE.print('[bold red]Value cannot be empty.[/bold red]')
        raise SystemExit(1)

    try:
        update_config_field(settings.config_path, chosen, value)
    except ValueError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc
    ctx.obj['settings'] = load_settings()
    CONSOLE.print(f'[bold green]{chosen}[/bold green] updated.')


@config_group.command('show')
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show process root, paths, and config.yaml (model summary + secret status)."""
    settings: Settings = ctx.obj['settings']
    if not settings.config_path.is_file():
        CONSOLE.print(
            '[bold red]No config.yaml found in the process root.[/bold red] '
            'Run [bold green]ssj setup[/bold green] first.'
        )
        raise SystemExit(1)

    _render_settings(settings)


def _pick_config_key(key: str | None) -> str:
    allowed = sorted(CONFIG_YAML_KEYS)
    if key:
        chosen = key.strip()
        if chosen not in CONFIG_YAML_KEYS:
            CONSOLE.print(
                f'[bold red]Unknown key {chosen!r}.[/bold red] '
                f'Allowed: {", ".join(allowed)}'
            )
            raise SystemExit(1)
        return chosen
    if len(allowed) == 1:
        return allowed[0]
    for index, name in enumerate(allowed, start=1):
        CONSOLE.print(f'  {index}. {name}')
    pick = click.prompt(
        'Number',
        type=click.IntRange(1, len(allowed)),
        default=1,
    )
    return allowed[pick - 1]


def _current_config_value(settings: Settings, key: str) -> object | None:
    mapping = {
        'profile': settings.profile,
        'max_steps': settings.max_steps,
        'sandbox': settings.sandbox,
        'trace_subdir': settings.trace_subdir,
        'chat_profiles_subdir': settings.chat_profiles_subdir,
    }
    return mapping.get(key)


def _render_settings(settings: Settings) -> None:
    table = Table(show_header=True, header_style='bold green')
    table.add_column('Key', style='cyan')
    table.add_column('Value')

    table.add_row('root', str(settings.data_dir))
    table.add_row('config_path', str(settings.config_path))
    table.add_row('profile', settings.profile)
    table.add_row('model', f'[bold green]{settings.model_alias}[/bold green] ({settings.model})')
    table.add_row('models_path', str(settings.models_path))
    table.add_row('max_steps', str(settings.max_steps))
    table.add_row('sandbox', settings.sandbox)
    table.add_row('trace_dir', str(settings.trace_dir))
    table.add_row('chat_profiles_dir', str(settings.chat_profiles_dir))
    table.add_row('reports_dir', str(settings.data_dir / 'reports'))

    CONSOLE.print(Panel(table, title='[bold green]ssj config show[/bold green]', expand=False))

    rows = secret_status(settings.model)
    if not rows:
        CONSOLE.print(
            Panel(
                f'[yellow]{_UNKNOWN_HINT}[/yellow]\n'
                'Configure keys with [bold green]ssj model set <alias>[/bold green] '
                'or [bold green]ssj setup[/bold green].',
                title='Secrets (model)',
                expand=False,
            )
        )
        return

    sec = Table(show_header=True, header_style='bold green')
    sec.add_column('Env key', style='cyan')
    sec.add_column('Status')
    sec.add_column('Note', style='dim')
    for spec, display in rows:
        note = spec.hint or ('required' if spec.required else 'optional')
        sec.add_row(spec.name, display, note)
    CONSOLE.print(Panel(sec, title='Secrets (model)', expand=False))
