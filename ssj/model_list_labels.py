"""Labels for ssj model list (profile kind vs credentials readiness)."""

from __future__ import annotations

from ssj.model_secrets import env_value_for_model, resolve_secrets_for_model
from ssj.models_store import ModelProfile

TYPE_BUILTIN = 'built-in'
TYPE_CUSTOM = 'custom'

KEYS_CONFIGURED = 'configured'
KEYS_MISSING = 'missing'
KEYS_UNKNOWN = 'unknown'


def profile_type_label(prof: ModelProfile) -> str:
    return TYPE_BUILTIN if prof.builtin else TYPE_CUSTOM


def profile_keys_label(litellm: str) -> str:
    """Whether required env keys for this profile are set in the process root."""
    specs = resolve_secrets_for_model(litellm)
    if not specs:
        return KEYS_UNKNOWN
    required = [s for s in specs if s.required]
    if not required:
        return KEYS_CONFIGURED
    if all(env_value_for_model(litellm, s.name) for s in required):
        return KEYS_CONFIGURED
    return KEYS_MISSING
