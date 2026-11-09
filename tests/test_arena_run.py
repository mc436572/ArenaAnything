from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from shared.arena_runner import run_case_matrix
from shared.case_workspace import init_case_workspace


def test_run_matrix_mock_eval(tmp_path: Path, monkeypatch) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'run-case'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'run-case',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
                'eval': {'profile': 'demo-profile'},
                'run': {
                    'temperature': 0.25,
                    'timeout_sec': 45,
                    'probe_limit': 7,
                },
                'output': {'reports_dir': 'reports'},
            }
        ),
        encoding='utf-8',
    )
    init_case_workspace(case_yaml, repo_root=repo)
    ds_root = case_dir / 'ssj-ds'
    (ds_root / '.env').write_text('DEEPSEEK_API_KEY=sk-test-key\n', encoding='utf-8')

    fake_report = ds_root / 'reports' / 'eval-demo-ds-20260101T000000Z.json'
    fake_report.parent.mkdir(parents=True, exist_ok=True)
    fake_report.write_text('{"suite":"demo","n":1,"correct":1,"accuracy":1.0}\n', encoding='utf-8')

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = 'ok'
    mock_proc.stderr = ''

    captured_env: dict[str, str] = {}

    def _capture_run(*_args, **kwargs):
        captured_env.update(kwargs.get('env') or {})
        return mock_proc

    with patch('shared.ssj_subprocess.subprocess.run', side_effect=_capture_run):
        with patch(
            'shared.arena_runner._latest_eval_report',
            return_value=fake_report,
        ):
            results = run_case_matrix(case_yaml, repo_root=repo)

    assert captured_env.get('SSJ_EVAL_TEMPERATURE') == '0.25'
    assert float(captured_env['SSJ_EVAL_TIMEOUT']) == 45
    assert captured_env.get('SSJ_EVAL_PROBE_LIMIT') == '7'

    assert len(results) == 1
    assert results[0].exit_code == 0
    assert results[0].report_dest is not None
    assert results[0].report_dest.is_file()
