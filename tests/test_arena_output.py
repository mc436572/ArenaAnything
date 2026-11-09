from __future__ import annotations

import json
from pathlib import Path

import yaml

from shared.arena_output import build_summary, render_index_html, write_case_output


def test_output_builds_html(tmp_path: Path) -> None:
    case_dir = tmp_path / 'case001-4llm-demo'
    case_dir.mkdir()
    (case_dir / 'case.yaml').write_text(
        yaml.safe_dump(
            {
                'case_id': 'case001-4llm-demo',
                'title': 'test',
                'agent': {'line': 'ssj', 'version': '0.1.0'},
                'benchmark': {'suites': ['demo']},
                'matrix': {'profiles': ['ds', 'mimo']},
                'eval': {'profile': 'demo-profile'},
                'output': {'reports_dir': 'reports'},
            }
        ),
        encoding='utf-8',
    )
    rep = case_dir / 'reports' / 'ds'
    rep.mkdir(parents=True)
    report = {
        'suite': 'demo',
        'model_alias': 'ds',
        'litellm_model': 'deepseek/deepseek-chat',
        'n': 30,
        'correct': 24,
        'accuracy': 0.8,
        'duration_sec': 60.0,
        'items': [{'latency_ms': 2000.0}] * 30,
    }
    (rep / 'eval-demo-ds-test.json').write_text(json.dumps(report), encoding='utf-8')

    summary = build_summary(case_dir / 'case.yaml')
    assert len(summary['cells']) == 1
    assert summary['cells'][0]['accuracy'] == 0.8
    assert summary['cells'][0]['duration_sec'] == 60.0
    assert summary['cells'][0]['throughput'] == 0.5

    html = render_index_html(summary)
    assert 'case001-4llm-demo' in html or 'test' in html
    assert '80.0%' in html
    assert 'model: deepseek-chat' in html
    assert summary['cells'][0].get('model_id') == 'deepseek-chat'
    assert '0.50 q/s' in html or '0.5 q/s' in html

    summary_path, html_path = write_case_output(case_dir / 'case.yaml')
    assert summary_path.is_file()
    assert html_path.is_file()
