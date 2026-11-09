"""进程根：工作目录、SSJ_ROOT、config.yaml 必须一致。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli.ssj import main
from ssj.settings import (
    RootMismatchError,
    init_data_dir,
    load_settings,
    mask_edges,
    resolve_root,
    set_env_key,
)


def _quiet_env(**extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {'SSJ_ROOT', 'SSJ_DATA_DIR', 'SSJ_MODEL', 'DEEPSEEK_API_KEY'}
    }
    env['SSJ_SILENT_STARTUP'] = '1'
    env.update(extra)
    return env


def test_manual_root_is_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('SSJ_ROOT', raising=False)
    assert resolve_root() == tmp_path.resolve()


def test_ssj_root_must_match_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    other = tmp_path / 'elsewhere'
    other.mkdir()
    monkeypatch.setenv('SSJ_ROOT', str(other))
    with pytest.raises(RootMismatchError):
        resolve_root()


def test_init_writes_only_inside_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('SSJ_ROOT', raising=False)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'from-parent')
    monkeypatch.setenv('SSJ_MODEL', 'parent-model')

    settings = init_data_dir()

    assert settings.data_dir == tmp_path.resolve()
    assert (tmp_path / 'config.yaml').is_file()
    assert (tmp_path / '.env.example').is_file()
    assert (tmp_path / 'traces').is_dir()
    assert not (tmp_path / 'inbox').exists()
    assert settings.model == 'deepseek/deepseek-chat'
    assert settings.model_alias == 'ds'
    assert (tmp_path / 'models.yaml').is_file()
    assert os.environ.get('DEEPSEEK_API_KEY') is None


def test_env_file_in_root_supplies_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('SSJ_ROOT', raising=False)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'from-parent')
    (tmp_path / 'config.yaml').write_text('model: from-file\n', encoding='utf-8')
    (tmp_path / '.env').write_text('DEEPSEEK_API_KEY=from-file-key\n', encoding='utf-8')

    settings = load_settings()

    assert settings.model == 'from-file'
    assert settings.model_alias in {'main', 'legacy'}
    assert os.environ['DEEPSEEK_API_KEY'] == 'from-file-key'


def test_config_symlink_outside_root_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / 'agent'
    outside = tmp_path / 'other'
    root.mkdir()
    outside.mkdir()
    (outside / 'config.yaml').write_text('model: other\n', encoding='utf-8')
    (root / 'config.yaml').symlink_to(outside / 'config.yaml')
    monkeypatch.chdir(root)
    monkeypatch.delenv('SSJ_ROOT', raising=False)

    with pytest.raises(RootMismatchError):
        load_settings()


def test_cli_setup_creates_tree_and_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    secret = 'sk-tree-init-key-123456789'
    with patch('ssj.model_ping.ping_model', return_value='pong'):
        setup = runner.invoke(main, ['setup'], input=f'\n\n\n{secret}\n', env=_quiet_env())
    assert setup.exit_code == 0, setup.output
    assert (tmp_path / 'config.yaml').is_file()
    assert not (tmp_path / 'inbox').exists()

    show = runner.invoke(main, ['config', 'show'], env=_quiet_env())
    assert show.exit_code == 0, show.output
    assert 'deepseek/deepseek-chat' in show.output


def test_cli_set_hides_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    secret = 'sk-test-secret-value'
    runner = CliRunner()
    runner.invoke(main, ['setup'], input='\n\n\n', env=_quiet_env())

    result = runner.invoke(
        main,
        ['model', 'set', 'ds'],
        input=f'\n\n{secret}\n\n',
        env=_quiet_env(),
    )
    assert result.exit_code == 0, result.output
    assert secret not in result.output

    stored = (tmp_path / '.env').read_text(encoding='utf-8').replace('"', '').replace("'", '')
    assert f'DEEPSEEK_API_KEY={secret}' in stored

    show = runner.invoke(main, ['config', 'show'], env=_quiet_env())
    assert show.exit_code == 0, show.output
    assert secret not in show.output
    assert '(required, not set)' not in show.output


def test_mask_edges_shows_five_characters_each_side() -> None:
    assert mask_edges('sk-test-secret-value') == 'sk-te**********value'
    assert mask_edges('short') == '*****'


def test_set_env_key_rejects_bad_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('SSJ_ROOT', raising=False)
    with pytest.raises(ValueError):
        set_env_key('NOT A KEY', 'x')


def test_cli_setup_writes_model_and_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    secret = 'sk-setup-test-key-12345'
    runner = CliRunner()
    with patch('ssj.model_ping.ping_model', return_value='pong'):
        result = runner.invoke(
            main,
            ['setup'],
            input=f'\n\n\n{secret}\n',
            env=_quiet_env(),
        )
    assert result.exit_code == 0, result.output
    models_text = (tmp_path / 'models.yaml').read_text(encoding='utf-8')
    assert 'ds' in models_text
    assert 'deepseek/deepseek-chat' in models_text
    example = (tmp_path / '.env.example').read_text(encoding='utf-8')
    assert 'DEEPSEEK_API_KEY=' in example
    show = runner.invoke(main, ['config', 'show'], env=_quiet_env())
    assert show.exit_code == 0
    assert 'DEEPSEEK_API_KEY' in show.output


def test_cli_help_accepts_h_flag() -> None:
    runner = CliRunner()
    root = runner.invoke(main, ['-h'], env=_quiet_env())
    assert root.exit_code == 0
    assert 'Usage:' in root.output
    assert 'This is ssj' not in root.output
    assert 'setup' in root.output
    assert 'config show' in root.output
    assert 'model list' in root.output
    assert 'model set' in root.output
    assert 'config show' in root.output

    cfg = runner.invoke(main, ['config', '-h'], env=_quiet_env())
    assert cfg.exit_code == 0
    assert 'show' in cfg.output
    assert 'init' not in cfg.output

    setup = runner.invoke(main, ['setup', '-h'], env=_quiet_env())
    assert setup.exit_code == 0
    assert 'setup' in setup.output.lower() or 'Interactive' in setup.output


def test_cli_refuses_mismatched_ssj_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ['config', 'show'],
        env=_quiet_env(SSJ_ROOT=str(tmp_path / 'not-here')),
    )
    assert result.exit_code == 1
    assert 'differ' in result.output
