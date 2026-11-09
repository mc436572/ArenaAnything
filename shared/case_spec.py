"""Parse case.yaml fields used by arena validate / run / output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.case_workspace import load_case_spec


@dataclass(frozen=True)
class CaseSpecView:
    path: Path
    case_id: str
    title: str
    agent_line: str
    agent_version: str
    suites: tuple[str, ...]
    profiles: tuple[str, ...]
    eval_profile: str
    reports_dir: str
    repeats: int
    probe_limit: int
    timeout_sec: float
    temperature: float

    @property
    def case_dir(self) -> Path:
        return self.path.resolve().parent


def parse_case_spec(case_yaml: Path) -> CaseSpecView:
    raw = load_case_spec(case_yaml)
    case_id = str(raw.get('case_id') or '').strip()
    title = str(raw.get('title') or '').strip()
    agent = raw.get('agent') or {}
    line = str(agent.get('line') or 'ssj').strip() or 'ssj'
    version = str(agent.get('version') or '0.1.0').strip() or '0.1.0'

    benchmark = raw.get('benchmark') or {}
    suites_raw = benchmark.get('suites') or []
    if not isinstance(suites_raw, list):
        suites_raw = []
    suites = tuple(str(s).strip() for s in suites_raw if str(s).strip())

    matrix = raw.get('matrix') or {}
    profiles_raw = matrix.get('profiles') or []
    if not isinstance(profiles_raw, list):
        profiles_raw = []
    profiles = tuple(str(p).strip() for p in profiles_raw if str(p).strip())

    eval_block = raw.get('eval') or {}
    eval_profile = str(eval_block.get('profile') or 'demo-profile').strip() or 'demo-profile'

    output = raw.get('output') or {}
    reports_dir = str(output.get('reports_dir') or 'reports').strip() or 'reports'

    run = raw.get('run') or {}
    repeats = int(run.get('repeats') or 1)
    probe_limit = int(run.get('probe_limit') or 0)
    timeout_sec = float(run.get('timeout_sec') or 60)
    temperature = float(run.get('temperature') or 0)

    return CaseSpecView(
        path=case_yaml,
        case_id=case_id,
        title=title,
        agent_line=line,
        agent_version=version,
        suites=suites,
        profiles=profiles,
        eval_profile=eval_profile,
        reports_dir=reports_dir,
        repeats=repeats,
        probe_limit=probe_limit,
        timeout_sec=timeout_sec,
        temperature=temperature,
    )
