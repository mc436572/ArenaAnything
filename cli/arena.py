"""arena — global Case pool (list/init/del) and per-Case check/run/summary."""

from __future__ import annotations

from pathlib import Path

import click

from cli.group import SsjGroup


def _repo_start() -> Path:
    return Path.cwd()


def _rel_to_repo(path: Path) -> str:
    from shared.case_catalog import find_repo_root

    repo = find_repo_root(_repo_start())
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_report(case_yaml: Path) -> tuple[Path, Path]:
    from cli.console import CONSOLE
    from shared.arena_output import build_summary, print_accuracy_matrix, write_case_output

    summary_path, html_path = write_case_output(case_yaml)
    print_accuracy_matrix(build_summary(case_yaml))
    CONSOLE.print('[bold]summary:[/]')
    CONSOLE.print(f'  {_rel_to_repo(summary_path)}')
    CONSOLE.print(f'  {_rel_to_repo(html_path)}')
    return summary_path, html_path


def _resolve_case(case_id: str) -> Path:
    from shared.case_catalog import resolve_case_yaml

    return resolve_case_yaml(case_id, start=_repo_start())


def _case_option(*, required: bool = True):
    def decorator(f):
        return click.option(
            '-c',
            '--case',
            'case_id',
            required=required,
            help='Case id (workspace case/<id>/).',
        )(f)

    return decorator


@click.group(
    cls=SsjGroup,
    context_settings={'help_option_names': ['-h', '--help']},
)
def main() -> None:
    """Arena — Case pool under case/; materialize with init, eval with run.

    Typical flow: arena list -> arena init --case NAME -> arena check -c NAME
    -> arena run -c NAME all
    """
    from shared.runtime_platform import require_linux_or_wsl

    require_linux_or_wsl()


@main.command('list')
def cmd_list() -> None:
    """List Case profiles and workspaces in this repo."""
    from shared.case_catalog import find_repo_root, list_case_catalog

    repo = find_repo_root(_repo_start())
    rows = list_case_catalog(repo)
    from cli.console import CONSOLE
    from rich.table import Table

    if not rows:
        CONSOLE.print(
            '[dim]No case recipes (templates/case/*.yaml) or workspaces (case/*/case.yaml).[/]'
        )
        return

    CONSOLE.print(
        '[dim]Legend:[/] [cyan]recipe[/] = templates/case only · '
        '[green]ready[/] = materialized case/<id>/ · '
        '[yellow]on-disk[/] = workspace incomplete'
    )
    table = Table(show_header=True, header_style='bold', pad_edge=False, box=None)
    table.add_column('case_id', style='bold', no_wrap=True, min_width=22)
    table.add_column('status', no_wrap=True, min_width=10)
    table.add_column('title', overflow='fold')
    for row in rows:
        if row.on_disk and row.materialized:
            status = '[green]ready[/]'
        elif row.on_disk:
            status = '[yellow]on-disk[/]'
        elif row.defined:
            status = '[cyan]recipe[/]'
        else:
            status = '[dim]-[/]'
        title = row.title or '-'
        if row.on_disk and row.materialized:
            title_cell = title
        elif row.defined and not row.on_disk:
            title_cell = f'[dim]{title}[/]'
        else:
            title_cell = title
        table.add_row(row.case_id, status, title_cell)
    CONSOLE.print(table)


