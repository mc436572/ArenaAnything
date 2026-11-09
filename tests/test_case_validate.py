from __future__ import annotations

from pathlib import Path

import yaml

from shared.case_validate import validate_case
from shared.case_workspace import init_case_workspace


def test_validate_demo_four_case_after_init() -> None:
    repo = Path(__file__).resolve().parents[1]
    case_yaml = repo / 'case' / 'case001-4llm-demo' / 'case.yaml'
    init_case_workspace(case_yaml, repo_root=repo)
    result = validate_case(case_yaml, repo_root=repo)
    assert result.ok, result.errors


def test_validate_requires_materialized_instances(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'fresh-case'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'fresh-case',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
                'eval': {'profile': 'demo-profile'},
            }
        ),
        encoding='utf-8',
    )
    result = validate_case(case_yaml, repo_root=repo)
    assert not result.ok
    assert any('Missing instance' in e or 'ssj-ds' in e for e in result.errors)


def test_validate_ok_after_init(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'ok-case'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'ok-case',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds']},
                'eval': {'profile': 'demo-profile'},
            }
        ),
        encoding='utf-8',
    )
    init_case_workspace(case_yaml, repo_root=repo)
    result = validate_case(case_yaml, repo_root=repo)
    assert result.ok, result.errors


def test_validate_rejects_unknown_suite(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    case_dir = tmp_path / 'bad-case'
    case_dir.mkdir()
    case_yaml = case_dir / 'case.yaml'
    case_yaml.write_text(
        yaml.safe_dump(
            {
                'case_id': 'bad',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['not-a-suite']},
                'matrix': {'profiles': ['ds']},
            }
        ),
        encoding='utf-8',
    )
    result = validate_case(case_yaml, repo_root=repo)
    assert not result.ok
    assert any('Unknown suite' in e for e in result.errors)
