"""Provider-specific chat completion parameters."""

from __future__ import annotations

# Longest-prefix wins (same convention as model_reply / provider_routing).
_FIXED_TEMPERATURE_BY_PREFIX: tuple[tuple[str, float], ...] = (
    # Moonshot K3: API rejects temperature=0 ("only 1 is allowed for this model").
    ('moonshot/kimi-k3', 1.0),
)


def effective_chat_temperature(litellm_model: str, temperature: float | None) -> float | None:
    """Return temperature to send on the wire for this litellm id."""
    lower = litellm_model.strip().lower()
    matched: float | None = None
    best_len = -1
    for prefix, fixed in _FIXED_TEMPERATURE_BY_PREFIX:
        pl = prefix.lower()
        if lower.startswith(pl) and len(pl) > best_len:
            matched = fixed
            best_len = len(pl)
    if matched is not None:
        return matched
    return temperature
