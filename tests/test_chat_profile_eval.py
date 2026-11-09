from __future__ import annotations

from pathlib import Path

import pytest

from ssj.chat_profile import load_eval_profile


def test_load_eval_profile_defaults_max_tokens(tmp_path: Path) -> None:
    path = tmp_path / 'e.yaml'
    path.write_text('limit: 2\n', encoding='utf-8')
    opts = load_eval_profile(path)
    assert opts.limit == 2
    assert opts.max_tokens == 16


def test_rejects_suite_in_eval_profile(tmp_path: Path) -> None:
    path = tmp_path / 'bad.yaml'
    path.write_text('suite: demo\n', encoding='utf-8')
    with pytest.raises(ValueError, match='must not include "suite"'):
        load_eval_profile(path)
