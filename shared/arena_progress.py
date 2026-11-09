"""Poll ssj eval progress files while arena run workers are active."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import TypeVar

from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from cli.console import CONSOLE
from shared.eval_progress_file import read_progress_snapshot

T = TypeVar('T')


def clear_progress_snapshots(progress_paths: dict[tuple[str, str], Path]) -> None:
    for path in progress_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            path.unlink()


def _elapsed_from_snapshot(snap: dict) -> float | None:
    if snap.get('elapsed_sec') is not None:
        return float(snap['elapsed_sec'])
    started = snap.get('started_at')
    ts = snap.get('ts')
    if started is not None and ts is not None:
        return round(float(ts) - float(started), 2)
    return None


def _format_elapsed(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return '—'
    total = int(round(seconds))
    minutes, sec = divmod(total, 60)
    if minutes:
        return f'{minutes}:{sec:02d}'
    return f'0:{sec:02d}'


def _poll_progress_files(
    progress: Progress,
    task_ids: dict[tuple[str, str], int],
    progress_paths: dict[tuple[str, str], Path],
    *,
    totals_locked: set[tuple[str, str]],
) -> None:
    for key, path in progress_paths.items():
        snap = read_progress_snapshot(path)
        if snap is None:
            continue
        tid = task_ids.get(key)
        if tid is None:
            continue
        total = int(snap.get('total') or 0) or 1
        done = int(snap.get('done') or 0)
        item = str(snap.get('item_id') or '')
        status = str(snap.get('status') or 'running')
        desc = f'{key[0]}/{key[1]}'
        if item:
            desc = f'{desc} {item}'
        if status == 'done':
            done = total
        elif status == 'failed':
            desc = f'{desc} failed'
        if key not in totals_locked and total > 1:
            progress.update(tid, total=total)
            totals_locked.add(key)
        progress.update(tid, completed=min(done, total), total=total, description=desc)


def _print_run_timings(
    cells: list[tuple[str, str]],
    progress_paths: dict[tuple[str, str], Path],
) -> None:
    table = Table(show_header=True, header_style='bold', box=None, pad_edge=False)
    table.add_column('run', no_wrap=True)
    table.add_column('progress', justify='right', no_wrap=True)
    table.add_column('elapsed', justify='right', no_wrap=True)
    for profile, suite in cells:
        key = (profile, suite)
        path = progress_paths.get(key)
        snap = read_progress_snapshot(path) if path else None
        label = f'{profile}/{suite}'
        if not snap:
            table.add_row(label, '—', '—')
            continue
        total = int(snap.get('total') or 0)
        done = int(snap.get('done') or 0)
        elapsed = _elapsed_from_snapshot(snap)
        table.add_row(label, f'{done}/{total}', _format_elapsed(elapsed))
    CONSOLE.print()
    CONSOLE.print('[bold]run time:[/]')
    CONSOLE.print(table)


def run_with_progress_monitor(
    cells: list[tuple[str, str]],
    progress_paths: dict[tuple[str, str], Path],
    *,
    workers: int,
    submit_cell: Callable[[str, str], T],
) -> list[T]:
    """One worker per profile; poll SSJ_PROGRESS_FILE snapshots for Rich bars."""
    by_profile: dict[str, list[tuple[str, str]]] = {}
    for profile, suite in cells:
        by_profile.setdefault(profile, []).append((profile, suite))

    results: list[T] = []
    pool_workers = max(1, min(workers, len(by_profile)))
    totals_locked: set[tuple[str, str]] = set()

    CONSOLE.print('[bold]running:[/]')
    with Progress(
        TextColumn('[bold cyan]{task.description}'),
        BarColumn(),
        TextColumn('{task.completed}/{task.total}'),
        console=CONSOLE,
        transient=False,
        refresh_per_second=4,
    ) as progress:
        task_ids: dict[tuple[str, str], int] = {}
        for profile, suite in cells:
            key = (profile, suite)
            path = progress_paths.get(key)
            snap = read_progress_snapshot(path) if path else None
            init_total = int(snap.get('total') or 0) if snap else 0
            tid = progress.add_task(
                f'{profile}/{suite}',
                total=init_total if init_total > 0 else 1,
            )
            task_ids[key] = tid
            if init_total > 1:
                totals_locked.add(key)

        def _run_profile(profile: str, suite_rows: list[tuple[str, str]]) -> list[T]:
            out: list[T] = []
            for p, s in suite_rows:
                out.append(submit_cell(p, s))
            return out

        with ThreadPoolExecutor(max_workers=pool_workers) as pool:
            pending: dict[Future[list[T]], str] = {
                pool.submit(_run_profile, profile, rows): profile
                for profile, rows in by_profile.items()
            }
            while pending:
                _poll_progress_files(
                    progress, task_ids, progress_paths, totals_locked=totals_locked
                )
                finished = [f for f in pending if f.done()]
                for fut in finished:
                    results.extend(fut.result())
                    del pending[fut]
                if pending:
                    time.sleep(0.25)
            _poll_progress_files(
                progress, task_ids, progress_paths, totals_locked=totals_locked
            )

    _print_run_timings(cells, progress_paths)
    return results
