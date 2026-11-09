from __future__ import annotations

from ssj.model_reply import parse_choice_letter
from ssj.probe_runner import run_probe_suite, score_item


def test_parse_letter_variants() -> None:
    assert parse_choice_letter('C') == 'C'
    assert parse_choice_letter('答案：b') == 'B'
    assert parse_choice_letter('The answer is D.') == 'D'
    assert parse_choice_letter('[B]') == 'B'
    assert parse_choice_letter('最终答案：[c]') == 'C'
    assert parse_choice_letter('') is None
    assert parse_choice_letter('不知道') is None


def test_score_item_wrong_on_parse_miss() -> None:
    row = score_item({'id': 'q1', 'answer': 'A'}, '也许是第一个')
    assert row['correct'] is False
    assert row['parsed'] is None


def test_score_item_one_zero() -> None:
    item = {'id': 'y1', 'parse': 'one_zero', 'answer': '1'}
    assert score_item(item, '1', litellm_model='deepseek/deepseek-chat')['correct'] is True
    assert score_item(item, '答案：0', litellm_model='deepseek/deepseek-chat')['correct'] is False


def test_run_probe_suite_keeps_order_and_counts_errors() -> None:
    replies = iter(['C', '', 'A'])

    def complete(model: str, messages: list[dict[str, str]], **kwargs: object) -> str:
        assert model == 'deepseek/deepseek-chat'
        text = next(replies)
        if text == '':
            from ssj.model_ping import PingError

            raise PingError('boom')
        return text

    items = [
        {'id': 'a', 'answer': 'C', 'prompt': 'one'},
        {'id': 'b', 'answer': 'B', 'prompt': 'two'},
        {'id': 'c', 'answer': 'D', 'prompt': 'three'},
    ]
    report = run_probe_suite(items, 'deepseek/deepseek-chat', complete=complete)
    assert [row['id'] for row in report['items']] == ['a', 'b', 'c']
    assert report['correct'] == 1
    assert report['n'] == 3
    assert report['items'][1]['error'] == 'boom'
    assert report['items'][2]['correct'] is False


def test_run_probe_suite_progress_callback() -> None:
    seen: list[tuple[int, int, str]] = []

    def complete(model: str, messages: list[dict[str, str]], **kwargs: object) -> str:
        return 'A'

    def on_progress(done: int, total: int, item_id: str, row: dict) -> None:
        seen.append((done, total, item_id))

    items = [
        {'id': 'x1', 'answer': 'A', 'prompt': 'one'},
        {'id': 'x2', 'answer': 'B', 'prompt': 'two'},
    ]
    run_probe_suite(
        items,
        'deepseek/deepseek-chat',
        complete=complete,
        on_progress=on_progress,
    )
    assert seen == [(1, 2, 'x1'), (2, 2, 'x2')]
