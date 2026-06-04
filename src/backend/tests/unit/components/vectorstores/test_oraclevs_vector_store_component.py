from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_oracledb.vectorstores.oraclevs import drop_table_purge
from lfx.components.oracledb import OracleVectorStoreComponent
from lfx.components.oracledb.connection import build_connection_params, split_credentialized_dsn
from lfx.schema.data import Data
from pydantic import BaseModel

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping
from tests.oracle_test_utils import (
    get_oracle_connection_inputs,
    get_oracle_connection_params,
    get_oracle_embedding_params,
    get_oracle_test_connection_inputs,
)


def _expected_connection_params(kwargs: dict[str, Any]) -> dict[str, Any]:
    return build_connection_params(
        kwargs.get("connection_params"),
        user=kwargs.get("user"),
        password=kwargs.get("password"),
        dsn=kwargs.get("dsn"),
        wallet_password=kwargs.get("wallet_password"),
    )


class _MetadataModel(BaseModel):
    value: str


def test_oracle_vector_store_connection_secrets_are_password_inputs() -> None:
    inputs = {input_.name: input_ for input_ in OracleVectorStoreComponent.inputs}

    for name in ("user", "password", "dsn", "wallet_password"):
        assert inputs[name].password is True

    assert inputs["connection_params"].advanced is True
    assert "Non-secret" in inputs["connection_params"].info


def test_connection_params_rejects_sensitive_keys() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "connection_params contains sensitive keys: connection_string, private_key\\. "
            "Use the dedicated secret fields"
        ),
    ):
        build_connection_params(
            {"connection_string": "user/password@host/service", "config_dir": "/wallet/config", "private_key": "key"},
            dsn="host/service",
        )


def test_connection_params_rejects_normalized_sensitive_keys() -> None:
    with pytest.raises(ValueError, match="connection_params contains sensitive keys"):
        build_connection_params(
            {"password ": "secret", "wallet-password": "wallet-secret"},
            dsn="host/service",
        )


def test_connection_params_allows_non_secret_sharding_keys() -> None:
    params = build_connection_params(
        {"shardingkey": ["tenant"], "supershardingkey": ["region"]},
        dsn="host/service",
    )

    assert params == {
        "dsn": "host/service",
        "shardingkey": ["tenant"],
        "supershardingkey": ["region"],
    }


def test_build_connection_params_parses_credentials_from_dsn() -> None:
    params = build_connection_params(
        {"config_dir": "/wallet/config"},
        dsn="user/p@ssword@host/service",
    )

    assert params == {
        "config_dir": "/wallet/config",
        "dsn": "host/service",
        "password": "p" + "@ssword",
        "user": "user",
    }


def test_split_credentialized_dsn_allows_at_sign_in_password() -> None:
    user, password, dsn = split_credentialized_dsn("user/p@ssword@host/service")

    assert user == "user"
    assert password == "p" + "@ssword"
    assert dsn == "host/service"


class TestOracleVectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return OracleVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self, request) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        connection_params = get_oracle_connection_params()
        if connection_params:
            from lfx.components.oracledb import OracleEmbeddingsComponent

            embedding = OracleEmbeddingsComponent(
                **get_oracle_connection_inputs(connection_params),
                embedding_params=get_oracle_embedding_params(),
            ).build_embeddings()
        else:
            embedding = MagicMock(name="oracle_embedding")

        return {
            "embedding": embedding,
            "table_name": f"table_{request.node.name}",
            **get_oracle_connection_inputs(connection_params or get_oracle_test_connection_inputs()),
            "create_index": True,
            "index_params": {"idx_name": f"index_{request.node.name}", "idx_type": "HNSW"},
            "mutate_on_duplicate": False,
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    def test_create_db(self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]) -> None:
        """Test the create_collection method."""
        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        if get_oracle_connection_params():
            component.build_vector_store()
            return

        vector_store = MagicMock()
        with (
            patch("lfx.components.oracledb.oraclevs.oracledb.connect", return_value=MagicMock()) as mock_connect,
            patch("lfx.components.oracledb.oraclevs.OracleVS", return_value=vector_store) as mock_oracle_vs,
            patch("lfx.components.oracledb.oraclevs.create_index") as mock_create_index,
            patch("lfx.components.oracledb.oraclevs.version", return_value="1.1.0", create=True),
        ):
            assert component.build_vector_store() is vector_store

        mock_connect.assert_called_once_with(**_expected_connection_params(default_kwargs))
        mock_oracle_vs.assert_called_once()
        mock_create_index.assert_called_once()

    @pytest.mark.parametrize(
        ("search_type", "expected_search_type", "expected_kwargs"),
        [
            ("Similarity", "similarity", {"k": 2}),
            ("Similarity with score threshold", "similarity", {"k": 2}),
            ("MMR (Max Marginal Relevance)", "mmr", {"k": 2}),
        ],
    )
    def test_search_dispatches_to_expected_langchain_mode(
        self,
        component_class: type[OracleVectorStoreComponent],
        search_type: str,
        expected_search_type: str,
        expected_kwargs: dict[str, Any],
    ) -> None:
        component: OracleVectorStoreComponent = component_class().set(
            search_type=search_type,
            search_query="oracle vectors",
            number_of_results=2,
        )

        vector_store = MagicMock()
        vector_store.search.return_value = [Document(page_content="Oracle vector search result")]
        component._cached_vector_store = vector_store

        results = component.search_documents()

        assert len(results) == 1
        assert results[0].text == "Oracle vector search result"
        vector_store.search.assert_called_once_with(
            query="oracle vectors",
            search_type=expected_search_type,
            **expected_kwargs,
        )

    def test_similarity_search(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the similarity search functionality through the component."""
        # Create test data with distinct topics
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
            "The lazy dog sleeps all day long",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["search_type"] = "Similarity"
        default_kwargs["number_of_results"] = 2

        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)

        if not get_oracle_connection_params():
            vector_store = MagicMock()
            vector_store.search.side_effect = [
                [
                    Document(page_content="The lazy dog sleeps all day long"),
                    Document(page_content="The quick brown fox jumps over the lazy dog"),
                ],
                [
                    Document(page_content="The lazy dog sleeps all day long"),
                    Document(page_content="The quick brown fox jumps over the lazy dog"),
                    Document(page_content="Machine learning models process data"),
                ],
            ]
            component._cached_vector_store = vector_store
        else:
            component.build_vector_store()

        # Test similarity search through the component
        component.set(search_query="dog sleeping")
        results = component.search_documents()

        assert len(results) == 2
        # The most relevant results should be about dogs
        assert any("dog" in result.text.lower() for result in results)

        # Test with different number of results
        component.set(number_of_results=3)
        results = component.search_documents()
        assert len(results) == 3

        if get_oracle_connection_params():
            drop_table_purge(component.connection, default_kwargs["table_name"])

    def test_mmr_search(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the MMR search functionality through the component."""
        # Create test data with some similar documents
        test_data = [
            "The quick brown fox jumps",
            "The quick brown fox leaps",
            "The quick brown fox hops",
            "Something completely different about cats",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["search_type"] = "MMR (Max Marginal Relevance)"
        default_kwargs["number_of_results"] = 3

        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)

        if not get_oracle_connection_params():
            vector_store = MagicMock()
            vector_store.search.side_effect = [
                [
                    Document(page_content="The quick brown fox jumps"),
                    Document(page_content="The quick brown fox leaps"),
                    Document(page_content="Something completely different about cats"),
                ],
                [
                    Document(page_content="The quick brown fox jumps"),
                    Document(page_content="Something completely different about cats"),
                ],
            ]
            component._cached_vector_store = vector_store
        else:
            component.build_vector_store()

        # Test MMR search through the component
        component.set(search_query="quick fox")
        results = component.search_documents()

        assert len(results) == 3
        # Results should be diverse but relevant
        assert any("fox" in result.text.lower() for result in results)

        # Test with different settings
        component.set(number_of_results=2)
        diverse_results = component.search_documents()
        assert len(diverse_results) == 2

        if get_oracle_connection_params():
            drop_table_purge(component.connection, default_kwargs["table_name"])

    def test_search_with_different_types(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test search with different search types."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)

        if not get_oracle_connection_params():
            vector_store = MagicMock()
            vector_store.search.side_effect = [
                [
                    Document(page_content="Python is a popular programming language"),
                    Document(page_content="Machine learning models process data"),
                ],
                [
                    Document(page_content="Python is a popular programming language"),
                    Document(page_content="Machine learning models process data"),
                ],
            ]
            component._cached_vector_store = vector_store
        else:
            component.build_vector_store()

        # Test similarity search
        component.set(search_type="Similarity", search_query="programming languages")
        similarity_results = component.search_documents()
        assert len(similarity_results) == 2
        assert any("python" in result.text.lower() for result in similarity_results)

        # Test MMR search
        component.set(search_type="MMR (Max Marginal Relevance)", search_query="programming languages")
        mmr_results = component.search_documents()
        assert len(mmr_results) == 2

        # Test with empty query
        component.set(search_query="")
        empty_results = component.search_documents()
        assert len(empty_results) == 0

        if get_oracle_connection_params():
            drop_table_purge(component.connection, default_kwargs["table_name"])

    def test_legacy_score_threshold_search_type_falls_back_to_similarity(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Old saved flows using score-threshold mode should degrade to similarity."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)

        if not get_oracle_connection_params():
            vector_store = MagicMock()
            vector_store.search.side_effect = [
                [
                    Document(page_content="Python is a popular programming language"),
                    Document(page_content="The quick brown fox jumps over the lazy dog"),
                ],
                [
                    Document(page_content="Python is a popular programming language"),
                    Document(page_content="The quick brown fox jumps over the lazy dog"),
                    Document(page_content="Machine learning models process data"),
                ],
            ]
            component._cached_vector_store = vector_store
        else:
            component.build_vector_store()

        component.set(
            search_type="Similarity with score threshold",
            search_query="programming languages",
            number_of_results=2,
        )
        results = component.search_documents()

        assert len(results) == 2
        assert any("python" in result.text.lower() for result in results)
        assert any("programming" in result.text.lower() for result in results)

        component.set(number_of_results=3)
        results = component.search_documents()
        assert len(results) == 3

        if get_oracle_connection_params():
            drop_table_purge(component.connection, default_kwargs["table_name"])

    def test_retrieval_data_without_metadata(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the retrieval with documents that have no metadata."""
        # Create a collection with documents but no metadata
        test_data = [
            Data(data={"text": "Simple document 1"}),
            Data(data={"text": "Simple document 2"}),
        ]
        default_kwargs["ingest_data"] = test_data

        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)

        if not get_oracle_connection_params():
            vector_store = MagicMock()
            vector_store.search.return_value = [
                Document(page_content="Simple document 1"),
                Document(page_content="Simple document 2"),
            ]
            component._cached_vector_store = vector_store
        else:
            component.build_vector_store()

        # Get the collection data
        component.set(search_query="simple search")
        data_objects = component.search_documents()

        # Verify the conversion
        assert len(data_objects) == 2
        for data_obj in data_objects:
            assert isinstance(data_obj, Data)
            assert "text" in data_obj.data
            assert data_obj.data["text"] in {"Simple document 1", "Simple document 2"}

        if get_oracle_connection_params():
            drop_table_purge(component.connection, default_kwargs["table_name"])

    def test_retrieval_data_empty_collection(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the retrieval function with an empty collection."""
        # Create an empty collection
        default_kwargs["ingest_data"] = []
        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        if not get_oracle_connection_params():
            vector_store = MagicMock()
            vector_store.search.return_value = []
            component._cached_vector_store = vector_store
        else:
            component.build_vector_store()

        # Get the collection data
        component.set(search_query="search empty")
        data_objects = component.search_documents()

        # Verify the conversion
        assert len(data_objects) == 0

        if get_oracle_connection_params():
            drop_table_purge(component.connection, default_kwargs["table_name"])

    def test_build_vector_store_generates_index_defaults_and_serializes_metadata(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        default_kwargs["ingest_data"] = [
            Data(
                data={
                    "text": "Oracle vectors",
                    "model": _MetadataModel(value="nested"),
                    "items": [_MetadataModel(value="list-item"), {"inner": _MetadataModel(value="dict-item")}],
                    "coords": (1, 2),
                }
            )
        ]
        default_kwargs["index_params"] = {"": "drop-me"}

        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        supports_mutate_on_duplicate = any(
            getattr(input_, "name", None) == "mutate_on_duplicate" for input_ in component.inputs
        )
        vector_store = MagicMock()

        with (
            patch("lfx.components.oracledb.oraclevs.oracledb.connect", return_value=MagicMock()) as mock_connect,
            patch(
                "lfx.components.oracledb.oraclevs.OracleVS.from_documents",
                return_value=vector_store,
            ) as mock_from_documents,
            patch("lfx.components.oracledb.oraclevs.create_index") as mock_create_index,
            patch("lfx.components.oracledb.oraclevs.version", return_value="1.1.0", create=True),
        ):
            assert component.build_vector_store() is vector_store

        mock_connect.assert_called_once_with(**_expected_connection_params(default_kwargs))
        documents = mock_from_documents.call_args.kwargs["documents"]
        assert len(documents) == 1
        assert documents[0].metadata == {
            "model": {"value": "nested"},
            "items": [{"value": "list-item"}, {"inner": {"value": "dict-item"}}],
            "coords": [1, 2],
        }
        if supports_mutate_on_duplicate:
            assert mock_from_documents.call_args.kwargs.get("mutate_on_duplicate", False) is False
        else:
            assert "mutate_on_duplicate" not in mock_from_documents.call_args.kwargs

        index_params = mock_create_index.call_args.args[2]
        assert index_params["idx_type"] == "HNSW"
        assert index_params["idx_name"].startswith(f"{default_kwargs['table_name']}_idx_")
        assert "" not in index_params

    def test_build_vector_store_defaults_none_index_params(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        component.index_params = None
        vector_store = MagicMock()

        with (
            patch("lfx.components.oracledb.oraclevs.oracledb.connect", return_value=MagicMock()),
            patch("lfx.components.oracledb.oraclevs.OracleVS", return_value=vector_store),
            patch("lfx.components.oracledb.oraclevs.create_index") as mock_create_index,
            patch("lfx.components.oracledb.oraclevs.version", return_value="1.1.0", create=True),
        ):
            assert component.build_vector_store() is vector_store

        index_params = mock_create_index.call_args.args[2]
        assert index_params["idx_type"] == "HNSW"
        assert index_params["idx_name"].startswith(f"{default_kwargs['table_name']}_idx_")

    def test_build_vector_store_omits_mutate_on_duplicate_for_langchain_1_0(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        default_kwargs["create_index"] = False
        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = MagicMock()

        with (
            patch("lfx.components.oracledb.oraclevs.oracledb.connect", return_value=MagicMock()) as mock_connect,
            patch("lfx.components.oracledb.oraclevs.OracleVS", return_value=vector_store) as mock_oracle_vs,
            patch("lfx.components.oracledb.oraclevs.version", return_value="1.0.2", create=True),
        ):
            assert component.build_vector_store() is vector_store

        mock_connect.assert_called_once_with(**_expected_connection_params(default_kwargs))
        assert "mutate_on_duplicate" not in mock_oracle_vs.call_args.kwargs

    def test_build_vector_store_closes_opened_connection_when_construction_fails(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        default_kwargs["create_index"] = False
        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        connection = MagicMock()

        with (
            patch("lfx.components.oracledb.oraclevs.oracledb.connect", return_value=connection),
            patch("lfx.components.oracledb.oraclevs.OracleVS", side_effect=RuntimeError("construct boom")),
            patch("lfx.components.oracledb.oraclevs.version", return_value="1.1.0", create=True),
            pytest.raises(RuntimeError, match="construct boom"),
        ):
            component.build_vector_store()

        connection.close.assert_called_once_with()
        assert component.connection is None

    def test_build_vector_store_closes_opened_connection_when_index_creation_fails(
        self, component_class: type[OracleVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        component: OracleVectorStoreComponent = component_class().set(**default_kwargs)
        connection = MagicMock()
        vector_store = MagicMock()

        with (
            patch("lfx.components.oracledb.oraclevs.oracledb.connect", return_value=connection),
            patch("lfx.components.oracledb.oraclevs.OracleVS", return_value=vector_store),
            patch("lfx.components.oracledb.oraclevs.create_index", side_effect=RuntimeError("index boom")),
            patch("lfx.components.oracledb.oraclevs.version", return_value="1.1.0", create=True),
            pytest.raises(RuntimeError, match="index boom"),
        ):
            component.build_vector_store()

        connection.close.assert_called_once_with()
        assert component.connection is None

    def test_search_documents_normalizes_decimal_metadata(
        self, component_class: type[OracleVectorStoreComponent]
    ) -> None:
        component: OracleVectorStoreComponent = component_class().set(
            search_type="Similarity",
            search_query="oracle vectors",
            number_of_results=1,
        )
        vector_store = MagicMock()
        vector_store.search.return_value = [
            Document(
                page_content="Oracle vector search result",
                metadata={
                    "score": Decimal("1.5"),
                    "nested": {"count": Decimal(2)},
                    "items": [Decimal("3.25")],
                },
            )
        ]
        component._cached_vector_store = vector_store

        results = component.search_documents()

        assert len(results) == 1
        assert results[0].data["score"] == 1.5
        assert results[0].data["nested"]["count"] == 2.0
        assert results[0].data["items"] == [3.25]

    def test_search_documents_clears_status_for_empty_query(
        self, component_class: type[OracleVectorStoreComponent]
    ) -> None:
        component: OracleVectorStoreComponent = component_class().set(
            search_type="Similarity",
            search_query="",
            number_of_results=1,
        )
        component.status = [Data(text="stale")]
        component.build_vector_store = MagicMock()

        assert component.search_documents() == []
        assert component.status == []
        component.build_vector_store.assert_not_called()
