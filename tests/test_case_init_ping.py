from __future__ import annotations

from shared.case_init_ping import success_ping_detail, summarize_ping_log


def test_summarize_ping_log_skips_rich_box_lines() -> None:
    log = "╭─ ok ─╮\nmodel ping OK: deepseek-chat\n╰───────╯"
    assert summarize_ping_log(log) == 'model ping OK: deepseek-chat'


def test_success_ping_detail_uses_latency_not_pong() -> None:
    log = "  #1: ok (0.412s) — pong\n- pong\n- noul=0.9100"
    assert success_ping_detail(log) == '0.412s'


def test_summarize_ping_log_ignores_pong_and_noul() -> None:
    assert summarize_ping_log("- pong\n- noul=0.9100\n") == 'no output'
