from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shared.case_catalog import add_case, delete_case, list_case_catalog, resolve_case_yaml
from shared.ssj_bundle import build_bundle_archive, bundle_archive_path

_REPO = Path(__file__).resolve().parents[1]


def test_add_materializes_from_profile(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    (repo / 'benchmark').mkdir(parents=True)
    (repo / 'benchmark' / 'manifest.yaml').write_text('suites: {}\n', encoding='utf-8')
    tpl_ssj = repo / 'templates' / 'ssj' / '0.1.0'
    tpl_ssj.mkdir(parents=True)
    (tpl_ssj / 'config.yaml').write_text('root: test\n', encoding='utf-8')
    (tpl_ssj / 'models.yaml').write_text(
        'default: ds\nmodels:\n  ds:\n    litellm: deepseek/deepseek-chat\n',
        encoding='utf-8',
    )
    (tpl_ssj / 'AGENT_VERSION.yaml').write_text('version: "0.1.0"\n', encoding='utf-8')
    (tpl_ssj / 'README.md').write_text('readme\n', encoding='utf-8')
    (tpl_ssj / '.env.example').write_text('# example\n', encoding='utf-8')
    (tpl_ssj / 'chat-profiles').mkdir()
    (tpl_ssj / 'chat-profiles' / 'demo-profile.yaml').write_text('name: demo\n', encoding='utf-8')

    profiles = repo / 'templates' / 'case'
    profiles.mkdir(parents=True)
    archive = bundle_archive_path(repo, 'ssj', '0.1.0')
    if not archive.is_file():
        build_bundle_archive(
            source_root=_REPO,
            output_archive=archive,
            line='ssj',
            version='0.1.0',
        )
    (profiles / 'my-case.yaml').write_text(
        yaml.safe_dump(
            {
                'case_id': 'my-case',
                'title': 'Test',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
            }
        ),
        encoding='utf-8',
    )

    case_dir = add_case('my-case', repo_root=repo)
    assert case_dir.is_dir()
    assert (case_dir / 'case.yaml').is_file()
    assert (case_dir / 'ssj-ds' / 'config.yaml').is_file()
    path = resolve_case_yaml('my-case', repo_root=repo)
    assert path == case_dir / 'case.yaml'


def test_delete_requires_force(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    (repo / 'benchmark').mkdir(parents=True)
    (repo / 'benchmark' / 'manifest.yaml').write_text('suites: {}\n', encoding='utf-8')
    case_root = repo / 'case' / 'gone'
    case_root.mkdir(parents=True)
    (case_root / 'case.yaml').write_text('case_id: gone\ntitle: x\n', encoding='utf-8')
    with pytest.raises(ValueError, match='--force'):
        delete_case('gone', repo_root=repo, force=False)
    delete_case('gone', repo_root=repo, force=True)
    assert not case_root.exists()


def test_list_catalog_merges_profile_and_disk(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    (repo / 'benchmark').mkdir(parents=True)
    (repo / 'benchmark' / 'manifest.yaml').write_text('suites: {}\n', encoding='utf-8')
    profiles = repo / 'templates' / 'case'
    profiles.mkdir(parents=True)
    (profiles / 'only-profile.yaml').write_text(
        'case_id: only-profile\ntitle: P\nagent: {line: ssj, version: "0.1.0"}\n'
        'benchmark: {suites: [demo]}\nmatrix: {profiles: [ds]}\n',
        encoding='utf-8',
    )
    rows = list_case_catalog(repo)
    ids = [r.case_id for r in rows]
    assert 'only-profile' in ids
