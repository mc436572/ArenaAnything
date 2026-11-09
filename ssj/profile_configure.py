"""Interactive profile setup: model id → API base → secrets."""

from __future__ import annotations

import os

import click

from cli.console import CONSOLE
from ssj.profile_secrets import configure_secrets_for_litellm
from ssj.model_catalog import BUILTIN_CATALOG
from ssj.model_secrets import allowed_key_names_for_model
from ssj.models_store import ModelsStore, update_profile
from ssj.provider_routing import match_provider, resolved_api_root
from ssj.settings import set_env_key


def prompt_model_id(default: str = '') -> str:
    value = click.prompt('Model id (provider/name)', default=default, type=str).strip()
    if not value:
        CONSOLE.print('[bold red]Model id cannot be empty.[/bold red]')
        raise SystemExit(1)
    return value


def catalog_default_model_id(alias: str) -> str | None:
    for entry in BUILTIN_CATALOG:
        if entry.alias == alias:
            return entry.litellm
    return None


def configure_profile(store: ModelsStore, alias: str) -> str:
    """Returns the final model id string for this profile."""
    prof = store.models[alias]
    original_id = prof.litellm
    CONSOLE.print(f'Configure profile [cyan]{alias}[/cyan]')

    model_id = _prompt_and_save_model_id(store, alias, original_id)
    _prompt_api_base(model_id)
    configure_secrets_for_litellm(
        model_id,
        existing_key='enter_to_keep',
        skip_env_names=_optional_base_env_names(model_id),
    )
    return model_id


def _optional_base_env_names(model_id: str) -> frozenset[str]:
    matched = match_provider(model_id)
    if matched is None:
        return frozenset()
    route, _ = matched
    if route.api_base_env:
        return frozenset({route.api_base_env})
    return frozenset()


def _prompt_api_base(model_id: str) -> None:
    matched = match_provider(model_id)
    if matched is None:
        CONSOLE.print('[dim]API base: (unknown provider — set env keys if needed)[/dim]')
        return
    route, _ = matched
    root = resolved_api_root(model_id) or route.default_api_root
    allowed = allowed_key_names_for_model(model_id)
    if route.api_base_env and route.api_base_env in allowed:
        value = click.prompt('API base URL', default=root, type=str).strip()
        if not value:
            CONSOLE.print('[yellow]Skipped API base.[/yellow]')
            return
        existing = os.environ.get(route.api_base_env, '').strip()
        if value == existing:
            CONSOLE.print(f'[dim]{route.api_base_env}[/dim] unchanged ({value})')
            return
        if not existing and value.rstrip('/') == route.default_api_root.rstrip('/'):
            CONSOLE.print(
                f'[dim]{route.api_base_env}[/dim] using default ({value})'
            )
            return
        try:
            set_env_key(route.api_base_env, value, model=model_id)
        except ValueError as exc:
            CONSOLE.print(f'[bold red]{exc}[/bold red]')
            raise SystemExit(1) from exc
        CONSOLE.print(f'[green]{route.api_base_env}[/green] saved.')
    else:
        CONSOLE.print(f'[dim]API base: {root}[/dim]')


def _prompt_and_save_model_id(store: ModelsStore, alias: str, current: str) -> str:
    new_id = click.prompt('Model id (provider/name)', default=current, type=str).strip()
    if not new_id:
        CONSOLE.print('[bold red]Model id cannot be empty.[/bold red]')
        raise SystemExit(1)
    if new_id != current:
        update_profile(store, alias, litellm=new_id)
        CONSOLE.print(f'Model id → [green]{new_id}[/green]')
    return new_id
