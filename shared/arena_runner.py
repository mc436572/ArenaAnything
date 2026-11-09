"""Run ssj eval matrix for a Case (suite × profile)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from shared.case_spec import CaseSpecView, parse_case_spec
from shared.case_validate import CaseValidationError, require_valid_case
from shared.case_workspace import find_repo_root, instance_dir_name
from ssj.model_secrets import env_value_for_model, resolve_secrets_for_model
from ssj.models_store import load_models_store


def _dotenv_map(instance_root: Path) -> dict[str, str]:
    from dotenv import dotenv_values

    path = instance_root / '.env'
    if not path.is_file():
        return {}
    raw = dotenv_values(path)
    out: dict[str, str] = {}
    for key, val in raw.items():
        if val is None:
            continue
        text = str(val).strip()
        if text:
            out[str(key)] = text
    return out


def _secret_value(instance_root: Path, litellm: str, env_name: str) -> str:
    local = _dotenv_map(instance_root).get(env_name, '').strip()
    if local:
        return local
    return env_value_for_model(litellm, env_name)


@dataclass(frozen=True)
class EvalCellResult:
    profile: str
    suite: str
    instance_root: Path
    exit_code: int
    report_src: Path | None
    report_dest: Path | None
    log: str


def _missing_required_keys(instance_root: Path) -> list[str]:
    store = load_models_store(instance_root)
    litellm = store.default_litellm()
    missing: list[str] = []
    for spec in resolve_secrets_for_model(litellm):
        if not spec.required:
            continue
        if not _secret_value(instance_root, litellm, spec.name):
            missing.append(spec.name)
    return missing


def check_case_keys(spec: CaseSpecView) -> dict[str, list[str]]:
    """Profile → list of missing required env names."""
    out: dict[str, list[str]] = {}
    for profile in spec.profiles:
        root = spec.case_dir / instance_dir_name(spec.agent_line, profile)
        if not root.is_dir():
            out[profile] = ['(instance root missing — run arena init)']
            continue
        miss = _missing_required_keys(root)
        if miss:
            out[profile] = miss
    return out


def _latest_eval_report(reports_dir: Path, suite: str, alias: str) -> Path | None:
    if not reports_dir.is_dir():
        return None
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', alias.strip() or 'model')
    pattern = f'eval-{suite}-{safe}-*.json'
    matches = sorted(reports_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _progress_path(spec: CaseSpecView, profile: str, suite: str) -> Path:
    return (
        spec.case_dir
        / spec.reports_dir
        / '.progress'
        / f'{profile}__{suite}.json'
    )


def _run_one_cell(
    spec: CaseSpecView,
    profile: str,
    suite: str,
    *,
    repo_root: Path,
    progress_path: Path | None = None,
) -> EvalCellResult:
    from shared.ssj_subprocess import run_ssj_in_instance

    instance_root = spec.case_dir / instance_dir_name(spec.agent_line, profile)
    extra_env: dict[str, str] = {
        'SSJ_SILENT_STARTUP': '1',
        'SSJ_EVAL_TEMPERATURE': str(spec.temperature),
        'SSJ_EVAL_TIMEOUT': str(spec.timeout_sec),
        'SSJ_EVAL_PROBE_LIMIT': str(spec.probe_limit),
    }
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        extra_env['SSJ_PROGRESS_FILE'] = str(progress_path.resolve())
        extra_env.setdefault('SSJ_PROGRESS_STEP', '5')

    try:
        proc = run_ssj_in_instance(
            instance_root,
            [
                'eval',
                '-s',
                suite,
                '--with-profile',
                spec.eval_profile,
            ],
            agent_version=spec.agent_version,
            extra_env=extra_env,
        )
        log = (proc.stdout or '') + (proc.stderr or '')
    except FileNotFoundError as exc:
        return EvalCellResult(
            profile=profile,
            suite=suite,
            instance_root=instance_root.resolve(),
            exit_code=127,
            report_src=None,
            report_dest=None,
            log=str(exc),
        )

    report_src: Path | None = None
    report_dest: Path | None = None
    if proc.returncode == 0:
        store = load_models_store(instance_root)
        report_src = _latest_eval_report(instance_root / 'reports', suite, store.default)
        if report_src is not None:
            dest_dir = spec.case_dir / spec.reports_dir / profile
            dest_dir.mkdir(parents=True, exist_ok=True)
            report_dest = dest_dir / report_src.name
            shutil.copy2(report_src, report_dest)

    return EvalCellResult(
        profile=profile,
        suite=suite,
        instance_root=instance_root.resolve(),
        exit_code=proc.returncode,
        report_src=report_src,
        report_dest=report_dest,
        log=log,
    )


def run_case_matrix(
    case_yaml: Path,
    *,
    repo_root: Path | None = None,
    check_keys: bool = True,
    profiles: tuple[str, ...] | None = None,
    suites: tuple[str, ...] | None = None,
) -> list[EvalCellResult]:
    repo = repo_root or find_repo_root(case_yaml.parent)
    spec = require_valid_case(case_yaml, repo_root=repo)

    run_profiles = profiles or spec.profiles
    run_suites = suites or spec.suites
    for p in run_profiles:
        if p not in spec.profiles:
            raise CaseValidationError(f'Unknown profile filter: {p!r}')
    for s in run_suites:
        if s not in spec.suites:
            raise CaseValidationError(f'Unknown suite filter: {s!r}')

    if check_keys:
        missing = check_case_keys(spec)
        bad = {k: v for k, v in missing.items() if k in run_profiles}
        if bad:
            lines = ['Missing API keys before arena run:']
            for prof, keys in bad.items():
                lines.append(f'  {prof}: {", ".join(keys)}')
            lines.append('Configure each ssj-<profile>/ (.env or ssj model set).')
            raise CaseValidationError('\n'.join(lines))

    cells: list[tuple[str, str]] = [(prof, suite) for prof in run_profiles for suite in run_suites]
    progress_paths = {
        (prof, suite): _progress_path(spec, prof, suite) for prof, suite in cells
    }

    def _submit(profile: str, suite: str) -> EvalCellResult:
        repeats = max(1, spec.repeats)
        last: EvalCellResult | None = None
        for _ in range(repeats):
            last = _run_one_cell(
                spec,
                profile,
                suite,
                repo_root=repo,
                progress_path=progress_paths.get((profile, suite)),
            )
        assert last is not None
        return last

    # One parallel worker per matrix profile; suites for that profile run serially.
    workers = max(1, len(run_profiles))
    from shared.arena_progress import clear_progress_snapshots, run_with_progress_monitor

    clear_progress_snapshots(progress_paths)
    results = run_with_progress_monitor(
        cells,
        progress_paths,
        workers=workers,
        submit_cell=_submit,
    )

    # Stable sort: profile order then suite order
    prof_index = {p: i for i, p in enumerate(run_profiles)}
    suite_index = {s: i for i, s in enumerate(run_suites)}
    results.sort(
        key=lambda r: (prof_index.get(r.profile, 99), suite_index.get(r.suite, 99))
    )
    return results
