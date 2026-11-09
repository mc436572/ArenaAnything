from __future__ import annotations

from pathlib import Path

import pytest

from shared.release_sanitize import assert_release_tree_clean


def test_sanitize_flags_sk_key(tmp_path: Path) -> None:
    bad = tmp_path / 'ssj' / 'leak.py'
    bad.parent.mkdir(parents=True)
    # Obviously fake placeholder: matches the sanitizer regex, not a real credential.
    fake = 'sk-' + '0' * 24
    bad.write_text(f'x = "{fake}"\n', encoding='utf-8')
    with pytest.raises(ValueError, match='sanitize failed'):
        assert_release_tree_clean(tmp_path / 'ssj')


def test_sanitize_clean_dir(tmp_path: Path) -> None:
    ok = tmp_path / 'ssj' / 'ok.py'
    ok.parent.mkdir(parents=True)
    ok.write_text('# no secrets\n', encoding='utf-8')
    assert_release_tree_clean(tmp_path / 'ssj')
