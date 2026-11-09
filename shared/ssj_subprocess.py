"""Spawn ssj in an isolated process root (SSJ_ROOT == cwd). See README / arena docs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from shared.ssj_bundle import (
    case_unpack_dir,
    is_bundle_unpack_ready,
    pythonpath_for_bundle,
)
from ssj.model_secrets import all_registered_secret_names

# Must match settings._IGNORED_INHERITED_KEYS subset we clear before child starts.
_SPAWN_STRIP_KEYS = frozenset({'SSJ_ROOT', 'SSJ_DATA_DIR', 'SSJ_MODEL', 'PYTHONPATH'})


def resolve_instance_root(path: Path) -> Path:
    """Absolute process root for one ssj-<profile>/ directory."""
    return path.expanduser().resolve()


def resolve_case_bundle_root(instance_root: Path, *, version: str) -> Path:
    """Frozen ssj code tree: case/<id>/ssj/<version>/ (not the dev install)."""
    case_dir = resolve_instance_root(instance_root).parent
    unpack = case_unpack_dir(case_dir, version)
    if not is_bundle_unpack_ready(unpack):
        raise FileNotFoundError(
            f'Missing or incomplete frozen ssj bundle at {unpack} (run arena init)'
        )
    return unpack


def env_for_instance_root(
    instance_root: Path,
    *,
    bundle_root: Path | None = None,
) -> dict[str, str]:
    """Build subprocess env: no parent SSJ_ROOT/model override; no inherited API keys."""
    root = resolve_instance_root(instance_root)
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in _SPAWN_STRIP_KEYS and k not in all_registered_secret_names()
    }
    env['SSJ_ROOT'] = str(root)
    if bundle_root is not None:
        env['PYTHONPATH'] = pythonpath_for_bundle(bundle_root)
    return env


def assert_instance_ready(instance_root: Path) -> None:
    """Fail fast if materialize did not create a valid process root."""
    root = resolve_instance_root(instance_root)
    if not root.is_dir():
        raise FileNotFoundError(f'Instance root is not a directory: {root}')
    config = root / 'config.yaml'
    if not config.is_file():
        raise FileNotFoundError(f'Missing {config} (run arena init)')


def run_ssj_in_instance(
    instance_root: Path,
    argv: list[str],
    *,
    agent_version: str,
    extra_env: dict[str, str] | None = None,
    capture_output: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run frozen `python -m cli.ssj` from case/ssj/<ver>/; cwd = instance_root."""
    assert_instance_ready(instance_root)
    root = resolve_instance_root(instance_root)
    bundle_root = resolve_case_bundle_root(root, version=agent_version)
    env = env_for_instance_root(root, bundle_root=bundle_root)
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, '-m', 'cli.ssj', *argv]
    return subprocess.run(
        cmd,
        cwd=str(root),
        env=env,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
    )
