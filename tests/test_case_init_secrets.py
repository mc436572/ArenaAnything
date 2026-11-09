from __future__ import annotations

from pathlib import Path

import yaml

from shared.case_catalog import add_case
from shared.case_secrets import SecretsPoolError
from shared.ssj_bundle import build_bundle_archive, bundle_archive_path


def _minimal_repo(tmp_path: Path) -> Path:
    repo = tmp_path / 'repo'
    (repo / 'benchmark').mkdir(parents=True)
    (repo / 'benchmark' / 'manifest.yaml').write_text('suites: {}\n', encoding='utf-8')
    tpl_ssj = repo / 'templates' / 'ssj' / '0.1.0'
    tpl_ssj.mkdir(parents=True)
    for name, body in (
        ('config.yaml', 'profile: dev\n'),
        ('models.yaml', 'default: ds\nmodels:\n  ds:\n    litellm: deepseek/deepseek-chat\n'),
        ('AGENT_VERSION.yaml', 'version: "0.1.0"\n'),
        ('README.md', 'r\n'),
        ('.env.example', '# ex\n'),
    ):
        (tpl_ssj / name).write_text(body, encoding='utf-8')
    (tpl_ssj / 'chat-profiles').mkdir()
    (tpl_ssj / 'chat-profiles' / 'demo-profile.yaml').write_text('name: demo\n', encoding='utf-8')
    real = Path(__file__).resolve().parents[1]
    build_bundle_archive(
        source_root=real,
        output_archive=bundle_archive_path(repo, 'ssj', '0.1.0'),
        line='ssj',
        version='0.1.0',
    )
    profiles = repo / 'templates' / 'case'
    profiles.mkdir(parents=True)
    (profiles / 'key-case.yaml').write_text(
        yaml.safe_dump(
            {
                'case_id': 'key-case',
                'title': 'Keys',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
            }
        ),
        encoding='utf-8',
    )
    return repo


def test_init_applies_keys_from_repo_pool(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / '.env').write_text(
        'DEEPSEEK_API_KEY=sk-pool-test\n'
        'DEEPSEEK_API_BASE=https://custom.deepseek.example/v1\n',
        encoding='utf-8',
    )
    case_dir = add_case('key-case', repo_root=repo, apply_keys=True)
    env = case_dir / 'ssj-ds' / '.env'
    assert env.is_file()
    text = env.read_text(encoding='utf-8')
    assert 'sk-pool-test' in text
    assert 'custom.deepseek.example' in text


def test_init_no_key_skips_env(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / '.env').write_text('DEEPSEEK_API_KEY=sk-pool-test\n', encoding='utf-8')
    case_dir = add_case('key-case', repo_root=repo, apply_keys=False)
    assert not (case_dir / 'ssj-ds' / '.env').is_file()


def test_init_without_pool_fails_when_apply_keys(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    try:
        add_case('key-case', repo_root=repo, apply_keys=True)
    except SecretsPoolError:
        return
    raise AssertionError('expected SecretsPoolError')


def test_init_ping_all_profiles(tmp_path: Path, monkeypatch) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / '.env').write_text('DEEPSEEK_API_KEY=sk-pool-test\n', encoding='utf-8')
    calls: list = []

    class P:
        returncode = 0
        stdout = 'pong'
        stderr = ''

    def fake_run(instance_root, argv, **kwargs):
        calls.append((instance_root.name, argv))
        return P()

    monkeypatch.setattr('shared.ssj_subprocess.run_ssj_in_instance', fake_run)
    add_case('key-case', repo_root=repo, apply_keys=True)
    from shared.case_init_ping import ping_case_profiles

    case_dir = repo / 'case' / 'key-case'
    rows = ping_case_profiles(
        case_dir=case_dir,
        agent_line='ssj',
        agent_version='0.1.0',
        profiles=['ds'],
    )
    assert rows[0].ok
    assert calls[0][1] == ['model', 'ping']


def test_rebuild_wipes_reports_and_reapplies_keys(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    (repo / '.env').write_text('DEEPSEEK_API_KEY=sk-first\n', encoding='utf-8')
    case_dir = add_case('key-case', repo_root=repo, apply_keys=True)
    marker = case_dir / 'reports' / 'ds' / 'old.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{}', encoding='utf-8')
    (repo / '.env').write_text('DEEPSEEK_API_KEY=sk-second\n', encoding='utf-8')
    case_dir = add_case('key-case', repo_root=repo, apply_keys=True, rebuild=True)
    assert not marker.exists()
    assert 'sk-second' in (case_dir / 'ssj-ds' / '.env').read_text(encoding='utf-8')
