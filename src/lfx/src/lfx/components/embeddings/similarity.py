from typing import Any

import numpy as np

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, Output
from lfx.schema.data import Data


class EmbeddingSimilarityComponent(Component):
    display_name: str = "Embedding Similarity"
    description: str = "Compute selected form of similarity between two embedding vectors."
    icon = "equal"
    legacy: bool = True

    inputs = [
        DataInput(
            name="embedding_vectors",
            display_name="Embedding Vectors",
            info="A list containing exactly two data objects with embedding vectors to compare.",
            is_list=True,
            required=True,
        ),
        DropdownInput(
            name="similarity_metric",
            display_name="Similarity Metric",
            info="Select the similarity metric to use.",
            options=["Cosine Similarity", "Euclidean Distance", "Manhattan Distance"],
            value="Cosine Similarity",
        ),
    ]

    outputs = [
        Output(display_name="Similarity Data", name="similarity_data", method="compute_similarity"),
    ]

    def compute_similarity(self) -> Data:
        embedding_vectors: list[Data] = self.embedding_vectors

        # Assert that the list contains exactly two Data objects
        if len(embedding_vectors) != 2:  # noqa: PLR2004
            msg = "Exactly two embedding vectors are required."
            raise ValueError(msg)

        embedding_1 = np.array(embedding_vectors[0].data["embeddings"])
        embedding_2 = np.array(embedding_vectors[1].data["embeddings"])

        if embedding_1.shape != embedding_2.shape:
            similarity_score: dict[str, Any] = {"error": "Embeddings must have the same dimensions."}
        else:
            similarity_metric = self.similarity_metric

            if similarity_metric == "Cosine Similarity":
                score = np.dot(embedding_1, embedding_2) / (np.linalg.norm(embedding_1) * np.linalg.norm(embedding_2))
                similarity_score = {"cosine_similarity": score}

            elif similarity_metric == "Euclidean Distance":
                score = np.linalg.norm(embedding_1 - embedding_2)
                similarity_score = {"euclidean_distance": score}

            elif similarity_metric == "Manhattan Distance":
                score = np.sum(np.abs(embedding_1 - embedding_2))
                similarity_score = {"manhattan_distance": score}

        # Create a Data object to encapsulate the similarity score and additional information
        similarity_data = Data(
            data={
                "embedding_1": embedding_vectors[0].data["embeddings"],
                "embedding_2": embedding_vectors[1].data["embeddings"],
                "similarity_score": similarity_score,
            },
            text_key="similarity_score",
        )

        self.status = similarity_data
        return similarity_data
