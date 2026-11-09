"""Distribute API keys from a local secrets pool into ssj-<profile>/.env (never committed)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, set_key

from ssj.model_secrets import resolve_secrets_for_model


class SecretsPoolError(ValueError):
    pass


def resolve_secrets_pool_path(
    *,
    repo_root: Path,
    case_dir: Path,
    case_spec: dict,
) -> Path:
    """Locate the secrets pool .env (gitignored)."""
    # Canonical name first; SSAIYAN_SECRETS kept as a deprecated alias so existing
    # local setups keep working after the project rename.
    override = os.environ.get('ARENAANYTHING_SECRETS', '').strip()
    legacy = not override
    if not override:
        override = os.environ.get('SSAIYAN_SECRETS', '').strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            env_name = 'SSAIYAN_SECRETS' if legacy else 'ARENAANYTHING_SECRETS'
            raise SecretsPoolError(
                f'{env_name} points to missing file: {path}'
            )
        return path.resolve()

    secrets = case_spec.get('secrets') or {}
    if isinstance(secrets, dict):
        rel = str(secrets.get('file') or '').strip()
        if rel:
            path = (case_dir / rel).resolve()
            if not path.is_file():
                path = (repo_root / rel).resolve()
            if not path.is_file():
                raise SecretsPoolError(
                    f'Secrets pool not found: {rel!r} (case secrets.file or repo-relative)'
                )
            return path

    default = (repo_root / '.env').resolve()
    if not default.is_file():
        raise SecretsPoolError(
            'No secrets pool: create repo-root .env, set ARENAANYTHING_SECRETS, '
            'or case.yaml secrets.file — then re-run arena init'
        )
    return default


def load_secrets_pool(path: Path) -> dict[str, str]:
    raw = dotenv_values(path)
    out: dict[str, str] = {}
    for key, val in raw.items():
        if val is None:
            continue
        text = str(val).strip()
        if text and key:
            out[str(key)] = text
    return out


def _existing_env(instance_root: Path) -> dict[str, str]:
    path = instance_root / '.env'
    if not path.is_file():
        return {}
    raw = dotenv_values(path)
    out: dict[str, str] = {}
    for key, val in raw.items():
        if val is None:
            continue
        text = str(val).strip()
        if text and key:
            out[str(key)] = text
    return out


def missing_required_secret_names(instance_root: Path, litellm: str) -> list[str]:
    missing: list[str] = []
    local = _existing_env(instance_root)
    for spec in resolve_secrets_for_model(litellm):
        if not spec.required:
            continue
        if not local.get(spec.name, '').strip():
            missing.append(spec.name)
    return missing


def apply_secrets_to_instance(
    instance_root: Path,
    litellm: str,
    pool: dict[str, str],
    *,
    force: bool,
) -> None:
    """Write keys from pool into instance_root/.env (required + optional when pool has value)."""
    instance_root.mkdir(parents=True, exist_ok=True)
    env_path = instance_root / '.env'
    local = _existing_env(instance_root)
    gaps: list[str] = []

    for spec in resolve_secrets_for_model(litellm):
        pool_val = pool.get(spec.name, '').strip()
        has_local = bool(local.get(spec.name, '').strip())

        if not spec.required:
            if not pool_val:
                continue
            if force or not has_local:
                set_key(str(env_path), spec.name, pool_val)
            continue

        if force:
            if not pool_val:
                gaps.append(spec.name)
                continue
            set_key(str(env_path), spec.name, pool_val)
            continue
        if has_local:
            continue
        if not pool_val:
            gaps.append(spec.name)
            continue
        set_key(str(env_path), spec.name, pool_val)

    if gaps:
        prof = instance_root.name
        raise SecretsPoolError(
            f'{prof}: secrets pool missing required key(s): {", ".join(gaps)}'
        )

    if env_path.is_file():
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass


def apply_secrets_for_case(
    *,
    case_dir: Path,
    repo_root: Path,
    case_spec: dict,
    agent_line: str,
    profiles: list[str],
    force: bool,
) -> None:
    from shared.case_workspace import instance_dir_name

    pool_path = resolve_secrets_pool_path(
        repo_root=repo_root, case_dir=case_dir, case_spec=case_spec
    )
    pool = load_secrets_pool(pool_path)
    if not pool:
        raise SecretsPoolError(f'Secrets pool is empty: {pool_path}')

    errors: list[str] = []
    for profile in profiles:
        name = str(profile).strip()
        if not name:
            continue
        inst = case_dir / instance_dir_name(agent_line, name)
        if not (inst / 'models.yaml').is_file():
            errors.append(f'{inst.name}: not materialized (missing models.yaml)')
            continue
        from ssj.models_store import load_models_store

        try:
            litellm = load_models_store(inst).default_litellm()
            apply_secrets_to_instance(inst, litellm, pool, force=force)
        except (OSError, ValueError, SecretsPoolError) as exc:
            errors.append(str(exc))
    if errors:
        raise SecretsPoolError('\n'.join(errors))
