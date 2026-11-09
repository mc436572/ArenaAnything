from __future__ import annotations

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


def test_eval_requires_suite_and_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_data_dir()
    runner = CliRunner()
    missing_profile = runner.invoke(main, ['eval', '--suite', 'demo'], env=_quiet_env())
    assert missing_profile.exit_code != 0
    missing_suite = runner.invoke(
        main, ['eval', '--with-profile', 'demo-profile'], env=_quiet_env()
    )
    assert missing_suite.exit_code != 0


def test_eval_invokes_runner_with_profile_options(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init_data_dir()
    prof_dir = tmp_path / 'chat-profiles'
    prof_dir.mkdir(exist_ok=True)
    (prof_dir / 'mcq.yaml').write_text(
        'system_prompt: MCQ\nlimit: 1\nmax_tokens: 8\n',
        encoding='utf-8',
    )

    items = [{'id': '1', 'answer': 'A', 'prompt': 'Q'}]
    fake_report = {
        'n': 1,
        'correct': 1,
        'accuracy': 1.0,
        'items': [
            {
                'id': '1',
                'answer': 'A',
                'parsed': 'A',
                'correct': True,
                'latency_ms': 1.0,
            }
        ],
    }

    with patch('ssj.eval_cmd.load_probe_items', return_value=items) as load:
        with patch('ssj.eval_cmd.run_probe_suite', return_value=fake_report) as run:
            with patch('ssj.eval_cmd.write_probe_report', return_value=tmp_path / 'r.json'):
                runner = CliRunner()
                result = runner.invoke(
                    main,
                    ['eval', '-s', 'demo', '--with-profile', 'mcq'],
                    env=_quiet_env(),
                )

    assert result.exit_code == 0, result.output
    load.assert_called_once_with('demo')
    run.assert_called_once()
    kwargs = run.call_args.kwargs
    assert kwargs['system_prompt'] == 'MCQ'
    assert kwargs['max_tokens'] == 8
