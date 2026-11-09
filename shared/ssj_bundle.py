"""Frozen ssj version bundles (tar.gz): build, extract, launch path (no pip)."""

from __future__ import annotations

import hashlib
import shutil
import tarfile
from collections.abc import Callable
from pathlib import Path

import yaml

BUNDLE_MANIFEST = 'BUNDLE_MANIFEST.yaml'
BUNDLE_FILENAME = 'ssj-{version}.tar.gz'


def bundle_archive_name(version: str) -> str:
    ver = str(version).strip()
    if not ver:
        raise ValueError('agent version must be non-empty')
    return BUNDLE_FILENAME.format(version=ver)


def template_dir(repo_root: Path, line: str, version: str) -> Path:
    return (repo_root / 'templates' / line / version).resolve()


def bundle_archive_path(repo_root: Path, line: str, version: str) -> Path:
    return template_dir(repo_root, line, version) / bundle_archive_name(version)


def case_unpack_dir(case_dir: Path, version: str) -> Path:
    return (case_dir.resolve() / 'ssj' / str(version).strip()).resolve()


def _bundle_marker(unpack_dir: Path) -> Path:
    return unpack_dir / BUNDLE_MANIFEST


def is_bundle_unpack_ready(unpack_dir: Path) -> bool:
    return (
        _bundle_marker(unpack_dir).is_file()
        and (unpack_dir / 'cli' / 'ssj.py').is_file()
        and (unpack_dir / 'ssj').is_dir()
    )


def agent_version_from_case_dir(case_dir: Path) -> tuple[str, str]:
    """Return (line, version) from case/case.yaml."""
    case_yaml = case_dir / 'case.yaml'
    if not case_yaml.is_file():
        raise FileNotFoundError(f'Missing {case_yaml}')
    with case_yaml.open(encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f'Invalid case yaml: {case_yaml}')
    agent = data.get('agent') or {}
    line = str(agent.get('line') or 'ssj').strip() or 'ssj'
    version = str(agent.get('version') or '0.1.0').strip() or '0.1.0'
    return line, version


def extract_bundle_into_case(
    *,
    repo_root: Path,
    case_dir: Path,
    line: str,
    version: str,
    force: bool = False,
    on_extract_progress: Callable[[int, int], None] | None = None,
) -> tuple[Path, bool]:
    """Extract templates/ssj/<ver>/ssj-<ver>.tar.gz → case/<id>/ssj/<ver>/.

    Returns (unpack_dir, extracted_now).
    """
    archive = bundle_archive_path(repo_root, line, version)
    if not archive.is_file():
        raise FileNotFoundError(
            f'Missing frozen bundle {archive.relative_to(repo_root).as_posix()} '
            f'(maintainers rebuild it under templates/ssj/{version}/)'
        )
    dest = case_unpack_dir(case_dir, version)
    if dest.exists() and is_bundle_unpack_ready(dest) and not force:
        return dest, False
    if dest.exists() and force:
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        total = len(members)
        if on_extract_progress and total:
            on_extract_progress(0, total)
        for i, member in enumerate(members, start=1):
            tar.extract(member, path=dest, filter='data')
            if on_extract_progress:
                on_extract_progress(i, total)
        if on_extract_progress and total == 0:
            on_extract_progress(0, 0)
    if not is_bundle_unpack_ready(dest):
        raise ValueError(f'Bundle extract incomplete under {dest}')
    return dest, True


def pythonpath_for_bundle(unpack_dir: Path) -> str:
    root = unpack_dir.resolve()
    return str(root)


# --- build (maintainer-side frozen bundle) ---

_BUNDLE_ITEMS: tuple[tuple[str, str], ...] = (
    ('ssj', 'ssj'),
    ('cli/__init__.py', 'cli/__init__.py'),
    ('cli/ssj.py', 'cli/ssj.py'),
    ('cli/group.py', 'cli/group.py'),
    ('cli/console.py', 'cli/console.py'),
    ('shared/__init__.py', 'shared/__init__.py'),
    ('shared/benchmark_probes.py', 'shared/benchmark_probes.py'),
    ('shared/eval_progress_file.py', 'shared/eval_progress_file.py'),
)

# Byte-code / cache dirs must never enter a published bundle.
_BUNDLE_IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo')


def _is_cache_artifact(rel_posix: str) -> bool:
    parts = rel_posix.split('/')
    return '__pycache__' in parts or rel_posix.endswith(('.pyc', '.pyo'))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def build_bundle_archive(
    *,
    source_root: Path,
    output_archive: Path,
    line: str,
    version: str,
) -> Path:
    """Pack frozen ssj snapshot into ssj-<version>.tar.gz (no pip)."""
    source_root = source_root.resolve()
    output_archive.parent.mkdir(parents=True, exist_ok=True)
    staging = output_archive.parent / f'.staging-{version}'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    manifest_files: list[dict[str, str]] = []
    ssj_src = source_root / 'ssj'
    if not ssj_src.is_dir():
        raise FileNotFoundError(f'Missing source package: {ssj_src}')

    shutil.copytree(ssj_src, staging / 'ssj', dirs_exist_ok=True, ignore=_BUNDLE_IGNORE)

    for src_rel, dest_rel in _BUNDLE_ITEMS:
        if dest_rel == 'ssj':
            continue
        src = source_root / src_rel
        if not src.is_file():
            raise FileNotFoundError(f'Bundle source missing: {src}')
        dest = staging / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    for rel in staging.rglob('*'):
        rel_posix = rel.relative_to(staging).as_posix()
        if _is_cache_artifact(rel_posix):
            if rel.is_file():
                rel.unlink()
            continue
        if rel.is_file() and rel.name != BUNDLE_MANIFEST:
            manifest_files.append(
                {
                    'path': rel_posix,
                    'sha256': _sha256_file(rel),
                }
            )

    manifest = {
        'line': line,
        'version': version,
        'format': 'ssj-bundle-v1',
        'files': sorted(manifest_files, key=lambda x: x['path']),
    }
    manifest_path = staging / BUNDLE_MANIFEST
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding='utf-8',
    )

    if output_archive.is_file():
        output_archive.unlink()
    with tarfile.open(output_archive, 'w:gz') as tar:
        for item in sorted(staging.rglob('*')):
            if not item.is_file():
                continue
            arc = item.relative_to(staging).as_posix()
            if _is_cache_artifact(arc):
                continue
            tar.add(item, arcname=arc)

    shutil.rmtree(staging)
    return output_archive.resolve()
