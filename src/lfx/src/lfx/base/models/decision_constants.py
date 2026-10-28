"""Hosted decision models; capabilities are independent of generating models."""

from lfx.base.models.model_metadata import create_model_metadata


def is_decision_row(row: dict) -> bool:
    """Whether a catalog row describes a decision model."""
    return (row.get("metadata") or {}).get("model_type") == "decision"


# Registered only for decisions: never a generating-model or assistant provider.
DECISION_ONLY_PROVIDERS = frozenset({"TypeSafe", "Perplexity"})

DECISION_MODELS_DETAILED = [
    {
        **create_model_metadata(provider=provider, name=name, icon=icon, model_type="decision"),
        "capabilities": ["choice", "boolean", "score"],
    }
    for provider, name, icon in (
        ("TypeSafe", "jev-latest", "Bot"),
        ("Perplexity", "pplx-decider-latest", "Perplexity"),
        ("Perplexity", "pplx-decider-flash-latest", "Perplexity"),
        ("OpenAI", "gpt-6-luna", "OpenAI"),
    )
]
