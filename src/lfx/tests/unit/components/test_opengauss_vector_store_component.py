"""Unit tests for the openGauss vector store component.

These tests run in isolation without langflow installed.
"""

from unittest.mock import MagicMock, patch

import pytest


class FakeEmbeddings:
    """Fake embeddings for unit tests without external dependencies."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]

    def embed_query(self, _text: str) -> list[float]:
        return [0.1] * 1536


class TestOpenGaussVectorStoreComponent:
    """Tests for the openGauss component and vector store."""

    @pytest.fixture
    def component_class(self):
        from lfx.components.opengauss.opengauss import OpenGaussVectorStoreComponent

        return OpenGaussVectorStoreComponent

    def test_init(self, component_class) -> None:
        component = component_class()
        assert component.display_name == "openGauss"
        assert component.name == "opengauss"
        assert component.icon == "openGauss"

    def test_inputs_defined(self, component_class) -> None:
        component = component_class()
        input_names = [i.name for i in component.inputs]
        assert "connection_string" in input_names
        assert "table_name" in input_names
        assert "embedding" in input_names
        assert "create_index" in input_names
        assert "index_type" in input_names
        assert "distance_strategy" in input_names

    def test_connection_string_parsing(self, component_class) -> None:
        component = component_class().set(
            connection_string="postgresql://user:pass@host:1234/mydb",
            table_name="public.test",
        )
        kwargs = component._build_kwargs()
        assert kwargs["host"] == "host"
        assert kwargs["port"] == 1234
        assert kwargs["user"] == "user"
        assert kwargs["password"] == "pass"  # noqa: S105
        assert kwargs["database"] == "mydb"

    def test_connection_string_defaults(self, component_class) -> None:
        component = component_class().set(
            connection_string="postgresql://localhost/postgres",
            table_name="public.test",
        )
        kwargs = component._build_kwargs()
        assert kwargs["host"] == "localhost"
        assert kwargs["port"] == 5432
        assert kwargs["user"] == "gaussdb"
        assert kwargs["password"] == ""
        assert kwargs["database"] == "postgres"

    def test_extract_text_common_keys(self, component_class) -> None:
        from lfx.schema.data import Data

        assert component_class._extract_text(Data(data={"text": "hello"})) == "hello"
        assert component_class._extract_text(Data(data={"content": "world"})) == "world"

    def test_extract_text_empty(self, component_class) -> None:
        from lfx.schema.data import Data

        assert component_class._extract_text(Data(data={"other": "value"})) == ""

    def test_safe_json_dumps(self) -> None:
        from lfx.components.opengauss.opengauss import _safe_json_dumps

        assert _safe_json_dumps({"a": "b"}) == '{"a": "b"}'
        result = _safe_json_dumps({"a": object()})
        assert "a" in result

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_index_type_validation(self, mock_pool: MagicMock) -> None:
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        with pytest.raises(ValueError, match="Unsupported index type"):
            OpenGaussVectorStore(embedding=FakeEmbeddings(), index_type="INVALID")

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_distance_strategy_validation(self, mock_pool: MagicMock) -> None:
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        with pytest.raises(ValueError, match="Unsupported distance strategy"):
            OpenGaussVectorStore(embedding=FakeEmbeddings(), distance_strategy="INVALID")

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_table_ident_schema(self, mock_pool: MagicMock) -> None:
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        vs = OpenGaussVectorStore(embedding=FakeEmbeddings(), table_name="public.langflow")
        ident_str = str(vs._table_ident)
        assert "public" in ident_str
        assert "langflow" in ident_str

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_table_ident_no_schema(self, mock_pool: MagicMock) -> None:
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        vs = OpenGaussVectorStore(embedding=FakeEmbeddings(), table_name="langflow")
        assert "langflow" in str(vs._table_ident)

    @patch("psycopg2.extras.execute_values")
    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_add_texts_batching(self, mock_pool: MagicMock, mock_exec: MagicMock) -> None:
        import psycopg2.sql
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.connection = mock_conn
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        vs = OpenGaussVectorStore.__new__(OpenGaussVectorStore)
        vs.embedding_function = FakeEmbeddings()
        vs._table_ident = psycopg2.sql.Identifier("test")
        vs._table_name = "test"
        vs._pool = mock_pool()

        texts = [f"text {i}" for i in range(30)]
        ids = vs.add_texts(texts)
        assert len(ids) == 30
        assert mock_exec.call_count == 2

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_build_vector_store_without_data(self, mock_pool: MagicMock) -> None:
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore, OpenGaussVectorStoreComponent

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        with patch.object(OpenGaussVectorStore, "_create_table"):
            component = OpenGaussVectorStoreComponent().set(
                connection_string="postgresql://localhost/postgres",
                table_name="public.test",
                embedding=FakeEmbeddings(),
            )
            vs = component.build_vector_store()
            assert vs is not None

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_search_documents(self, mock_pool: MagicMock) -> None:
        from langchain_core.documents import Document
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore, OpenGaussVectorStoreComponent

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        with (
            patch.object(OpenGaussVectorStore, "_create_table"),
            patch.object(OpenGaussVectorStore, "similarity_search") as mock_search,
        ):
            mock_search.return_value = [
                Document(page_content="result", metadata={}, id="1"),
            ]
            component = OpenGaussVectorStoreComponent().set(
                connection_string="postgresql://localhost/postgres",
                table_name="public.test",
                embedding=FakeEmbeddings(),
                search_query="test query",
                number_of_results=3,
            )
            results = component.search_documents()
            assert len(results) == 1
            assert results[0].text == "result"

    @patch("psycopg2.pool.SimpleConnectionPool")
    def test_search_documents_empty_query(self, mock_pool: MagicMock) -> None:
        from lfx.components.opengauss.opengauss import OpenGaussVectorStore, OpenGaussVectorStoreComponent

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn
        mock_cursor.fetchone.return_value = [True]

        with patch.object(OpenGaussVectorStore, "_create_table"):
            component = OpenGaussVectorStoreComponent().set(
                connection_string="postgresql://localhost/postgres",
                table_name="public.test",
                embedding=FakeEmbeddings(),
                search_query="",
            )
            results = component.search_documents()
            assert results == []
