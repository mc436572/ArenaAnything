from __future__ import annotations

from unittest.mock import MagicMock, patch

from ssj.model_chat_params import effective_chat_temperature
from ssj.model_ping import chat_openai_compatible


def test_effective_temperature_kimi_k3_forces_one() -> None:
    assert effective_chat_temperature('moonshot/kimi-k3', 0) == 1.0
    assert effective_chat_temperature('moonshot/kimi-k3', None) == 1.0
    assert effective_chat_temperature('MOONSHOT/KIMI-K3', 0.2) == 1.0


def test_effective_temperature_other_models_unchanged() -> None:
    assert effective_chat_temperature('deepseek/deepseek-chat', 0) == 0
    assert effective_chat_temperature('moonshot/kimi-k2-turbo-preview', 0) == 0
    assert effective_chat_temperature('deepseek/deepseek-chat', None) is None


def test_kimi_k3_chat_payload_uses_temperature_one() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        'choices': [{'message': {'content': 'A'}}],
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch.dict('os.environ', {'MOONSHOT_API_KEY': 'sk-test'}, clear=False):
        with patch('ssj.model_ping.httpx.Client', return_value=mock_client):
            chat_openai_compatible(
                'moonshot/kimi-k3',
                [{'role': 'user', 'content': 'hi'}],
                temperature=0,
            )

    payload = mock_client.post.call_args[1]['json']
    assert payload['temperature'] == 1.0
