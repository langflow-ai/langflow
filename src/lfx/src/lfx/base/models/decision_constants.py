"""Hosted decision models; capabilities are independent of generating models."""

from lfx.base.models.model_metadata import create_model_metadata


def is_decision_row(row: dict) -> bool:
    """Whether a catalog row describes a decision model."""
    return (row.get("metadata") or {}).get("model_type") == "decision"


# Registered only for decisions: never a generating-model or assistant provider.
DECISION_ONLY_PROVIDERS = frozenset({"TypeSafe", "Perplexity"})
# Decision catalogs read from the provider's model-list endpoint; the provider validates IDs at run time.
LIVE_DECISION_PROVIDERS = frozenset({"OpenRouter", "TypeSafe"})
DECISION_CAPABILITIES = ("choice", "boolean", "score")


def decision_model_metadata(provider: str, name: str, icon: str, *, default: bool = False) -> dict:
    """One decision catalog row, offering every Decision Type."""
    return {
        **create_model_metadata(provider=provider, name=name, icon=icon, model_type="decision", default=default),
        "capabilities": list(DECISION_CAPABILITIES),
    }


DECISION_MODELS_DETAILED = [
    decision_model_metadata(provider, name, icon)
    for provider, name, icon in (
        ("TypeSafe", "jev-latest", "Bot"),
        ("Perplexity", "pplx-decider-latest", "Perplexity"),
        ("Perplexity", "pplx-decider-flash-latest", "Perplexity"),
        ("OpenAI", "gpt-6-luna", "OpenAI"),
    )
]
