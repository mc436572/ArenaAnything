"""Merge Case eval reports into summary.json and index.html."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from shared.case_spec import CaseSpecView, parse_case_spec
from shared.case_workspace import instance_dir_name


def _duration_from_report(data: dict) -> float:
    if data.get('duration_sec') is not None:
        return float(data['duration_sec'])
    items = data.get('items') or []
    if not isinstance(items, list):
        return 0.0
    ms = sum(float(row.get('latency_ms') or 0) for row in items if isinstance(row, dict))
    return round(ms / 1000.0, 2)


def _throughput(n: int, duration_sec: float) -> float:
    if duration_sec <= 0 or n <= 0:
        return 0.0
    return round(n / duration_sec, 3)


def _load_report(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f'Invalid report JSON: {path}')
    return data


def _collect_reports(case_dir: Path, spec_profiles: tuple[str, ...], reports_dir_name: str) -> list[dict]:
    cells: list[dict] = []
    base = case_dir / reports_dir_name
    for profile in spec_profiles:
        prof_dir = base / profile
        if not prof_dir.is_dir():
            continue
        for path in sorted(prof_dir.glob('eval-*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = _load_report(path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            suite = str(data.get('suite') or '')
            if any(c.get('profile') == profile and c.get('suite') == suite for c in cells):
                continue
            n = int(data.get('n') or 0)
            correct = int(data.get('correct') or 0)
            acc = float(data.get('accuracy') or (correct / n if n else 0.0))
            duration_sec = _duration_from_report(data)
            cells.append(
                {
                    'profile': profile,
                    'suite': suite,
                    'accuracy': acc,
                    'correct': correct,
                    'n': n,
                    'duration_sec': duration_sec,
                    'throughput': _throughput(n, duration_sec),
                    'litellm_model': data.get('litellm_model'),
                    'model_alias': data.get('model_alias'),
                    'eval_profile': data.get('eval_profile'),
                    'ssj_version': data.get('ssj_version'),
                    'report_path': path.relative_to(case_dir).as_posix(),
                }
            )
    return cells


def _api_model_id(litellm: str) -> str:
    text = litellm.strip()
    if '/' in text:
        return text.split('/', 1)[1]
    return text


def _profile_model_labels(spec: CaseSpecView) -> dict[str, dict[str, str]]:
    """API model slug + models.yaml description (human version label)."""
    from ssj.models_store import load_models_store

    out: dict[str, dict[str, str]] = {}
    for profile in spec.profiles:
        root = spec.case_dir / instance_dir_name(spec.agent_line, profile)
        path = root / 'models.yaml'
        if not path.is_file():
            continue
        try:
            store = load_models_store(root)
            prof = store.default_profile()
            out[profile] = {
                'model_id': _api_model_id(prof.litellm),
                'model_note': (prof.description or '').strip(),
                'litellm_model': prof.litellm,
            }
        except (OSError, ValueError):
            continue
    return out


def _enrich_cells(cells: list[dict], labels: dict[str, dict[str, str]]) -> list[dict]:
    enriched: list[dict] = []
    for cell in cells:
        row = dict(cell)
        prof = str(row.get('profile') or '')
        litellm = str(row.get('litellm_model') or '')
        meta = labels.get(prof) or {}
        row['model_id'] = meta.get('model_id') or _api_model_id(litellm)
        note = meta.get('model_note') or ''
        if not note and litellm:
            row['model_note'] = litellm
        else:
            row['model_note'] = note
        enriched.append(row)
    return enriched


def _litellm_by_profile(cells: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cell in cells:
        prof = str(cell.get('profile') or '')
        if prof and prof not in out:
            out[prof] = str(cell.get('litellm_model') or '')
    return out


def _format_duration_sec(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return '—'
    return f'{seconds:.1f}s'


def print_accuracy_matrix(summary: dict) -> None:
    """CLI results table (one row per profile×suite; fits narrow terminals)."""
    from cli.console import CONSOLE
    from rich.table import Table

    profiles = summary.get('profiles') or []
    suites = summary.get('suites') or []
    cells = summary.get('cells') or []
    by_key = {(c.get('profile'), c.get('suite')): c for c in cells}

    single_suite = len(suites) == 1
    table = Table(show_header=True, header_style='bold', box=None, pad_edge=False)
    table.add_column('profile', style='bold', no_wrap=True)
    table.add_column('model id', no_wrap=True)
    table.add_column('version', overflow='fold', max_width=28)
    if not single_suite:
        table.add_column('suite', no_wrap=True)
    table.add_column('acc', justify='right', no_wrap=True)
    table.add_column('score', justify='right', no_wrap=True)
    table.add_column('time', justify='right', no_wrap=True)
    table.add_column('q/s', justify='right', no_wrap=True)

    for suite in suites:
        for profile in profiles:
            cell = by_key.get((profile, suite))
            if not cell:
                row: list[str] = [str(profile), '—', '—']
                if not single_suite:
                    row.append(f'suite：{suite}')
                row.extend(['—', '—', '—', '—'])
                table.add_row(*row)
                continue
            acc = float(cell.get('accuracy') or 0.0) * 100
            n = int(cell.get('n') or 0)
            correct = cell.get('correct')
            dur = float(cell.get('duration_sec') or 0)
            qps = float(cell.get('throughput') or _throughput(n, dur))
            row = [
                str(profile),
                str(cell.get('model_id') or '—'),
                str(cell.get('model_note') or '—'),
            ]
            if not single_suite:
                row.append(f'suite：{suite}')
            row.extend(
                [
                    f'{acc:.1f}%',
                    f'{correct}/{n}',
                    _format_duration_sec(dur),
                    f'{qps:.2f}',
                ]
            )
            table.add_row(*row)

    CONSOLE.print()
    CONSOLE.print('[bold]Results[/]')
    if single_suite:
        CONSOLE.print(f'[dim]suite：{suites[0]}[/]')
    CONSOLE.print(table)


def build_summary(case_yaml: Path) -> dict:
    spec = parse_case_spec(case_yaml)
    case_dir = spec.case_dir
    cells = _enrich_cells(
        _collect_reports(case_dir, spec.profiles, spec.reports_dir),
        _profile_model_labels(spec),
    )
    return {
        'case_id': spec.case_id,
        'title': spec.title,
        'agent': {'line': spec.agent_line, 'version': spec.agent_version},
        'eval_profile': spec.eval_profile,
        'suites': list(spec.suites),
        'profiles': list(spec.profiles),
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'cells': cells,
    }


def render_index_html(summary: dict) -> str:
    title = escape(str(summary.get('title') or summary.get('case_id') or 'Case summary'))
    case_id = escape(str(summary.get('case_id') or ''))
    agent = summary.get('agent') or {}
    agent_line = escape(str(agent.get('line') or 'ssj'))
    agent_ver = escape(str(agent.get('version') or ''))
    generated = escape(str(summary.get('generated_at') or ''))
    suites = summary.get('suites') or []
    profiles = summary.get('profiles') or []
    cells = summary.get('cells') or []

    by_key = {(c.get('profile'), c.get('suite')): c for c in cells}

    note_by_profile = {
        str(c.get('profile')): str(c.get('model_note') or '')
        for c in cells
        if c.get('profile')
    }
    id_by_profile = {
        str(c.get('profile')): str(c.get('model_id') or '')
        for c in cells
        if c.get('profile')
    }

    header_parts: list[str] = []
    for p in profiles:
        prof = escape(str(p))
        model_id = escape(id_by_profile.get(str(p)) or '—')
        note = escape(note_by_profile.get(str(p)) or '')
        note_line = f'<br><span class="meta">{note}</span>' if note else ''
        header_parts.append(
            f'<th>{prof}<br><span class="meta">model: {model_id}</span>{note_line}</th>'
        )
    header = ''.join(header_parts)
    body_rows = []
    for suite in suites:
        cols = []
        for profile in profiles:
            cell = by_key.get((profile, suite))
            if not cell:
                cols.append('<td class="missing">—</td>')
                continue
            acc = float(cell.get('accuracy') or 0.0) * 100
            correct = cell.get('correct')
            n = cell.get('n')
            dur = float(cell.get('duration_sec') or 0)
            qps = float(cell.get('throughput') or _throughput(int(n or 0), dur))
            cols.append(
                f'<td><strong>{acc:.1f}%</strong><br>'
                f'<span class="meta">{correct}/{n}</span><br>'
                f'<span class="meta">{dur:.1f}s · {qps:.2f} q/s</span></td>'
            )
        suite_label = escape(str(suite))
        body_rows.append(f'<tr><th>suite：{suite_label}</th>{"".join(cols)}</tr>')

    detail_rows = []
    for c in cells:
        acc = float(c.get('accuracy') or 0.0) * 100
        detail_rows.append(
            '<tr>'
            f'<td>{escape(str(c.get("profile")))}</td>'
            f'<td>{escape(str(c.get("suite")))}</td>'
            f'<td>{acc:.1f}%</td>'
            f'<td>{c.get("correct")}/{c.get("n")}</td>'
            f'<td>{float(c.get("duration_sec") or 0):.1f}s</td>'
            f'<td>{float(c.get("throughput") or 0):.2f}</td>'
            f'<td><code>{escape(str(c.get("model_id") or ""))}</code></td>'
            f'<td>{escape(str(c.get("model_note") or ""))}</td>'
            f'<td><code>{escape(str(c.get("litellm_model") or ""))}</code></td>'
            f'<td><code>{escape(str(c.get("report_path") or ""))}</code></td>'
            '</tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .sub {{ color: #555; margin-bottom: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem 0.75rem; text-align: left; vertical-align: top; }}
    th {{ background: #f4f4f4; }}
    .meta {{ font-size: 0.85rem; color: #666; }}
    .missing {{ color: #999; }}
    code {{ font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="sub">case_id: <code>{case_id}</code> · agent: <code>{agent_line}@{agent_ver}</code> · generated: {generated}</p>
  <h2>Accuracy matrix</h2>
  <p class="sub">Rows = suite · columns = profile · model = configured litellm id (request slug).</p>
  <table>
    <thead><tr><th></th>{header}</tr></thead>
    <tbody>
      {''.join(body_rows)}
    </tbody>
  </table>
  <h2>Reports</h2>
  <table>
    <thead><tr><th>profile</th><th>suite</th><th>accuracy</th><th>score</th><th>time</th><th>q/s</th><th>model id</th><th>version</th><th>litellm</th><th>file</th></tr></thead>
    <tbody>
      {''.join(detail_rows) if detail_rows else '<tr><td colspan="10">No reports found under reports/&lt;profile&gt;/</td></tr>'}
    </tbody>
  </table>
</body>
</html>
"""


def write_case_output(case_yaml: Path) -> tuple[Path, Path]:
    spec = parse_case_spec(case_yaml)
    case_dir = spec.case_dir
    export_dir = case_dir / 'export'
    export_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(case_yaml)
    summary_path = export_dir / 'summary.json'
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    html_path = export_dir / 'index.html'
    html_path.write_text(render_index_html(summary), encoding='utf-8')
    return summary_path, html_path
