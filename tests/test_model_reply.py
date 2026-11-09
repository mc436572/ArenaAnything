from ssj.model_reply import (
    extract_chat_reply_text,
    extract_openrouter_reasoning_fallback,
    parse_mimo_mcq,
    parse_mcq_choice,
    resolve_choice_parser,
    resolve_reply_extractor,
)


def test_extract_content_only():
    data = {'choices': [{'message': {'content': '  hello  '}}]}
    assert extract_chat_reply_text('openrouter/deepseek/deepseek-chat', data) == 'hello'


def test_mimo_reasoning_fallback():
    data = {
        'choices': [
            {
                'message': {
                    'content': '',
                    'reasoning': 'think…\n最终 [B]',
                },
            },
        ],
    }
    assert extract_chat_reply_text('openrouter/xiaomi/mimo-v2.6-flash', data) == 'think…\n最终 [B]'
    assert extract_openrouter_reasoning_fallback(data) == 'think…\n最终 [B]'


def test_mimo_prefers_content():
    data = {'choices': [{'message': {'content': '[C]', 'reasoning': 'long'}}]}
    assert extract_chat_reply_text('openrouter/xiaomi/mimo-v2.6-flash', data) == '[C]'


def test_parse_mimo_tail():
    long_reason = '…' * 20 + '\n答案：[D]'
    assert parse_mimo_mcq(long_reason) == 'D'
    assert parse_mcq_choice('openrouter/xiaomi/mimo-v2.6-flash', '[A]') == 'A'


def test_longest_prefix_wins():
    assert resolve_reply_extractor('openrouter/xiaomi/mimo-x').__name__ == 'extract_openrouter_reasoning_fallback'
    assert resolve_choice_parser('openrouter/xiaomi/mimo-x').__name__ == 'parse_mimo_mcq'
    assert resolve_reply_extractor('typesafe/jev-latest').__name__ == 'extract_content_only'
