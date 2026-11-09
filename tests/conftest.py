"""Shared pytest helpers for ArenaAnything."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.ssj_bundle import build_bundle_archive, bundle_archive_path

REAL_REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session', autouse=True)
def _ensure_real_repo_ssj_bundle() -> None:
    ensure_ssj_bundle(REAL_REPO)


def ensure_ssj_bundle(
    repo_root: Path,
    *,
    line: str = 'ssj',
    version: str = '0.1.0',
) -> Path:
    """Ensure templates/ssj/<ver>/ssj-<ver>.tar.gz exists (build from dev tree if needed)."""
    archive = bundle_archive_path(repo_root, line, version)
    if archive.is_file():
        return archive
    build_bundle_archive(
        source_root=REAL_REPO,
        output_archive=archive,
        line=line,
        version=version,
    )
    return archive
