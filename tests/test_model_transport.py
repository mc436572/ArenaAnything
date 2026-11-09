from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ssj.model_ping import PingError, ping_model
from ssj.model_transport import (
    assemble_systemone_body,
    build_choice_question,
    build_noul_question,
    build_systemone_state,
    decisions_payload_model,
    decisions_url,
    format_jev_binary_answer,
    jev_binary_decision_from_text,
    probe_item_via_decisions,
    resolve_transport,
)
from ssj.probe_runner import run_probe_suite


def test_systemone_body_shape_matches_docs() -> None:
    body = assemble_systemone_body(
        'typesafe/jev-latest',
        state=build_systemone_state('listing text', system_prompt='You are a grader.'),
        questions={
            **build_noul_question(
                'ok',
                instructions='Is it ok?',
                true_label='yes',
                false_label='no',
            ),
            **build_choice_question(
                'pick',
                instructions='Pick one',
                criteria={'A': 'first', 'B': 'second'},
            ),
        },
    )
    assert body['model'] == 'jev-latest'
    assert body['state'] == ['You are a grader.', 'listing text']
    assert body['questions']['ok']['type'] == 'noul'
    assert set(body['questions']['ok']['criteria']) == {'true', 'false'}
    assert body['questions']['pick']['type'] == 'choice'
    assert body['questions']['pick']['criteria']['A'] == 'first'


def test_resolve_transport_jev_openrouter() -> None:
    t = resolve_transport('openrouter/typesafe/jev-1.13')
    assert t.kind == 'decisions'
    assert t.rule is not None
    assert t.rule.api_root_kind == 'openrouter'


def test_resolve_transport_chat_default() -> None:
    assert resolve_transport('deepseek/deepseek-chat').kind == 'chat_openai'


def test_typesafe_systemone_model_maps_short_tags() -> None:
    rule = resolve_transport('typesafe/jev-1.13').rule
    assert rule is not None
    assert decisions_payload_model('typesafe/jev-1.13', rule) == 'jev-latest'
    assert decisions_payload_model('typesafe/jev-latest', rule) == 'jev-latest'


def test_openrouter_decisions_model_keeps_typesafe_prefix() -> None:
    rule = resolve_transport('openrouter/typesafe/jev-1.13').rule
    assert rule is not None
    assert decisions_payload_model('openrouter/typesafe/jev-1.13', rule) == 'typesafe/jev-1.13'


def test_decisions_url_strips_openrouter_v1() -> None:
    t = resolve_transport('openrouter/typesafe/jev-latest')
    assert t.rule is not None
    with patch.dict(
        'os.environ',
        {'OPENROUTER_API_BASE': 'https://openrouter.ai/api/v1'},
        clear=False,
    ):
        from ssj.provider_routing import resolved_api_root

        _ = resolved_api_root('openrouter/typesafe/jev-latest')
        url = decisions_url('openrouter/typesafe/jev-latest', t.rule)
    assert url == 'https://openrouter.ai/api/alpha/decisions'


def test_format_jev_binary_answer_noul() -> None:
    assert format_jev_binary_answer({'answers': {'binary_judgment': {'noul': 0.91}}}) == '是（noul=0.9100）'
    assert format_jev_binary_answer({'answers': {'binary_judgment': {'noul': 0.2}}}) == '否（noul=0.2000）'


def test_jev_binary_decision_from_text() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {'answers': {'binary_judgment': {'noul': 0.88}}}
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch.dict('os.environ', {'TYPESAFE_API_KEY': 'api-test'}, clear=False):
        with patch('ssj.model_transport.httpx.Client', return_value=mock_client):
            text, raw = jev_binary_decision_from_text(
                'typesafe/jev-latest',
                '注册会计师可以签字吗？',
                timeout=5.0,
            )
    assert '是' in text
    body = mock_client.post.call_args[1]['json']
    assert '注册会计师' in body['state'][-1]
    assert body['questions']['binary_judgment']['type'] == 'noul'
    assert raw['answers']['binary_judgment']['noul'] == 0.88


def test_ping_jev_posts_decisions() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {'answers': {'ping_ok': {'noul': 0.91}}}
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'sk-or-test'}, clear=False):
        with patch('ssj.model_transport.httpx.Client', return_value=mock_client):
            text = ping_model('openrouter/typesafe/jev-1.13', timeout=5.0)

    assert text == 'noul=0.9100'
    call = mock_client.post.call_args
    assert call[0][0] == 'https://openrouter.ai/api/alpha/decisions'
    body = call[1]['json']
    assert body['model'] == 'typesafe/jev-1.13'
    assert body['questions']['ping_ok']['type'] == 'noul'


def test_probe_item_choice() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        'answers': {
            'answer': {
                'choice': 'C',
                'probabilities': {'A': 0.1, 'B': 0.2, 'C': 0.6, 'D': 0.1},
            },
        },
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    item = {
        'id': 'q1',
        'answer': 'C',
        'prompt': 'Pick one',
        'choices': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd'},
    }
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'sk-or-test'}, clear=False):
        with patch('ssj.model_transport.httpx.Client', return_value=mock_client):
            reply = probe_item_via_decisions('openrouter/typesafe/jev-1.13', item, timeout=5.0)
    assert reply == 'C'


def test_run_probe_suite_jev_uses_decisions() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        'answers': {'answer': {'choice': 'A', 'probabilities': {'A': 0.9}}},
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    items = [
        {
            'id': 'a',
            'answer': 'A',
            'prompt': 'Q',
            'choices': {'A': '1', 'B': '2'},
        },
    ]
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'sk-or-test'}, clear=False):
        with patch('ssj.model_transport.httpx.Client', return_value=mock_client):
            report = run_probe_suite(items, 'openrouter/typesafe/jev-1.13')
    assert report['correct'] == 1
    assert report['items'][0]['parsed'] == 'A'


def test_probe_item_requires_choices() -> None:
    with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'sk-or-test'}, clear=False):
        with pytest.raises(PingError, match='choices'):
            probe_item_via_decisions(
                'openrouter/typesafe/jev-1.13',
                {'id': 'x', 'prompt': 'p'},
            )
