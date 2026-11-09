"""Scan paths for accidental secrets before ssj release bundle."""

from __future__ import annotations

import re
from pathlib import Path

# Conservative patterns — fail release if matched in staged sources.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'\bsk-[A-Za-z0-9]{10,}\b'), 'OpenAI/DeepSeek-style sk- key'),
    (
        re.compile(r'\bapi[_-]?key\s*=\s*(["\'])(?!\1).{8,}\1', re.I),
        'inline api_key string literal',
    ),
    (re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'), 'PEM private key'),
)

_SKIP_DIR_NAMES = frozenset(
    {
        'venv_wsl',
        '.venv',
        'case',
        '__pycache__',
        '.git',
        '.pytest_cache',
        'node_modules',
    }
)

_SKIP_SUFFIXES = frozenset({'.pyc', '.tar.gz', '.egg-info'})


def _should_scan(path: Path) -> bool:
    if any(part in _SKIP_DIR_NAMES for part in path.parts):
        return False
    name = path.name
    if name == '.env' or name.startswith('.env.'):
        return False
    for suf in _SKIP_SUFFIXES:
        if name.endswith(suf):
            return False
    return path.is_file()


def scan_tree_for_secrets(root: Path) -> list[str]:
    """Return human-readable violations (empty if clean)."""
    root = root.resolve()
    violations: list[str] = []
    for path in root.rglob('*'):
        if not _should_scan(path):
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for pattern, label in _SECRET_PATTERNS:
            if pattern.search(text):
                violations.append(f'{rel}: possible {label}')
    return violations


def assert_release_tree_clean(source_root: Path) -> None:
    hits = scan_tree_for_secrets(source_root)
    if hits:
        sample = '\n  '.join(hits[:20])
        extra = f'\n  ... and {len(hits) - 20} more' if len(hits) > 20 else ''
        raise ValueError(
            'Release sanitize failed — remove secrets before freeze:\n  '
            f'{sample}{extra}'
        )
