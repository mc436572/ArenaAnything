"""ssj model CLI。"""

from __future__ import annotations

import os
from pathlib import Path

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


def test_model_list_after_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    setup = runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    assert setup.exit_code == 0, setup.output

    listed = runner.invoke(main, ['model', 'list'], env=_quiet_env())
    assert listed.exit_code == 0, listed.output
    assert 'ds' in listed.output
    assert 'kimi' in listed.output
    assert 'grok' in listed.output
    assert 'jev' in listed.output
    assert 'built-in' in listed.output
    assert 'Keys' in listed.output
    assert 'missing' in listed.output or 'configured' in listed.output

    add = runner.invoke(
        main,
        ['model', 'add', 'ds1017'],
        input='deepseek/deepseek-chat\ncustom\n\nsk-list-test-key\n\n\n',
        env=_quiet_env(),
    )
    assert add.exit_code == 0, add.output

    filt = runner.invoke(main, ['model', 'list', '*1017*'], env=_quiet_env())
    assert filt.exit_code == 0, filt.output
    assert 'ds1017' in filt.output


def test_model_set_can_rotate_key_without_changing_model_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=sk-old-key-value\n', encoding='utf-8')

    result = runner.invoke(
        main,
        ['model', 'set', 'ds'],
        input='\n\nsk-rotated-key-value\n\n',
        env=_quiet_env(),
    )
    assert result.exit_code == 0, result.output
    assert 'saved' in result.output
    assert 'sk-rotated-key-value' in (tmp_path / '.env').read_text(encoding='utf-8')


def test_model_set_skips_existing_key_and_sets_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    (tmp_path / '.env').write_text('MOONSHOT_API_KEY=sk-already-set-key\n', encoding='utf-8')

    result = runner.invoke(
        main,
        ['model', 'set', 'kimi'],
        input='\n\n\n\n',
        env=_quiet_env(),
    )
    assert result.exit_code == 0, result.output
    assert 'kept' in result.output
    assert result.output.count('API base URL') == 1
    assert 'MOONSHOT_API_KEY' in result.output
    assert 'Default model:' in result.output

    dup = runner.invoke(main, ['model', 'add', 'kimi'], env=_quiet_env())
    assert dup.exit_code != 0
    assert 'model set kimi' in dup.output

    missing = runner.invoke(main, ['model', 'add', 'kimi'], env=_quiet_env())
    assert missing.exit_code != 0
    assert 'model set kimi' in missing.output
    assert 'add kimi2' not in missing.output


def test_model_add_prompts_for_litellm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    result = runner.invoke(
        main,
        ['model', 'add', 'ds1017'],
        input='deepseek/deepseek-chat\n\n\nsk-add-test-key\n\n\n',
        env=_quiet_env(),
    )
    assert result.exit_code == 0, result.output
    assert 'ds1017' in result.output


def test_model_set_openrouter_mimo_prompts_base_and_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())
    result = runner.invoke(
        main,
        ['model', 'set', 'mimo'],
        input='\n\nsk-or-mimo-openrouter-test-key\n\n',
        env=_quiet_env(),
    )
    assert result.exit_code == 0, result.output
    assert 'openrouter/xiaomi/mimo-v2.6-flash' in result.output
    assert 'API base URL' in result.output
    assert 'OPENROUTER_API_KEY' in result.output
    assert 'saved' in result.output
    assert 'using default' in result.output
    env_text = (tmp_path / '.env').read_text(encoding='utf-8')
    assert 'OPENROUTER_API_BASE=' not in env_text
    assert 'sk-or-mimo-openrouter-test-key' in env_text


def test_model_set_no_default_when_declined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n', env=_quiet_env())

    result = runner.invoke(
        main,
        ['model', 'set', 'kimi'],
        input='\n\n\nsk-moonshot-test-key\nn\n',
        env=_quiet_env(),
    )
    assert result.exit_code == 0, result.output
    assert 'unchanged' in result.output.lower() or 'Default unchanged' in result.output

    show = runner.invoke(main, ['config', 'show'], env=_quiet_env())
    assert show.exit_code == 0, show.output
    assert 'ds' in show.output
