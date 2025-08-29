from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from langchain.evaluation.embedding_distance import EmbeddingDistance
from langchain_core.embeddings import Embeddings
from langflow.components.logic.classifier_router import (
    ClassifierRouterComponent,
    ClassifierType,
    EmbeddingClassifier,
    LLMClassifier,
)
from langflow.schema.message import Message


class TestEmbedding(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        text_lower = text.lower()
        if "titanic" in text_lower or "movies" in text_lower or "cinema" in text_lower:
            return [1.0, 0.0]
        if "football" in text_lower:
            return [0.0, 1.0]
        return [0.5, 0.5]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


def create_confident_llm():
    llm = MagicMock()
    runnable = MagicMock()
    runnable.invoke.return_value = '{"category_name": "Cinema", "confidence": 0.95}'
    llm.with_config.return_value = runnable
    return llm


def test_outputs_are_instance_scoped(sample_categories):
    c1 = ClassifierRouterComponent()
    c2 = ClassifierRouterComponent()
    c1.set_attributes({"categories_descriptions": sample_categories, "input_text": "x"})
    c1.update_outputs({"outputs": [{"name": "no_matches"}]}, "categories_descriptions", sample_categories)
    assert {o.name for o in c2.outputs} == {"no_matches"}


@pytest.fixture
def sample_categories():
    return [
        {"category": "Cinema", "description": "Everything about movies"},
        {"category": "Football", "description": "Everything about football"},
    ]


@pytest.fixture
def test_embedding():
    return TestEmbedding()


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    runnable = MagicMock()
    llm.with_config.return_value = runnable
    return llm


@pytest.fixture
def base_component(sample_categories):
    component = ClassifierRouterComponent()
    component.stop = MagicMock()
    component.set_attributes(
        {
            "categories_descriptions": sample_categories,
            "input_text": "Test text",
            "message": Message(text="Test text"),
        }
    )
    return component


class TestClassifierRouterComponent:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("input_text", "expected_outputs"),
        [
            ("Tell me about Titanic movie", {"Cinema", "Football", "no_matches"}),
            ("Who won the football match?", {"Cinema", "Football", "no_matches"}),
        ],
    )
    async def test_dynamic_outputs_creation(self, sample_categories, input_text, expected_outputs):
        component = ClassifierRouterComponent()

        # Initially should have only base outputs
        initial_outputs = {out.name for out in component.outputs}
        assert len(initial_outputs) == 1

        component.set_attributes(
            {
                "categories_descriptions": sample_categories,
                "input_text": input_text,
            }
        )

        frontend_node = {
            "outputs": [
                {
                    "types": ["Message"],
                    "selected": "Message",
                    "name": "no_matches",
                    "display_name": "no matches",
                    "method": "no_matches_response",
                    "value": "__UNDEFINED__",
                    "cache": True,
                    "allows_loop": False,
                    "group_outputs": True,
                    "tool_mode": True,
                }
            ]
        }

        updated_node = component.update_outputs(frontend_node, "categories_descriptions", sample_categories)

        # Verify outputs were created correctly
        output_names = {out.name for out in component.outputs}
        frontend_output_names = {o["name"] for o in updated_node["outputs"]}

        assert output_names == expected_outputs
        assert frontend_output_names == expected_outputs

        # Verify all methods exist
        for output in updated_node["outputs"]:
            method_name = output["method"]
            assert hasattr(component, method_name), f"Method {method_name} not found"

    @pytest.mark.parametrize(
        ("classifier_config", "test_input", "expected_cinema", "expected_football"),
        [
            # Embedding classifier - single match
            (
                {
                    "classifier_type": ClassifierType.EMBEDDING.value,
                    "distance_threshold": 0.5,
                    "top_n_values": 1,
                    "distance_metric": EmbeddingDistance.COSINE,
                },
                "Titanic movie",
                True,
                False,
            ),
            # Embedding classifier - multiple matches
            (
                {
                    "classifier_type": ClassifierType.EMBEDDING.value,
                    "distance_threshold": 1.0,
                    "top_n_values": 2,
                    "distance_metric": EmbeddingDistance.COSINE,
                },
                "General text",
                True,
                True,
            ),
            # LLM classifier - single match (high confidence)
            (
                {
                    "classifier_type": ClassifierType.LLM.value,
                    "confidence_threshold": 0.8,
                    "use_with_structured_output": False,
                    "use_history": False,
                    "llm_response": '{"category_name": "Cinema", "confidence": 0.95}',
                },
                "Test text",
                True,
                False,
            ),
            # LLM classifier - no matches (low confidence)
            (
                {
                    "classifier_type": ClassifierType.LLM.value,
                    "confidence_threshold": 0.8,
                    "use_with_structured_output": False,
                    "use_history": False,
                    "llm_response": '{"category_name": "Cinema", "confidence": 0.3}',
                },
                "Test text",
                False,
                False,
            ),
        ],
    )
    def test_classification_scenarios(
        self,
        base_component,
        test_embedding,
        mock_llm,
        classifier_config,
        test_input,
        expected_cinema,
        expected_football,
    ):
        component = base_component
        component.classifier_type = classifier_config["classifier_type"]
        component.set_attributes({"input_text": test_input, "message": Message(text=test_input)})

        if classifier_config["classifier_type"] == ClassifierType.EMBEDDING.value:
            component.embedding = test_embedding
            component.set_attributes({k: v for k, v in classifier_config.items() if k != "classifier_type"})
        else:  # llm
            mock_llm.with_config().invoke.return_value = classifier_config.pop("llm_response")
            component.llm = mock_llm

            with patch.object(type(component), "graph", new_callable=PropertyMock) as mock_graph_prop:
                mock_graph_prop.return_value = MagicMock(session_id="sess", run_id="run")

                component.set_attributes({k: v for k, v in classifier_config.items() if k != "classifier_type"})

        component._initialize_outputs(["Cinema", "Football"])

        cinema_result = component._check_Cinema()
        football_result = component._check_Football()
        no_matches_result = component.no_matches_response()

        if expected_cinema:
            assert cinema_result == component.message.text
        else:
            assert cinema_result is None

        if expected_football:
            assert football_result == component.message.text
        else:
            assert football_result is None

        if not expected_cinema and not expected_football:
            assert no_matches_result == component.message.text
        else:
            assert no_matches_result is None

    def test_classifier_type_embedding_gates_llm(self, sample_categories, test_embedding):
        component = ClassifierRouterComponent()
        # component.llm = mock_llm  # present but should not be used
        component.embedding = test_embedding
        component.distance_threshold = 1.0
        component.distance_metric = EmbeddingDistance.COSINE
        component.classifier_type = ClassifierType.EMBEDDING.value
        component.top_n_values = 1
        component.set_attributes({"categories_descriptions": sample_categories, "input_text": "Titanic"})
        # If LLM were used, we'd need a response; absence implies embedding used.
        component._initialize_outputs(["Cinema"])
        assert component._check_Cinema() is not None

    def test_classifier_type_llm_gates_embedding(self, sample_categories, test_embedding, mock_llm):
        component = ClassifierRouterComponent()
        component.embedding = test_embedding  # present but should not be used
        mock_llm.with_config().invoke.return_value = '{"category_name":"Cinema","confidence":0.95}'
        component.llm = mock_llm
        with patch.object(type(component), "graph", new_callable=PropertyMock) as mock_graph_prop:
            mock_graph_prop.return_value = MagicMock(session_id="sess", run_id="run")
            component.classifier_type = ClassifierType.LLM.value
            component.set_attributes({"categories_descriptions": sample_categories, "input_text": "Test"})
        component._initialize_outputs(["Cinema"])
        assert component._check_Cinema() is not None


