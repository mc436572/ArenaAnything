"""Case workspace layout and ssj root materialize (used by arena init later)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from shared.ssj_bundle import extract_bundle_into_case
from ssj.model_secrets import write_env_example
from ssj.models_store import load_models_store, set_default
from ssj.settings import chat_profiles_dir_for_root, write_default_config

REPO_ROOT_MARKER = Path('benchmark') / 'manifest.yaml'
DEFAULT_TEMPLATE = Path('templates') / 'ssj' / '0.1.0'


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / REPO_ROOT_MARKER).is_file():
            return parent
    raise FileNotFoundError(f'Cannot find SSaiyan repo root (missing {REPO_ROOT_MARKER})')


def load_case_spec(case_yaml: Path) -> dict:
    with case_yaml.open(encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f'Invalid case yaml: {case_yaml}')
    return data


def case_dir_from_spec_path(case_yaml: Path) -> Path:
    return case_yaml.resolve().parent


def instance_dir_name(agent_line: str, profile: str) -> str:
    """Process-root folder under a Case, e.g. ssj-ds."""
    line = str(agent_line or 'ssj').strip() or 'ssj'
    name = str(profile).strip()
    if not name:
        raise ValueError('profile must be non-empty')
    return f'{line}-{name}'


def ensure_ssj_root_dirs(dest_root: Path) -> None:
    """Create runtime subdirs without overwriting config (idempotent init)."""
    dest_root.mkdir(parents=True, exist_ok=True)
    (dest_root / 'traces').mkdir(exist_ok=True)
    (dest_root / 'session').mkdir(exist_ok=True)
    (dest_root / 'reports').mkdir(exist_ok=True)
    profiles_dir = chat_profiles_dir_for_root(dest_root)
    profiles_dir.mkdir(parents=True, exist_ok=True)


def instance_config_ready(dest_root: Path) -> bool:
    return dest_root.is_dir() and (dest_root / 'config.yaml').is_file()


def materialize_ssj_root(
    *,
    template_dir: Path,
    dest_root: Path,
    profile: str,
) -> None:
    """Copy template into dest_root and set models.yaml default to profile."""
    if not template_dir.is_dir():
        raise FileNotFoundError(f'Missing template: {template_dir}')

    dest_root.mkdir(parents=True, exist_ok=True)
    for name in (
        'config.yaml',
        'AGENT_VERSION.yaml',
        'README.md',
        '.env.example',
        'models.yaml',
    ):
        src = template_dir / name
        if src.is_file():
            shutil.copy2(src, dest_root / name)

    write_default_config(dest_root / 'config.yaml')
    (dest_root / 'traces').mkdir(exist_ok=True)
    (dest_root / 'session').mkdir(exist_ok=True)
    chat_profiles_dir_for_root(dest_root).mkdir(parents=True, exist_ok=True)
    (dest_root / 'reports').mkdir(exist_ok=True)

    store = load_models_store(dest_root)
    set_default(store, profile)
    litellm = store.default_litellm()
    write_env_example(dest_root / '.env.example', litellm)


def init_case_workspace(
    case_yaml: Path,
    *,
    repo_root: Path | None = None,
    template_rel: Path | None = None,
    apply_keys: bool = False,
    rebuild: bool = False,
    init_ui: object | None = None,
) -> Path:
    """Create reports/* and ssj-<profile>/ instance dirs from case.yaml."""
    repo = repo_root or find_repo_root(case_yaml.parent)
    spec = load_case_spec(case_yaml)
    case_dir = case_dir_from_spec_path(case_yaml)

    agent = spec.get('agent') or {}
    line = str(agent.get('line') or 'ssj')
    version = str(agent.get('version') or '0.1.0')
    template = template_rel or Path('templates') / line / version
    template_dir = (repo / template).resolve()

    matrix = spec.get('matrix') or {}
    profiles = matrix.get('profiles') or []
    if not profiles:
        raise ValueError('case.yaml: matrix.profiles is empty')

    output = spec.get('output') or {}
    reports_name = str(output.get('reports_dir') or 'reports')

    reports_base = case_dir / reports_name
    reports_base.mkdir(parents=True, exist_ok=True)
    (case_dir / 'export').mkdir(exist_ok=True)

    profile_names = [str(p).strip() for p in profiles if str(p).strip()]

    step1_title = 'Materialize profiles & extract bundle'
    if init_ui is not None:
        init_ui.step_running(1, step1_title)

    for name in profile_names:
        inst = instance_dir_name(line, name)
        dest = case_dir / inst
        if rebuild or not instance_config_ready(dest):
            materialize_ssj_root(
                template_dir=template_dir,
                dest_root=dest,
                profile=name,
            )
        else:
            ensure_ssj_root_dirs(dest)
        (reports_base / name).mkdir(parents=True, exist_ok=True)

    from shared.ssj_bundle import bundle_archive_name, bundle_archive_path

    archive = bundle_archive_path(repo, line, version)
    progress_cb = None
    if init_ui is not None:
        init_ui.begin_bundle_extract(bundle_archive_name(version))
        progress_cb = init_ui.update_bundle_extract

    try:
        _unpack_dir, extracted_now = extract_bundle_into_case(
            repo_root=repo,
            case_dir=case_dir,
            line=line,
            version=version,
            force=rebuild,
            on_extract_progress=progress_cb,
        )
    finally:
        if init_ui is not None:
            init_ui.end_bundle_extract()

    if init_ui is not None:
        if extracted_now:
            detail = f'extracted {bundle_archive_name(version)}'
        else:
            detail = 'bundle already present, skip extract'
        init_ui.step_done(1, step1_title, detail)

    step2_title = 'Apply secrets from pool'
    if apply_keys:
        if init_ui is not None:
            init_ui.step_running(2, step2_title)
        from shared.case_secrets import apply_secrets_for_case

        apply_secrets_for_case(
            case_dir=case_dir,
            repo_root=repo,
            case_spec=spec,
            agent_line=line,
            profiles=profile_names,
            force=rebuild,
        )
        if init_ui is not None:
            inst_list = ', '.join(instance_dir_name(line, n) for n in profile_names)
            init_ui.step_done(2, step2_title, inst_list)
    elif init_ui is not None:
        init_ui.step_skip(2, step2_title, '--no-key')

    return case_dir
