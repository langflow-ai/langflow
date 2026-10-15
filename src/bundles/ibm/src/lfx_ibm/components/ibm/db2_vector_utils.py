"""Db2 vector helpers, preserving distance values and zero-vector MMR behavior."""

from enum import Enum

import numpy as np


class DistanceStrategy(str, Enum):
    """Distance names accepted by existing Db2 callers."""

    EUCLIDEAN_DISTANCE = "EUCLIDEAN_DISTANCE"
    MAX_INNER_PRODUCT = "MAX_INNER_PRODUCT"
    DOT_PRODUCT = "DOT_PRODUCT"
    JACCARD = "JACCARD"
    COSINE = "COSINE"


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    denominator = np.outer(np.linalg.norm(left, axis=1), np.linalg.norm(right, axis=1))
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = (left @ right.T) / denominator
    # Historically a zero vector has zero similarity, including when every row is zero.
    return np.where(np.isfinite(scores), scores, 0.0)


def maximal_marginal_relevance(
    query_embedding: np.ndarray,
    embedding_list: list[list[float]],
    lambda_mult: float = 0.5,
    k: int = 4,
) -> list[int]:
    """Select relevant, diverse candidates, resolving ties in original retrieval order."""
    if min(k, len(embedding_list)) <= 0:
        return []
    embeddings = np.asarray(embedding_list)
    query_scores = _cosine_similarity(np.atleast_2d(query_embedding), embeddings)[0]
    selected = [int(np.argmax(query_scores))]
    while len(selected) < min(k, len(embeddings)):
        redundancy = _cosine_similarity(embeddings, embeddings[selected]).max(axis=1)
        scores = lambda_mult * query_scores - (1 - lambda_mult) * redundancy
        scores[selected] = -np.inf
        selected.append(int(np.argmax(scores)))
    return selected