class TestLLMClassifier:
    @pytest.mark.parametrize(
        ("response", "confidence_threshold", "expected_categories"),
        [
            ('{"category_name": "Cinema", "confidence": 0.95}', 0.8, ["Cinema"]),
            ('{"category_name": "Cinema", "confidence": 0.3}', 0.8, []),
            ('{"category_name": "Football", "confidence": 0.9}', 0.8, ["Football"]),
        ],
    )
    def test_confidence_based_classification(
        self, sample_categories, mock_llm, response, confidence_threshold, expected_categories
    ):
        mock_llm.with_config().invoke.return_value = response

        classifier = LLMClassifier(
            llm=mock_llm,
            input_text="Test text",
            categories_descriptions=sample_categories,
            classifier_prompt="Classify {input_text} into {categories}",
            callbacks=[],
            use_with_structured_output=False,
            confidence_threshold=confidence_threshold,
        )

        classifier.process_result()
        assert classifier.top_n_values_name == expected_categories

    def test_structured_output_fallback(self, sample_categories, mock_llm):
        mock_llm.with_config().invoke.return_value = '{"category_name": "Cinema", "confidence": 0.95}'

        classifier = LLMClassifier(
            llm=mock_llm,
            input_text="Test text",
            categories_descriptions=sample_categories,
            classifier_prompt="Classify {input_text} into {categories}",
            callbacks=[],
            use_with_structured_output=True,
            confidence_threshold=0.8,
        )

        with patch.object(classifier, "get_structured_output", side_effect=ValueError("Structured output failed")):
            classifier.process_result()

        assert classifier.top_n_values_name == ["Cinema"]


class TestEmbeddingClassifier:
    @pytest.mark.parametrize(
        ("input_text", "distance_threshold", "top_n", "expected_count", "expected_category"),
        [
            ("Tell me about Titanic", 0.5, 1, 1, "Cinema"),  # Single confident match
            ("Tell me about Titanic", 0.0, 1, 0, None),  # Too strict threshold
            ("General text", 1.0, 2, 2, None),  # Multiple matches allowed
            ("Football match", 0.5, 1, 1, "Football"),  # Different category match
        ],
    )
    def test_embedding_classification_scenarios(
        self,
        sample_categories,
        test_embedding,
        input_text,
        distance_threshold,
        top_n,
        expected_count,
        expected_category,
    ):
        classifier = EmbeddingClassifier(
            embedding=test_embedding,
            input_text=input_text,
            categories_descriptions=sample_categories,
            distance_threshold=distance_threshold,
            top_n_values=top_n,
        )

        classifier.initialize_embeddings()
        classifier.calculate_distance()

        assert len(classifier.top_n_values_name) == expected_count
        if expected_category and expected_count == 1:
            assert expected_category in classifier.top_n_values_name
