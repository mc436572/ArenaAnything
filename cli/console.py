"""Rich console for ssj (mini-like markup conventions)."""

import os

from rich.console import Console
from rich.rule import Rule

CONSOLE = Console(highlight=False)


def print_startup_banner(*, version: str, config_path) -> None:
    if os.environ.get('SSJ_SILENT_STARTUP'):
        return
    CONSOLE.print(
        f"This is [bold green]SSaiyan(V{version})[/bold green]. Have a nice day!\n"
        f"Config: [bold green]{config_path}[/bold green]",
    )
    CONSOLE.print(Rule(style='dim green'))
