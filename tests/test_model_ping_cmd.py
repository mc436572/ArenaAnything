from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli.ssj import main


def _quiet_env(**extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {'SSJ_ROOT', 'SSJ_DATA_DIR', 'SSJ_MODEL', 'DEEPSEEK_API_KEY'}
    }
    env['SSJ_SILENT_STARTUP'] = '1'
    env.update(extra)
    return env


def test_ping_default_only_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=sk-test\n', encoding='utf-8')

    with patch('ssj.model_cmd.ping_model', return_value='pong') as ping:
        result = runner.invoke(main, ['model', 'ping', '-t', '2'], env=_quiet_env())

    assert result.exit_code == 0, result.output
    assert ping.call_count == 2
    assert 'ping statistics' in result.output
    assert 'min (s)' in result.output
    assert 'avg (s)' in result.output


def test_ping_without_m_only_default_not_all_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    (tmp_path / '.env').write_text(
        'DEEPSEEK_API_KEY=sk-ds\nMOONSHOT_API_KEY=sk-kimi\n', encoding='utf-8'
    )
    import yaml

    models_path = tmp_path / 'models.yaml'
    data = yaml.safe_load(models_path.read_text(encoding='utf-8'))
    data['default'] = 'kimi'
    models_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')

    with patch('ssj.model_cmd.ping_model', return_value='pong') as ping:
        result = runner.invoke(main, ['model', 'ping'], env=_quiet_env())

    assert result.exit_code == 0, result.output
    assert ping.call_count == 1
    assert ping.call_args[0][0] == data['models']['kimi']['litellm']
    assert 'Ping kimi' in result.output
    assert 'Ping ds' not in result.output


def test_ping_unknown_m_friendly_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())

    result = runner.invoke(main, ['model', 'ping', '-m', 'nope'], env=_quiet_env())
    assert result.exit_code == 1
    assert 'Unknown model' in result.output


def test_ping_m_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=sk-test\n', encoding='utf-8')

    with patch('ssj.model_cmd.ping_model', return_value='pong'):
        result = runner.invoke(main, ['model', 'ping', '-m', 'ds'], env=_quiet_env())

    assert result.exit_code == 0, result.output
    assert 'Ping' in result.output and 'ds' in result.output
