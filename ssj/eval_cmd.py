"""ssj eval — multiple-choice suite scoring via manifest + preset profile."""

from __future__ import annotations

import json

import click
import yaml
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from cli.console import CONSOLE
from shared.benchmark_probes import BenchmarkProbeError, load_probe_items
from ssj.chat_profile import load_eval_profile, resolve_chat_profile_path
from ssj.eval_case_env import eval_run_overrides_from_env
from ssj.model_ping import PingError
from ssj.model_reply import chat_probe_reply
from shared.eval_progress_file import EvalProgressWriter
from ssj.probe_runner import default_report_path, run_probe_suite, write_probe_report
from ssj.settings import PACKAGE_VERSION, Settings


def run_eval(
    settings: Settings,
    *,
    suite: str,
    profile_name: str,
) -> None:
    if not settings.model_alias or not settings.model:
        CONSOLE.print(
            '[bold red]No default model is set.[/bold red] '
            'Run [bold green]ssj model set[/bold green] in this process root.'
        )
        raise SystemExit(1)

    try:
        resolved = resolve_chat_profile_path(settings.chat_profiles_dir, profile_name)
        opts = load_eval_profile(resolved)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc

    suite_name = suite.strip()
    if not suite_name:
        CONSOLE.print('[bold red]--suite cannot be empty.[/bold red]')
        raise SystemExit(1)

    try:
        items = load_probe_items(suite_name)
    except BenchmarkProbeError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc

    overrides = eval_run_overrides_from_env()
    item_limit = (
        overrides.probe_limit
        if overrides.probe_limit is not None
        else opts.limit
    )
    if item_limit:
        items = items[:item_limit]
    if not items:
        CONSOLE.print('[bold red]Suite has no items (check --suite or profile limit).[/bold red]')
        raise SystemExit(1)

    CONSOLE.print(
        f'Suite [bold]{suite_name}[/bold] · {len(items)} items · '
        f'profile [bold]{profile_name}[/bold] · '
        f'[bold]{settings.model_alias}[/bold] ({settings.model})'
    )

    def _complete(model: str, messages: list[dict[str, str]], **kwargs: object) -> str:
        return chat_probe_reply(model, messages, **kwargs)  # type: ignore[arg-type]

    progress_writer = EvalProgressWriter.from_env(
        suite=suite_name,
        model_alias=settings.model_alias,
        litellm_model=settings.model,
    )
    if progress_writer is not None:
        progress_writer.write_started(total=len(items))

    try:
        with Progress(
            TextColumn('[bold blue]{task.description}'),
            BarColumn(),
            TextColumn('{task.completed}/{task.total}'),
            TimeElapsedColumn(),
            console=CONSOLE,
            transient=True,
        ) as progress:
            task_id = progress.add_task('Eval', total=len(items))

            def _on_progress(done: int, total: int, item_id: str, row: dict) -> None:
                mark = '[green]✓[/green]' if row.get('correct') else '[red]✗[/red]'
                if row.get('error'):
                    mark = '[yellow]![/yellow]'
                progress.update(
                    task_id,
                    completed=done,
                    description=f'{item_id} {mark}',
                )
                if progress_writer is not None:
                    progress_writer.write_item(
                        done,
                        total,
                        item_id,
                        row,
                        force=bool(row.get('error')),
                    )

            eval_timeout = (
                overrides.timeout if overrides.timeout is not None else opts.timeout
            )
            eval_temperature = (
                overrides.temperature if overrides.temperature is not None else 0.0
            )
            report = run_probe_suite(
                items,
                settings.model,
                complete=_complete,
                system_prompt=opts.system_prompt,
                temperature=eval_temperature,
                timeout=eval_timeout,
                max_tokens=opts.max_tokens,
                on_progress=_on_progress,
            )
    except PingError as exc:
        if progress_writer is not None:
            progress_writer.write_failed(str(exc))
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc

    if progress_writer is not None:
        progress_writer.write_finished(
            done=int(report['n']),
            total=int(report['n']),
            correct=int(report['correct']),
        )

    report['suite'] = suite_name
    report['model_alias'] = settings.model_alias
    report['ssj_version'] = PACKAGE_VERSION
    report['eval_profile'] = profile_name

    table = Table(show_header=True, header_style='bold')
    table.add_column('id')
    table.add_column('answer')
    table.add_column('parsed')
    table.add_column('ok')
    table.add_column('ms', justify='right')
    for row in report['items']:
        ok = 'yes' if row['correct'] else 'no'
        style = 'green' if row['correct'] else 'red'
        parsed = row['parsed'] or '-'
        if row.get('error'):
            parsed = 'err'
        table.add_row(
            str(row['id']),
            str(row['answer']),
            parsed,
            f'[{style}]{ok}[/{style}]',
            str(row['latency_ms']),
        )
    CONSOLE.print(table)

    path = write_probe_report(
        report,
        default_report_path(settings.data_dir, suite_name, settings.model_alias),
    )
    acc = report['accuracy'] * 100
    CONSOLE.print(
        f"[bold]{report['correct']}/{report['n']}[/bold]  {acc:.1f}%  →  "
        f'[bold green]{path}[/bold green]'
    )


@click.command('eval', context_settings={'help_option_names': ['-h', '--help']})
@click.option(
    '--suite',
    '-s',
    required=True,
    help='Suite name from benchmark/manifest.yaml (e.g. demo, ceval).',
)
@click.option(
    '--with-profile',
    'profile_name',
    required=True,
    help='Scoring rules preset under chat_profiles_subdir (system_prompt, timeout, max_tokens, limit).',
)
@click.pass_context
def eval_cmd(ctx: click.Context, suite: str, profile_name: str) -> None:
    """Score a multiple-choice suite; --suite selects items, --with-profile selects rules."""
    settings: Settings = ctx.obj['settings']
    run_eval(settings, suite=suite, profile_name=profile_name)
