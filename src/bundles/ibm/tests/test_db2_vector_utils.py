"""Compatibility contracts for Community-free Db2 vector helpers."""

from enum import Enum
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from lfx_ibm.components.ibm.db2_vector_utils import DistanceStrategy, maximal_marginal_relevance
from lfx_ibm.components.ibm.db2vs import DB2VS


@pytest.mark.parametrize(
    ("query", "vectors", "weight", "k", "expected"),
    [
        ([1, 0], [[1, 0], [0.9, 0.1], [0, 1]], 1, 3, [0, 1, 2]),
        ([1, 0], [[1, 0], [0.9, 0.1], [0, 1]], 0, 3, [0, 2, 1]),
        ([1, 0], [[0, 0], [0, 0]], 0.5, 4, [0, 1]),
        ([0, 0], [[1, 0], [1, 0], [0, 1]], 0.5, 3, [0, 2, 1]),
        ([1, 0], [[1, 0], [1, 0]], 0.5, 2, [0, 1]),
        ([1, 0], [], 0.5, 4, []),
        ([1, 0], [[1, 0]], 0.5, 0, []),
    ],
)
def test_mmr_relevance_diversity_ties_and_zero_vectors(query, vectors, weight, k, expected):
    assert maximal_marginal_relevance(np.array(query), vectors, lambda_mult=weight, k=k) == expected


def test_from_texts_accepts_legacy_string_enum():
    class LegacyDistanceStrategy(str, Enum):
        COSINE = "COSINE"

    with (
        patch("lfx_ibm.components.ibm.db2vs.drop_table"),
        patch.object(DB2VS, "__init__", return_value=None) as initialize,
        patch.object(DB2VS, "add_texts"),
    ):
        DB2VS.from_texts(["document"], MagicMock(), client=MagicMock(), distance_strategy=LegacyDistanceStrategy.COSINE)
    assert initialize.call_args.kwargs["distance_strategy"] is DistanceStrategy.COSINE
