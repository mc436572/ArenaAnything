from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cli.ssj import main
from ssj.settings import init_data_dir


def _quiet_env(**extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {'SSJ_ROOT', 'SSJ_DATA_DIR', 'SSJ_MODEL', 'DEEPSEEK_API_KEY'}
    }
    env['SSJ_SILENT_STARTUP'] = '1'
    env.update(extra)
    return env


def test_chat_writes_session_and_trace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_data_dir()
    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=sk-test\n', encoding='utf-8')

    def fake_raw(model, messages, **kwargs):
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == 'Be brief.'
        assert messages[1]['role'] == 'user'
        return 'ok', {'choices': [{'message': {'content': 'ok'}}]}

    with patch('ssj.chat_cmd.chat_openai_compatible_raw', side_effect=fake_raw):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                'chat',
                '--text',
                'hello',
                '--system-prompt',
                'Be brief.',
            ],
            env=_quiet_env(),
        )

    assert result.exit_code == 0, result.output
    assert result.output.strip() == 'ok'

    session_files = list((tmp_path / 'session').glob('*.jsonl'))
    assert len(session_files) == 1
    lines = session_files[0].read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 2
    user_row = json.loads(lines[0])
    assert user_row['system_prompt'] == 'Be brief.'

    traces = list((tmp_path / 'traces').glob('chat-*.json'))
    assert len(traces) == 1


def test_chat_with_profile_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_data_dir()
    prof_dir = tmp_path / 'chat-profiles'
    prof_dir.mkdir(exist_ok=True)
    (prof_dir / 'ctx.yaml').write_text(
        'with_context: true\nsystem_prompt: S\n',
        encoding='utf-8',
    )

    def fake_raw(model, messages, **kwargs):
        assert messages[0]['content'] == 'S'
        assert kwargs['max_tokens'] == 4096
        return 'p', {'choices': [{'message': {'content': 'p'}}]}

    with patch('ssj.chat_cmd.chat_openai_compatible_raw', side_effect=fake_raw):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ['chat', '--with-profile', 'ctx', '--text', 'x'],
            env=_quiet_env(),
        )

    assert result.exit_code == 0, result.output
    assert (tmp_path / 'session' / '.active_global').is_file()


def test_chat_jev_binary_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_data_dir()
    (tmp_path / 'models.yaml').write_text(
        'default: jev\nmodels:\n  jev:\n    litellm: typesafe/jev-latest\n',
        encoding='utf-8',
    )
    (tmp_path / '.env').write_text('TYPESAFE_API_KEY=api-test\n', encoding='utf-8')

    with patch(
        'ssj.chat_cmd.jev_binary_decision_from_text',
        return_value=('是（noul=0.9100）', {'answers': {'binary_judgment': {'noul': 0.91}}}),
    ):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ['chat', '--text', '这是连通性测试吗？'],
            env=_quiet_env(),
        )

    assert result.exit_code == 0, result.output
    assert '是' in result.output
    assert 'JEV 二元问答' in result.output
