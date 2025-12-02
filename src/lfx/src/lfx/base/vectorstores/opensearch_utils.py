"""Utility functions for OpenSearch components."""

from __future__ import annotations

from lfx.log import logger


def normalize_model_name(model_name: str) -> str:
    """Normalize embedding model name for use as field suffix.

    Converts model names to valid OpenSearch field names by replacing
    special characters and ensuring alphanumeric format.

    Args:
        model_name: Original embedding model name (e.g., "text-embedding-3-small")

    Returns:
        Normalized field suffix (e.g., "text_embedding_3_small")
    """
    normalized = model_name.lower()
    # Replace common separators with underscores
    normalized = normalized.replace("-", "_").replace(":", "_").replace("/", "_").replace(".", "_")
    # Remove any non-alphanumeric characters except underscores
    normalized = "".join(c if c.isalnum() or c == "_" else "_" for c in normalized)
    # Remove duplicate underscores
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def get_embedding_field_name(model_name: str) -> str:
    """Get the dynamic embedding field name for a model.

    Args:
        model_name: Embedding model name

    Returns:
        Field name in format: chunk_embedding_{normalized_model_name}
    """
    field_name = f"chunk_embedding_{normalize_model_name(model_name)}"
    logger.info(f"Generated embedding field name: {field_name}")
    return field_name


def get_embedding_model_name_from_obj(embedding_obj) -> str | None:
    """Extract model name from an embedding object.

    Priority: deployment > model > model_id > model_name

    Args:
        embedding_obj: Embedding object to extract name from

    Returns:
        Model name string or None if not found
    """
    if not embedding_obj:
        return None

    if hasattr(embedding_obj, "deployment") and embedding_obj.deployment:
        return str(embedding_obj.deployment)
    if hasattr(embedding_obj, "model") and embedding_obj.model:
        return str(embedding_obj.model)
    if hasattr(embedding_obj, "model_id") and embedding_obj.model_id:
        return str(embedding_obj.model_id)
    if hasattr(embedding_obj, "model_name") and embedding_obj.model_name:
        return str(embedding_obj.model_name)

    return None


def build_embedding_identifiers(emb_obj) -> list[str]:
    """Build list of all possible identifiers for an embedding object.

    Args:
        emb_obj: Embedding object

    Returns:
        List of identifier strings
    """
    identifiers = []
    deployment = getattr(emb_obj, "deployment", None)
    model = getattr(emb_obj, "model", None)
    model_id = getattr(emb_obj, "model_id", None)
    model_name = getattr(emb_obj, "model_name", None)
    available_models_attr = getattr(emb_obj, "available_models", None)

    if deployment:
        identifiers.append(str(deployment))
    if model:
        identifiers.append(str(model))
    if model_id:
        identifiers.append(str(model_id))
    if model_name:
        identifiers.append(str(model_name))

    # Add combined identifier for disambiguation
    if deployment and model and deployment != model:
        identifiers.append(f"{deployment}:{model}")

    # Add available_models keys
    if available_models_attr and isinstance(available_models_attr, dict):
        identifiers.extend(
            str(model_key).strip() for model_key in available_models_attr if model_key and str(model_key).strip()
        )

    return identifiers


def build_embedding_info_string(emb_obj, idx: int) -> str:
    """Build a human-readable info string for an embedding object.

    Args:
        emb_obj: Embedding object
        idx: Index of the embedding in the list

    Returns:
        Formatted string with embedding details
    """
    emb_type = type(emb_obj).__name__
    identifiers = []
    deployment = getattr(emb_obj, "deployment", None)
    model = getattr(emb_obj, "model", None)
    model_id = getattr(emb_obj, "model_id", None)
    model_name = getattr(emb_obj, "model_name", None)
    available_models_attr = getattr(emb_obj, "available_models", None)

    if deployment:
        identifiers.append(f"deployment='{deployment}'")
    if model:
        identifiers.append(f"model='{model}'")
    if model_id:
        identifiers.append(f"model_id='{model_id}'")
    if model_name:
        identifiers.append(f"model_name='{model_name}'")

    if deployment and model and deployment != model:
        identifiers.append(f"combined='{deployment}:{model}'")

    if available_models_attr and isinstance(available_models_attr, dict):
        identifiers.append(f"available_models={list(available_models_attr.keys())}")

    return f"  [{idx}] {emb_type}: {', '.join(identifiers) if identifiers else 'No identifiers'}"
