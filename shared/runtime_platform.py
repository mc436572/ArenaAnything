"""Supported runtime: Linux / WSL only (arena subprocess + case paths)."""

from __future__ import annotations

import sys


def require_linux_or_wsl() -> None:
    if sys.platform == 'win32':
        raise SystemExit(
            'SSaiyan CLI requires Linux or WSL (not Windows native Python).\n'
            'Open WSL, cd to the repo, then:\n'
            '  source venv_wsl/bin/activate\n'
            '  pip install -r requirements.txt && pip install -e . --no-deps\n'
            '  arena list'
        )
