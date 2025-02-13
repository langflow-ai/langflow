import numpy as np
import pytest

from langflow.components.embeddings import EmbeddingSimilarityComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestEmbeddingSimilarityComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return EmbeddingSimilarityComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "embedding_vectors": [
                {"data": {"embeddings": [1.0, 2.0, 3.0]}},
                {"data": {"embeddings": [4.0, 5.0, 6.0]}},
            ],
            "similarity_metric": "Cosine Similarity",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_compute_similarity_cosine(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.compute_similarity()

        # Assert
        expected_score = np.dot([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]) / (
            np.linalg.norm([1.0, 2.0, 3.0]) * np.linalg.norm([4.0, 5.0, 6.0])
        )
        assert result.data["similarity_score"]["cosine_similarity"] == pytest.approx(expected_score)

    def test_compute_similarity_euclidean(self, component_class, default_kwargs):
        # Arrange
        default_kwargs["similarity_metric"] = "Euclidean Distance"
        component = component_class(**default_kwargs)

        # Act
        result = component.compute_similarity()

        # Assert
        expected_score = np.linalg.norm(np.array([1.0, 2.0, 3.0]) - np.array([4.0, 5.0, 6.0]))
        assert result.data["similarity_score"]["euclidean_distance"] == pytest.approx(expected_score)

    def test_compute_similarity_manhattan(self, component_class, default_kwargs):
        # Arrange
        default_kwargs["similarity_metric"] = "Manhattan Distance"
        component = component_class(**default_kwargs)

        # Act
        result = component.compute_similarity()

        # Assert
        expected_score = np.sum(np.abs(np.array([1.0, 2.0, 3.0]) - np.array([4.0, 5.0, 6.0])))
        assert result.data["similarity_score"]["manhattan_distance"] == expected_score

    def test_compute_similarity_invalid_vector_count(self, component_class):
        # Arrange
        component = component_class(
            embedding_vectors=[{"data": {"embeddings": [1.0, 2.0]}}, {"data": {"embeddings": [3.0]}}]
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Exactly two embedding vectors are required."):
            component.compute_similarity()

    def test_compute_similarity_dimension_mismatch(self, component_class):
        # Arrange
        component = component_class(
            embedding_vectors=[{"data": {"embeddings": [1.0, 2.0, 3.0]}}, {"data": {"embeddings": [4.0, 5.0]}}]
        )

        # Act
        result = component.compute_similarity()

        # Assert
        assert result.data["similarity_score"]["error"] == "Embeddings must have the same dimensions."
