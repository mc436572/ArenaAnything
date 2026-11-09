"""ssj — whiteboard agent instance CLI (one process root)."""

from __future__ import annotations

import click

from ssj.chat_cmd import chat_cmd
from ssj.eval_cmd import eval_cmd
from ssj.config_cmd import config_group, run_setup
from cli.console import CONSOLE, print_startup_banner
from cli.group import SsjGroup
from ssj.model_cmd import model_group
from ssj.settings import PACKAGE_VERSION, RootMismatchError, load_settings


@click.group(cls=SsjGroup, context_settings={'help_option_names': ['-h', '--help']})
@click.pass_context
def main(ctx: click.Context) -> None:
    """ssj — one agent instance per process root (config, model, chat, eval). Cases: arena."""
    from shared.runtime_platform import require_linux_or_wsl

    require_linux_or_wsl()
    ctx.ensure_object(dict)
    if ctx.resilient_parsing:
        return
    try:
        settings = load_settings()
    except RootMismatchError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc
    ctx.obj['settings'] = settings
    print_startup_banner(version=PACKAGE_VERSION, config_path=settings.config_path)


@main.command('setup', context_settings={'help_option_names': ['-h', '--help']})
@click.pass_context
def setup_cmd(ctx: click.Context) -> None:
    """One-stop: environment (config) → model profile → ping default."""
    run_setup(ctx)


main.add_command(config_group)
main.add_command(model_group)
main.add_command(chat_cmd)
main.add_command(eval_cmd)


if __name__ == '__main__':
    main()