@main.command('init')
@click.option(
    '--case',
    'case_id',
    required=True,
    help='Case id (templates/case/<id>.yaml → case/<id>/).',
)
@click.option(
    '--no-key',
    is_flag=True,
    help='During the init process, no writing API keys from the secrets pool.',
)
@click.option(
    '--rebuild',
    is_flag=True,
    help=(
        'Completely clear case/<id>/ dir, recreate from templates, and apply keys '
        'from secrets pool. Finally try to make a model ping to check them.'
    ),
)
@click.option(
    '--no-ping',
    is_flag=True,
    help='At the end of the init process, no model ping to check them.',
)
def cmd_init(case_id: str, no_key: bool, rebuild: bool, no_ping: bool) -> None:
    """Create or refresh case/<CASE_ID>/ from templates/case/<CASE_ID>.yaml.

    Default (no --rebuild): fill missing dirs/files only; merge missing keys from
    the secrets pool into each ssj-<profile>/.env; ping all profiles when keys apply.

    --rebuild: completely remove the case workspace first, then full recreate from
    templates + frozen bundle, pool keys, and connectivity ping.
    """
    from shared.case_catalog import add_case, find_repo_root
    from shared.case_secrets import SecretsPoolError
    from shared.case_workspace import instance_dir_name, load_case_spec

    from cli.arena_init_ui import InitReporter
    from shared.case_catalog import case_workspace_dir, load_profile_recipe

    repo = find_repo_root(_repo_start())
    apply_keys = not no_key
    reporter = InitReporter()
    try:
        recipe = load_profile_recipe(repo, case_id)
        agent_preview = recipe.get('agent') or {}
        line = str(agent_preview.get('line') or 'ssj')
        profiles = (recipe.get('matrix') or {}).get('profiles') or []
        profile_names = [str(p).strip() for p in profiles if str(p).strip()]
        case_dir = case_workspace_dir(repo, case_id)
        reporter.header(
            case_dir=case_dir,
            rebuild=rebuild,
            profiles=profile_names,
            line=line,
        )
        case_dir = add_case(
            case_id,
            repo_root=repo,
            apply_keys=apply_keys,
            rebuild=rebuild,
            init_ui=reporter,
        )
    except (FileNotFoundError, ValueError, SecretsPoolError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    spec = load_case_spec(case_dir / 'case.yaml')
    line = str((spec.get('agent') or {}).get('line') or 'ssj')

    agent = spec.get('agent') or {}
    version = str(agent.get('version') or '0.1.0')

    step3_title = 'Model ping (parallel)'
    if no_ping or not apply_keys:
        if not apply_keys:
            reporter.step_skip(3, step3_title, '--no-key')
        else:
            reporter.step_skip(3, step3_title, '--no-ping')
        reporter.next_hint('arena check --case …')
        return

    from shared.case_init_ping import ping_case_profiles

    reporter.step_running(3, step3_title)
    ping_rows = ping_case_profiles(
        case_dir=case_dir,
        agent_line=line,
        agent_version=version,
        profiles=profile_names,
    )
    failed = [r for r in ping_rows if not r.ok]
    reporter.step_done(3, step3_title, f'{len(profile_names)} profiles')
    for row in ping_rows:
        reporter.ping_row(instance_dir=row.instance_dir, ok=row.ok, detail=row.detail[:120])
    if failed:
        names = ', '.join(r.profile for r in failed)
        reporter.ping_failed(names)
        raise SystemExit(1)
    reporter.ping_all_ok()
    reporter.next_hint('arena run --case …')


@main.command('del')
@click.argument('case_id', type=str)
@click.option(
    '--silent',
    is_flag=True,
    help='Delete case/<case_id>/ immediately without a confirmation prompt.',
)
def cmd_del(case_id: str, silent: bool) -> None:
    """Remove case/<case_id>/ from disk."""
    from cli.console import CONSOLE
    from shared.case_catalog import delete_case, find_repo_root

    repo = find_repo_root(_repo_start())
    rel = f'case/{case_id.strip()}/'
    if not silent:
        CONSOLE.print(
            f'[bold red]Warning:[/] permanently delete [bold yellow]{rel}[/]?'
        )
        CONSOLE.print(
            '[dim]All contents will be removed: reports, ssj-* instances, '
            '.env, extracted bundle.[/]'
        )
        if not click.confirm('Continue?', default=False):
            CONSOLE.print('[yellow]Aborted.[/]')
            raise SystemExit(0)
    try:
        delete_case(case_id, repo_root=repo, force=True)
    except (FileNotFoundError, ValueError) as exc:
        CONSOLE.print(f'[bold red]{exc}[/]')
        raise SystemExit(1) from exc
    CONSOLE.print(f'[green]Deleted workspace[/] [bold]{rel}[/]')
    recipe = f'templates/case/{case_id.strip()}.yaml'
    from shared.case_catalog import profile_recipe_path

    if profile_recipe_path(repo, case_id).is_file():
        CONSOLE.print(
            f'[dim]Recipe[/] [cyan]{recipe}[/] [dim]still exists — '
            f'arena list will show[/] [cyan]recipe[/][dim]; use[/] '
            f'[bold]arena init --case {case_id.strip()}[/] [dim]to recreate workspace.[/]'
        )


@main.command('check')
@_case_option()
@click.option(
    '--strict/--no-strict',
    default=False,
    help='Exit 1 on validation errors (default: show warnings/errors and still exit 0).',
)
def cmd_check(case_id: str, strict: bool) -> None:
    """Show matrix, instances, and validation for one Case."""
    from shared.case_instances import list_instances
    from shared.case_validate import validate_case

    try:
        case_yaml = _resolve_case(case_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc

    result = validate_case(case_yaml)
    for warn in result.warnings:
        click.echo(f'warning: {warn}', err=True)
    if result.errors:
        for err in result.errors:
            click.echo(f'error: {err}', err=True)

    from cli.console import CONSOLE
    from rich.table import Table

    spec, rows = list_instances(case_yaml)
    CONSOLE.print(f'[bold]{spec.case_id}[/]  [dim]·[/]  {spec.title}')
    CONSOLE.print(f'[dim]suites[/]  {", ".join(spec.suites)}')
    CONSOLE.print()

    table = Table(show_header=True, header_style='bold', pad_edge=False, box=None)
    table.add_column('instance', style='bold', no_wrap=True, min_width=12)
    table.add_column('status', overflow='fold')
    for row in rows:
        if not row.materialized:
            status = '[yellow]missing[/]  [dim]run arena init[/]'
        elif row.missing_keys:
            miss = ', '.join(row.missing_keys)
            status = f'[red]keys missing[/]  [dim]{miss}[/]'
        else:
            status = '[green]ok[/]  [dim]keys ok[/]'
        table.add_row(row.instance_dir, status)
    CONSOLE.print(table)

    if strict and result.errors:
        raise SystemExit(1)
    if not result.errors:
        CONSOLE.print('[green]OK[/]')


@main.command('summary')
@_case_option()
def cmd_summary(case_id: str) -> None:
    """Write export/summary.json and export/index.html for one Case."""
    try:
        case_yaml = _resolve_case(case_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    _write_report(case_yaml)


@main.command('run')
@_case_option()
@click.argument(
    'scope',
    required=False,
    default='all',
    type=click.Choice(['all'], case_sensitive=False),
)
@click.option(
    '--suite',
    'suite_filter',
    multiple=True,
    help='Use specific benchmark suites (default: all in case.yaml).',
)
def cmd_run(
    case_id: str,
    scope: str,
    suite_filter: tuple[str, ...],
) -> None:
    """Run eval matrix; on success automatically runs arena summary."""
    from shared.arena_runner import run_case_matrix
    from shared.case_validate import CaseValidationError

    try:
        case_yaml = _resolve_case(case_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc

    _ = scope  # only ``all`` today; profiles from case.yaml matrix
    suites = tuple(suite_filter) if suite_filter else None
    try:
        results = run_case_matrix(
            case_yaml,
            check_keys=False,
            profiles=None,
            suites=suites,
        )
    except CaseValidationError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc
    except ValueError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc

    failed = 0
    for row in results:
        if row.exit_code != 0:
            failed += 1
            click.echo(
                f'failed: {row.profile}/{row.suite} (exit {row.exit_code})',
                err=True,
            )
            if row.log.strip():
                click.echo(row.log[-2000:], err=True)
    if failed:
        raise SystemExit(1)
    _write_report(case_yaml)


if __name__ == '__main__':
    main()
