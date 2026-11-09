from __future__ import annotations

from shared.eval_progress_file import should_write_progress


def test_should_write_first_last_and_step() -> None:
    step = 5
    assert should_write_progress(1, 30, step=step)
    assert should_write_progress(30, 30, step=step)
    assert should_write_progress(5, 30, step=step)
    assert should_write_progress(10, 30, step=step)
    assert not should_write_progress(3, 30, step=step)
    assert should_write_progress(3, 30, step=step, force=True)
