from __future__ import annotations

from pathlib import Path

import yaml

from shared.case_workspace import init_case_workspace, instance_dir_name, materialize_ssj_root
from ssj.models_store import load_models_store


def test_materialize_baseline_roots(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'baseline-test'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'baseline-test',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'matrix': {'profiles': ['ds', 'kimi']},
            }
        ),
        encoding='utf-8',
    )
    from shared.ssj_bundle import case_unpack_dir, is_bundle_unpack_ready

    init_case_workspace(case_yaml, repo_root=repo)
    assert is_bundle_unpack_ready(case_unpack_dir(case_dir, '0.1.0'))
    assert instance_dir_name('ssj', 'ds') == 'ssj-ds'
    ds_root = case_dir / 'ssj-ds'
    assert (ds_root / 'config.yaml').is_file()
    assert (ds_root / 'models.yaml').is_file()
    store = load_models_store(ds_root)
    assert store.default == 'ds'
    assert store.models['jev'].litellm == 'typesafe/jev-latest'
    assert store.models['ds'].litellm == 'deepseek/deepseek-chat'
    kimi_store = load_models_store(case_dir / 'ssj-kimi')
    assert kimi_store.default == 'kimi'


def test_materialize_ssj_root_template_exists() -> None:
    repo = Path(__file__).resolve().parents[1]
    template = repo / 'templates' / 'ssj' / '0.1.0'
    assert template.is_dir()
    assert (template / 'models.yaml').is_file()
    assert (template / 'RELEASE.md').is_file()
    assert (template / 'MANIFEST.yaml').is_file()
