"""Arena Case catalog: profiles under templates/case/, workspaces under case/."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from shared.case_spec import parse_case_spec
from shared.case_workspace import find_repo_root, init_case_workspace, load_case_spec

CASE_ID_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')
CASE_DIR_NAME = 'case'
PROFILE_DIR_NAME = Path('templates') / 'case'


def normalize_case_id(raw: str) -> str:
    case_id = str(raw or '').strip()
    if not case_id or not CASE_ID_RE.fullmatch(case_id):
        raise ValueError(
            f'Invalid case id {raw!r} (use letters, digits, dot, underscore, hyphen; no paths)'
        )
    return case_id


def case_profiles_dir(repo_root: Path) -> Path:
    return (repo_root / PROFILE_DIR_NAME).resolve()


def case_workspace_dir(repo_root: Path, case_id: str) -> Path:
    cid = normalize_case_id(case_id)
    return (repo_root / CASE_DIR_NAME / cid).resolve()


def profile_recipe_path(repo_root: Path, case_id: str) -> Path:
    cid = normalize_case_id(case_id)
    return case_profiles_dir(repo_root) / f'{cid}.yaml'


def case_yaml_path(repo_root: Path, case_id: str) -> Path:
    return case_workspace_dir(repo_root, case_id) / 'case.yaml'


def load_profile_recipe(repo_root: Path, case_id: str) -> dict:
    path = profile_recipe_path(repo_root, case_id)
    if not path.is_file():
        raise FileNotFoundError(
            f'Automatic case creation is not supported yet. '
            f'Add templates/case/{case_id}.yaml by hand, then run: arena init --case {case_id}'
        )
    with path.open(encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f'Invalid case profile yaml: {path}')
    recipe_id = str(data.get('case_id') or '').strip()
    if recipe_id != case_id:
        raise ValueError(
            f'Profile {path.name}: case_id {recipe_id!r} must match filename stem {case_id!r}'
        )
    return data


def _copy_profile_extras(repo_root: Path, case_id: str, dest_dir: Path) -> None:
    extras = case_profiles_dir(repo_root) / case_id
    if not extras.is_dir():
        return
    for item in extras.iterdir():
        if item.name.endswith('.yaml'):
            continue
        target = dest_dir / item.name
        if item.is_file():
            shutil.copy2(item, target)
        elif item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)


def resolve_case_yaml(
    case_id: str,
    *,
    repo_root: Path | None = None,
    start: Path | None = None,
) -> Path:
    """Resolve --case (case id) to case/<id>/case.yaml; enforce id ↔ directory ↔ yaml."""
    repo = repo_root or find_repo_root(start)
    cid = normalize_case_id(case_id)
    yaml_path = case_yaml_path(repo, cid)
    if not yaml_path.is_file():
        raise FileNotFoundError(
            f'Case workspace missing: {yaml_path.relative_to(repo).as_posix()} '
            f'(run `arena init --case {cid}`)'
        )
    spec = parse_case_spec(yaml_path)
    if spec.case_id != cid:
        raise ValueError(
            f'case.yaml case_id {spec.case_id!r} must match directory name {cid!r}'
        )
    return yaml_path


@dataclass(frozen=True)
class CaseCatalogRow:
    case_id: str
    title: str
    defined: bool
    on_disk: bool
    materialized: bool


def list_case_catalog(repo_root: Path) -> list[CaseCatalogRow]:
    profiles_root = case_profiles_dir(repo_root)
    defined_ids: set[str] = set()
    if profiles_root.is_dir():
        for path in profiles_root.glob('*.yaml'):
            defined_ids.add(path.stem)

    disk_ids: set[str] = set()
    case_root = repo_root / CASE_DIR_NAME
    if case_root.is_dir():
        for path in case_root.iterdir():
            if path.is_dir() and (path / 'case.yaml').is_file():
                disk_ids.add(path.name)

    all_ids = sorted(defined_ids | disk_ids)
    rows: list[CaseCatalogRow] = []
    for cid in all_ids:
        title = ''
        defined = cid in defined_ids
        on_disk = cid in disk_ids
        materialized = False
        if on_disk:
            try:
                spec = parse_case_spec(case_yaml_path(repo_root, cid))
                title = spec.title
                materialized = any(
                    (case_workspace_dir(repo_root, cid) / f'ssj-{p}').is_dir()
                    for p in spec.profiles
                )
            except (ValueError, OSError):
                title = '(invalid case.yaml)'
        elif defined:
            try:
                raw = load_profile_recipe(repo_root, cid)
                title = str(raw.get('title') or '').strip()
            except (ValueError, OSError):
                title = '(invalid profile)'
        rows.append(
            CaseCatalogRow(
                case_id=cid,
                title=title,
                defined=defined,
                on_disk=on_disk,
                materialized=materialized,
            )
        )
    return rows


def add_case(
    case_id: str,
    *,
    repo_root: Path | None = None,
    start: Path | None = None,
    apply_keys: bool = False,
    rebuild: bool = False,
    init_ui: object | None = None,
) -> Path:
    """Materialize case/<case_id>/ from templates/case/<case_id>.yaml (+ extras)."""
    repo = repo_root or find_repo_root(start)
    cid = normalize_case_id(case_id)
    recipe = load_profile_recipe(repo, cid)
    dest = case_workspace_dir(repo, cid)

    if rebuild and dest.exists():
        try:
            dest.relative_to((repo / CASE_DIR_NAME).resolve())
        except ValueError as exc:
            raise ValueError(f'Refuse to rebuild path outside case/: {dest}') from exc
        shutil.rmtree(dest)

    dest.mkdir(parents=True, exist_ok=True)
    yaml_path = dest / 'case.yaml'
    if rebuild or not yaml_path.is_file():
        with yaml_path.open('w', encoding='utf-8') as f:
            yaml.safe_dump(recipe, f, allow_unicode=True, sort_keys=False)
    else:
        existing = load_case_spec(yaml_path)
        if str(existing.get('case_id') or '').strip() != cid:
            raise ValueError(f'{yaml_path}: case_id must be {cid!r}')
    _copy_profile_extras(repo, cid, dest)
    init_case_workspace(
        yaml_path,
        repo_root=repo,
        apply_keys=apply_keys,
        rebuild=rebuild,
        init_ui=init_ui,
    )
    return dest


def delete_case(
    case_id: str,
    *,
    repo_root: Path | None = None,
    start: Path | None = None,
    force: bool = False,
) -> None:
    repo = repo_root or find_repo_root(start)
    cid = normalize_case_id(case_id)
    dest = case_workspace_dir(repo, cid)
    try:
        dest.relative_to((repo / CASE_DIR_NAME).resolve())
    except ValueError as exc:
        raise ValueError(f'Refuse to delete path outside case/: {dest}') from exc
    if not dest.exists():
        raise FileNotFoundError(f'Case workspace not found: {dest.relative_to(repo).as_posix()}')
    if not force:
        raise ValueError('Refusing to delete without --force')
    shutil.rmtree(dest)
