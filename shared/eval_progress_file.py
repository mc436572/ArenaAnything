"""Throttled eval progress snapshots for arena (env SSJ_PROGRESS_FILE)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def progress_file_from_env() -> Path | None:
    raw = os.environ.get('SSJ_PROGRESS_FILE', '').strip()
    if not raw:
        return None
    return Path(raw)


def progress_step_from_env() -> int:
    raw = os.environ.get('SSJ_PROGRESS_STEP', '5').strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def should_write_progress(
    done: int,
    total: int,
    *,
    step: int,
    force: bool = False,
) -> bool:
    """Reduce disk IO: first, last, every N items, and forced (errors)."""
    if force:
        return True
    if total <= 0:
        return done > 0
    if done <= 1 or done >= total:
        return True
    if step <= 1:
        return True
    return done % step == 0


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


@dataclass
class EvalProgressWriter:
    path: Path
    step: int
    meta: dict[str, Any]
    _last_done: int = -1
    _started_at: float | None = None

    @classmethod
    def from_env(
        cls,
        *,
        suite: str,
        model_alias: str,
        litellm_model: str,
    ) -> EvalProgressWriter | None:
        path = progress_file_from_env()
        if path is None:
            return None
        return cls(
            path=path,
            step=progress_step_from_env(),
            meta={
                'suite': suite,
                'model_alias': model_alias,
                'litellm_model': litellm_model,
            },
        )

    def write_started(self, *, total: int) -> None:
        started = time.time()
        self._started_at = started
        _atomic_write(
            self.path,
            {
                **self.meta,
                'status': 'running',
                'done': 0,
                'total': total,
                'item_id': '',
                'started_at': started,
                'ts': started,
            },
        )
        self._last_done = 0

    def write_item(
        self,
        done: int,
        total: int,
        item_id: str,
        row: dict[str, Any],
        *,
        force: bool = False,
    ) -> None:
        if done == self._last_done and not force:
            return
        if not should_write_progress(done, total, step=self.step, force=force):
            return
        _atomic_write(
            self.path,
            {
                **self.meta,
                'status': 'running',
                'done': done,
                'total': total,
                'item_id': item_id,
                'correct': row.get('correct'),
                'error': row.get('error'),
                'ts': time.time(),
            },
        )
        self._last_done = done

    def write_finished(self, *, done: int, total: int, correct: int) -> None:
        finished = time.time()
        started = self._started_at
        elapsed_sec: float | None = None
        if started is not None:
            elapsed_sec = round(finished - started, 2)
        payload: dict[str, Any] = {
            **self.meta,
            'status': 'done',
            'done': done,
            'total': total,
            'correct': correct,
            'item_id': '',
            'ts': finished,
        }
        if started is not None:
            payload['started_at'] = started
        if elapsed_sec is not None:
            payload['elapsed_sec'] = elapsed_sec
        _atomic_write(self.path, payload)
        self._last_done = done

    def write_failed(self, message: str) -> None:
        _atomic_write(
            self.path,
            {
                **self.meta,
                'status': 'failed',
                'error': message,
                'ts': time.time(),
            },
        )


def read_progress_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding='utf-8').strip()
        if not text:
            return None
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
