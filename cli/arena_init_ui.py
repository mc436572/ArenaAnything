"""Colored step output for arena init (Rich)."""

from __future__ import annotations

from typing import Any

from cli.console import CONSOLE

INIT_STEPS = 3


class InitReporter:
    def __init__(self) -> None:
        self.console = CONSOLE
        self._progress: Any = None
        self._extract_task: Any = None

    def header(self, *, case_dir, rebuild: bool, profiles: list[str], line: str) -> None:
        mode = 'Rebuilt' if rebuild else 'Materialized'
        self.console.print(f'[bold]{mode}:[/] {case_dir}')
        from shared.case_workspace import instance_dir_name

        for profile in profiles:
            self.console.print(f'  [cyan]{instance_dir_name(line, profile)}/[/]')

    def step_running(self, step: int, title: str) -> None:
        self.console.print(
            f'[bold cyan]Step {step}/{INIT_STEPS}[/] [bold]{title}[/]  [yellow]…[/]'
        )

    def begin_bundle_extract(self, label: str) -> None:
        from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

        self._progress = Progress(
            TextColumn('  [dim]{task.description}'),
            BarColumn(bar_width=40),
            TextColumn('[progress.percentage]{task.percentage:>3.0f}%'),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )
        self._progress.start()
        self._extract_task = self._progress.add_task(label, total=1)

    def update_bundle_extract(self, current: int, total: int) -> None:
        if self._progress is not None and self._extract_task is not None:
            self._progress.update(
                self._extract_task,
                completed=current,
                total=max(total, 1),
            )

    def end_bundle_extract(self) -> None:
        if self._progress is not None:
            self._progress.stop()
        self._progress = None
        self._extract_task = None

    def step_done(self, step: int, title: str, detail: str = '') -> None:
        line = f'[bold cyan]Step {step}/{INIT_STEPS}[/] [bold]{title}[/]  [green]✓[/]'
        if detail:
            line += f'  [dim]{detail}[/]'
        self.console.print(line)

    def step_skip(self, step: int, title: str, reason: str) -> None:
        self.console.print(
            f'[bold cyan]Step {step}/{INIT_STEPS}[/] [bold]{title}[/]  '
            f'[dim yellow]skipped[/] [dim]({reason})[/]'
        )

    def ping_row(self, *, instance_dir: str, ok: bool, detail: str) -> None:
        mark = '[green]ok[/]' if ok else '[bold red]FAIL[/]'
        suffix = f'  [dim]{detail}[/]' if detail.strip() else ''
        self.console.print(f'  [bold]{instance_dir:12}[/] {mark}{suffix}')

    def ping_all_ok(self) -> None:
        self.console.print('[green]Ping: all profiles OK.[/]')

    def ping_failed(self, names: str) -> None:
        self.console.print(f'[bold red]Ping failed for:[/] {names}')

    def next_hint(self, text: str) -> None:
        self.console.print(f'[dim]Next:[/] {text}')
