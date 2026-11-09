from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ssj.model_ping import PingError, ping_openai_compatible


def test_deepseek_ping_builds_correct_url() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        'choices': [{'message': {'content': 'pong'}}],
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'sk-test'}, clear=False):
        with patch('ssj.model_ping.httpx.Client', return_value=mock_client):
            text = ping_openai_compatible('deepseek/deepseek-chat', timeout=5.0)

    assert text == 'pong'
    call = mock_client.post.call_args
    assert call[0][0] == 'https://api.deepseek.com/v1/chat/completions'
    assert call[1]['json']['model'] == 'deepseek-chat'


def test_deepseek_ping_uses_env_api_base() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        'choices': [{'message': {'content': 'pong'}}],
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    env = {
        'DEEPSEEK_API_KEY': 'sk-test',
        'DEEPSEEK_API_BASE': 'https://api.deepseek.com/v1',
    }
    with patch.dict('os.environ', env, clear=True):
        with patch('ssj.model_ping.httpx.Client', return_value=mock_client):
            ping_openai_compatible('deepseek/deepseek-chat', timeout=5.0)

    assert mock_client.post.call_args[0][0] == 'https://api.deepseek.com/v1/chat/completions'


def test_missing_key_raises() -> None:
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(PingError, match='DEEPSEEK_API_KEY'):
            ping_openai_compatible('deepseek/deepseek-chat')
