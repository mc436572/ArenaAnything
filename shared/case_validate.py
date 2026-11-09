"""Validate case.yaml and materialized ssj instance roots (arena check)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from shared.benchmark_probes import list_suite_names, repo_benchmark_root
from shared.case_spec import CaseSpecView, parse_case_spec
from shared.case_workspace import find_repo_root, instance_dir_name
from shared.ssj_bundle import (
    bundle_archive_path,
    case_unpack_dir,
    is_bundle_unpack_ready,
)
from ssj.models_store import load_models_store

# Copied into each ssj-<profile>/ by materialize (see shared/case_workspace.py).
INSTANCE_FILES = (
    'config.yaml',
    'models.yaml',
    'AGENT_VERSION.yaml',
    '.env.example',
)
INSTANCE_DIRS = (
    'traces',
    'session',
    'reports',
    'chat-profiles',
)


class CaseValidationError(ValueError):
    pass


@dataclass
class CaseValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def _load_template_models(template_dir: Path) -> dict[str, str]:
    path = template_dir / 'models.yaml'
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    raw = data.get('models') if isinstance(data, dict) else {}
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for alias, val in raw.items():
            if isinstance(val, dict) and val.get('litellm'):
                out[str(alias)] = str(val['litellm']).strip()
    return out


def _verify_instance_root(
    *,
    spec: CaseSpecView,
    profile: str,
    inst: Path,
    template_litellm: dict[str, str],
    errors: list[str],
) -> None:
    label = inst.relative_to(spec.case_dir).as_posix()
    if not inst.is_dir():
        errors.append(f'Missing instance directory: {label} (run `arena init` first)')
        return

    for name in INSTANCE_FILES:
        if not (inst / name).is_file():
            errors.append(f'{label}: missing file {name}')

    for name in INSTANCE_DIRS:
        if not (inst / name).is_dir():
            errors.append(f'{label}: missing directory {name}/')

    from ssj.chat_profile import resolve_chat_profile_path
    from ssj.settings import chat_profiles_dir_for_root

    try:
        resolve_chat_profile_path(chat_profiles_dir_for_root(inst), spec.eval_profile)
    except (OSError, ValueError) as exc:
        errors.append(f'{label}: eval preset {spec.eval_profile!r} not found ({exc})')

    av_path = inst / 'AGENT_VERSION.yaml'
    if av_path.is_file():
        with av_path.open(encoding='utf-8') as f:
            av = yaml.safe_load(f) or {}
        if isinstance(av, dict):
            line = str(av.get('line') or '').strip()
            version = str(av.get('version') or '').strip()
            if line and line != spec.agent_line:
                errors.append(
                    f'{label}: AGENT_VERSION line {line!r} != case agent.line {spec.agent_line!r}'
                )
            if version and version != spec.agent_version:
                errors.append(
                    f'{label}: AGENT_VERSION version {version!r} != '
                    f'case agent.version {spec.agent_version!r}'
                )

    if not (inst / 'models.yaml').is_file():
        return

    try:
        store = load_models_store(inst)
    except (OSError, ValueError) as exc:
        errors.append(f'{label}: invalid models.yaml ({exc})')
        return

    if store.default != profile:
        errors.append(
            f'{label}: models.yaml default {store.default!r} != matrix profile {profile!r}'
        )

    prof = store.models.get(profile)
    if prof is None:
        errors.append(f'{label}: models.yaml has no entry for profile {profile!r}')
        return

    expected = template_litellm.get(profile)
    if expected and prof.litellm != expected:
        errors.append(
            f'{label}: litellm for {profile!r} is {prof.litellm!r}, '
            f'frozen template expects {expected!r}'
        )


def validate_case(case_yaml: Path, *, repo_root: Path | None = None) -> CaseValidationResult:
    """Validate case.yaml and every ssj-<profile>/ tree (after init)."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        spec = parse_case_spec(case_yaml)
    except (OSError, ValueError) as exc:
        return CaseValidationResult(False, [str(exc)], [])

    if not spec.case_id:
        errors.append('case_id is required')
    if not spec.profiles:
        errors.append('matrix.profiles must be a non-empty list')
    if len(spec.profiles) != len(set(spec.profiles)):
        errors.append('matrix.profiles contains duplicates')
    if not spec.suites:
        errors.append('benchmark.suites must be a non-empty list')
    if len(spec.suites) != len(set(spec.suites)):
        errors.append('benchmark.suites contains duplicates')

    try:
        repo = repo_root or find_repo_root(case_yaml.parent)
    except FileNotFoundError as exc:
        errors.append(str(exc))
        return CaseValidationResult(False, errors, warnings)

    template_dir = repo / 'templates' / spec.agent_line / spec.agent_version
    template_litellm: dict[str, str] = {}
    if not template_dir.is_dir():
        errors.append(f'Missing agent template: {template_dir.relative_to(repo)}')
    else:
        for name in ('models.yaml', 'AGENT_VERSION.yaml'):
            if not (template_dir / name).is_file():
                errors.append(f'Template missing {name}: {template_dir}')
        template_litellm = _load_template_models(template_dir)

    try:
        known_suites = set(list_suite_names(repo_benchmark_root(repo)))
        for suite in spec.suites:
            if suite not in known_suites:
                errors.append(
                    f'Unknown suite {suite!r}. Known: {", ".join(sorted(known_suites))}'
                )
    except ValueError as exc:
        errors.append(str(exc))

    for profile in spec.profiles:
        if template_litellm and profile not in template_litellm:
            errors.append(
                f'Profile {profile!r} not in frozen template models.yaml '
                f'({template_dir.relative_to(repo) if template_dir.is_dir() else "?"})'
            )

    case_dir = spec.case_dir
    archive = bundle_archive_path(repo, spec.agent_line, spec.agent_version)
    if not archive.is_file():
        errors.append(
            f'Missing frozen bundle {archive.relative_to(repo).as_posix()} '
            f'(maintainers rebuild it under templates/ssj/{spec.agent_version}/)'
        )
    unpack = case_unpack_dir(case_dir, spec.agent_version)
    if not is_bundle_unpack_ready(unpack):
        rel = unpack.relative_to(case_dir).as_posix()
        errors.append(f'Missing frozen ssj unpack at {rel}/ (run arena init)')

    reports_base = case_dir / spec.reports_dir
    if not reports_base.is_dir():
        errors.append(
            f'Missing case reports dir: {reports_base.relative_to(case_dir).as_posix()} '
            '(run `arena init`)'
        )
    else:
        for profile in spec.profiles:
            sub = reports_base / profile
            if not sub.is_dir():
                errors.append(
                    f'Missing reports/{profile}/ (run `arena init`)'
                )

    export_dir = case_dir / 'export'
    if not export_dir.is_dir():
        warnings.append('export/ not created yet (normal before first `arena summary`)')

    for profile in spec.profiles:
        inst = case_dir / instance_dir_name(spec.agent_line, profile)
        _verify_instance_root(
            spec=spec,
            profile=profile,
            inst=inst,
            template_litellm=template_litellm,
            errors=errors,
        )

    if not errors:
        from shared.arena_runner import check_case_keys

        key_map = check_case_keys(spec)
        for profile, missing in key_map.items():
            if missing:
                warnings.append(
                    f'{profile}: API keys not ready ({", ".join(missing)}) — '
                    'ssj model set in ssj-<profile>/ before arena run'
                )

    return CaseValidationResult(len(errors) == 0, errors, warnings)


def require_valid_case(case_yaml: Path, *, repo_root: Path | None = None) -> CaseSpecView:
    result = validate_case(case_yaml, repo_root=repo_root)
    if not result.ok:
        raise CaseValidationError('\n'.join(result.errors))
    return parse_case_spec(case_yaml)
