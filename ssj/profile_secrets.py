"""Interactive .env keys for a model id (provider/name)."""

from __future__ import annotations

import os
from typing import Literal

import click

from cli.console import CONSOLE
from ssj.secret_prompt import prompt_masked_secret
from ssj.model_secrets import (
    EnvKeySpec,
    _UNKNOWN_HINT,
    env_value_for_model,
    reconcile_legacy_openrouter_typesafe_env,
    resolve_secrets_for_model,
)
from ssj.settings import mask_secret, set_env_key

ExistingKeyPolicy = Literal['confirm', 'enter_to_keep', 'skip']


def configure_secrets_for_litellm(
    model_id: str,
    *,
    existing_key: ExistingKeyPolicy = 'confirm',
    skip_env_names: frozenset[str] | None = None,
) -> bool:
    """Prompt for provider keys. Returns False if model has no registered secrets."""
    specs = resolve_secrets_for_model(model_id)
    if not specs:
        CONSOLE.print(f'[bold red]{_UNKNOWN_HINT}[/bold red]')
        return False

    skipped = skip_env_names or frozenset()
    from ssj.settings import resolve_root

    root = resolve_root()
    reconcile_legacy_openrouter_typesafe_env(
        env_path=root / '.env',
        litellm_models=(model_id,),
    )
    for spec in specs:
        if spec.name in skipped:
            continue
        _configure_one_spec(spec, model_id, existing_key=existing_key)
    return True


def _configure_one_spec(
    spec: EnvKeySpec, model_id: str, *, existing_key: ExistingKeyPolicy
) -> None:
    existing = env_value_for_model(model_id, spec.name)
    if existing and existing_key == 'skip':
        CONSOLE.print(f'[dim]{spec.name}[/dim] kept ({mask_secret(spec.name)})')
        return

    if existing and existing_key == 'confirm':
        if not click.confirm(f'Replace {spec.name} ({mask_secret(spec.name)})?', default=False):
            return

    if not spec.required and not existing:
        if not click.confirm(f'Set optional {spec.name}?', default=False):
            return

    if existing and existing_key == 'enter_to_keep':
        label = f'{spec.name} (Enter to keep, or paste new): '
        value = prompt_masked_secret(label)
        if not value.strip():
            CONSOLE.print(f'[dim]{spec.name}[/dim] kept ({mask_secret(spec.name)})')
            return
        _save_env_key(spec, model_id, value)
        return

    value = prompt_masked_secret(f'{spec.name}: ')
    if not value.strip():
        if spec.required:
            CONSOLE.print(f'[yellow]Skipped {spec.name} (required for runs).[/yellow]')
        return
    _save_env_key(spec, model_id, value)


def _save_env_key(spec: EnvKeySpec, model_id: str, value: str) -> None:
    try:
        set_env_key(spec.name, value, model=model_id)
    except ValueError as exc:
        CONSOLE.print(f'[bold red]{exc}[/bold red]')
        raise SystemExit(1) from exc
    CONSOLE.print(f'[green]{spec.name}[/green] saved.')
