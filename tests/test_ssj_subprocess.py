from __future__ import annotations

from pathlib import Path

from shared.case_workspace import init_case_workspace
from shared.ssj_subprocess import env_for_instance_root, resolve_instance_root, run_ssj_in_instance
import yaml


def test_env_ssj_root_matches_resolved_root(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'spawn-case'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'spawn-case',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
                'eval': {'profile': 'demo-profile'},
            }
        ),
        encoding='utf-8',
    )
    init_case_workspace(case_yaml, repo_root=repo)
    ds_root = case_dir / 'ssj-ds'
    resolved = resolve_instance_root(ds_root)
    env = env_for_instance_root(ds_root)
    assert env['SSJ_ROOT'] == str(resolved)
    assert 'DEEPSEEK_API_KEY' not in env


def test_run_ssj_uses_cwd_and_ssj_root(tmp_path: Path, monkeypatch) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'spawn-run'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'spawn-run',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
                'eval': {'profile': 'demo-profile'},
            }
        ),
        encoding='utf-8',
    )
    init_case_workspace(case_yaml, repo_root=repo)
    ds_root = resolve_instance_root(case_dir / 'ssj-ds')
    captured: dict = {}

    def fake_run(cmd, cwd, env, **kwargs):
        captured['cwd'] = cwd
        captured['env_root'] = env.get('SSJ_ROOT')
        captured['pythonpath'] = env.get('PYTHONPATH')
        class P:
            returncode = 0
            stdout = ''
            stderr = ''

        return P()

    monkeypatch.setattr('shared.ssj_subprocess.subprocess.run', fake_run)
    run_ssj_in_instance(ds_root, ['--help'], agent_version='0.1.0')
    assert captured['cwd'] == str(ds_root)
    assert captured['env_root'] == str(ds_root)
    assert captured['pythonpath']
    assert 'ssj' in captured['pythonpath'] and '0.1.0' in captured['pythonpath']
