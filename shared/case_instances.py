"""List and resolve ssj instance dirs under a Case workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.arena_runner import check_case_keys
from shared.case_spec import CaseSpecView, parse_case_spec
from shared.case_workspace import instance_dir_name
from ssj.models_store import load_models_store


@dataclass(frozen=True)
class InstanceRow:
    profile: str
    instance_dir: str
    path: Path
    materialized: bool
    default_litellm: str | None
    missing_keys: tuple[str, ...]


def list_instances(case_yaml: Path) -> tuple[CaseSpecView, list[InstanceRow]]:
    spec = parse_case_spec(case_yaml)
    key_map = check_case_keys(spec)
    rows: list[InstanceRow] = []
    for profile in spec.profiles:
        inst = instance_dir_name(spec.agent_line, profile)
        root = spec.case_dir / inst
        litellm: str | None = None
        if root.is_dir() and (root / 'models.yaml').is_file():
            try:
                litellm = load_models_store(root).default_litellm()
            except (OSError, ValueError):
                litellm = None
        missing = tuple(key_map.get(profile) or ())
        rows.append(
            InstanceRow(
                profile=profile,
                instance_dir=inst,
                path=root,
                materialized=root.is_dir(),
                default_litellm=litellm,
                missing_keys=missing,
            )
        )
    return spec, rows


def resolve_profile_selector(spec: CaseSpecView, name: str) -> str:
    """Accept profile alias (ds) or instance dir (ssj-ds)."""
    raw = name.strip()
    if not raw:
        raise ValueError('Empty --name')
    if raw in spec.profiles:
        return raw
    prefix = f'{spec.agent_line}-'
    if raw.startswith(prefix):
        profile = raw[len(prefix) :]
        if profile in spec.profiles:
            return profile
    raise ValueError(
        f'Unknown instance {raw!r}. '
        f'Use profile in {list(spec.profiles)} or {prefix}<profile>.'
    )


def expand_name_tokens(name_filter: tuple[str, ...]) -> tuple[str, ...]:
    """Split `--name ds,kimi` and repeated `--name` into individual tokens."""
    tokens: list[str] = []
    for raw in name_filter:
        for part in raw.split(','):
            token = part.strip()
            if token:
                tokens.append(token)
    return tuple(tokens)


def resolve_profile_selectors(spec: CaseSpecView, names: tuple[str, ...]) -> tuple[str, ...]:
    if not names:
        return spec.profiles
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        profile = resolve_profile_selector(spec, name)
        if profile not in seen:
            seen.add(profile)
            out.append(profile)
    return tuple(out)
