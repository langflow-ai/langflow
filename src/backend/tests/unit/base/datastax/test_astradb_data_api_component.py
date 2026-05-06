"""Unit tests for :class:`AstraDBDataAPIComponent`.

These tests exercise every operation dispatch path and the astrapy-backed
collection-creation override without reaching out to Astra DB; ``astrapy``
entry points are mocked.
"""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import Mock, patch

import pytest
from lfx.components.datastax.astradb_data_api import (
    ALL_OPERATIONS,
    DEFAULT_COUNT_UPPER_BOUND,
    OP_COUNT,
    OP_DELETE_MANY,
    OP_DELETE_ONE,
    OP_ESTIMATED_COUNT,
    OP_FIND,
    OP_FIND_ONE,
    OP_INSERT_MANY,
    OP_INSERT_ONE,
    OP_UPDATE_MANY,
    OP_UPDATE_ONE,
    OPERATION_FIELDS,
    OPERATION_ICONS,
    AstraDBDataAPIComponent,
    _coerce_documents,
    _stringify,
)
from lfx.schema.data import Data

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def component() -> AstraDBDataAPIComponent:
    """Minimal component with required selector attrs pre-populated."""
    comp = AstraDBDataAPIComponent()
    comp.token = "test_token"  # noqa: S105
    comp.environment = "prod"
    comp.database_name = "test_db"
    comp.api_endpoint = "https://abcd1234-1234-1234-1234-1234567890ab.apps.astra.datastax.com"
    comp.keyspace = "default_keyspace"
    comp.collection_name = "test_coll"
    comp.operation = OP_FIND
    # Every operation-specific field starts unset.
    comp.filter_query = {}
    comp.projection = {}
    comp.sort = {}
    comp.limit = 0
    comp.skip = 0
    comp.include_similarity = False
    comp.document = {}
    comp.documents = []
    comp.ordered = False
    comp.update = {}
    comp.upsert = False
    comp.upper_bound = DEFAULT_COUNT_UPPER_BOUND
    comp.log = Mock()
    return comp


@pytest.fixture
def mock_collection() -> Mock:
    """A mocked astrapy.Collection with the operations we need."""
    return Mock()


@pytest.fixture
def component_with_collection(component, mock_collection):
    """Component where ``_get_collection`` is patched to return ``mock_collection``."""
    component._get_collection = Mock(return_value=mock_collection)  # type: ignore[method-assign]
    return component


# ----------------------------------------------------------------------
# Static / configuration tests
# ----------------------------------------------------------------------


class TestStaticConfiguration:
    """Tests that don't require a component instance."""

    def test_all_operations_have_icons(self):
        """Every dropdown option has an associated icon."""
        assert set(OPERATION_ICONS.keys()) == set(ALL_OPERATIONS)

    def test_all_operations_have_fields(self):
        """Every dropdown option has a field-set definition (possibly empty)."""
        assert set(OPERATION_FIELDS.keys()) == set(ALL_OPERATIONS)

    def test_operation_field_names_exist_on_inputs(self):
        """Every field referenced in OPERATION_FIELDS is an actual declared input."""
        input_names = {inp.name for inp in AstraDBDataAPIComponent.inputs}
        for op, fields in OPERATION_FIELDS.items():
            for field in fields:
                assert field in input_names, f"Operation '{op}' references unknown input field '{field}'"

    def test_component_metadata(self):
        """Component metadata is sensible."""
        assert AstraDBDataAPIComponent.display_name == "Astra DB Data API"
        assert AstraDBDataAPIComponent.name == "AstraDBDataAPI"
        assert AstraDBDataAPIComponent.icon == "AstraDB"
        assert AstraDBDataAPIComponent.beta is True

    def test_outputs_defined(self):
        """The three documented output sockets are present."""
        names = {o.name for o in AstraDBDataAPIComponent.outputs}
        assert names == {"data", "dataframe", "raw"}

    def test_tool_mode_inputs(self):
        """Key agent-controllable inputs expose ``tool_mode=True``."""
        tool_mode_names = {inp.name for inp in AstraDBDataAPIComponent.inputs if getattr(inp, "tool_mode", False)}
        expected = {"operation", "filter_query", "limit", "document", "documents", "update"}
        assert expected.issubset(tool_mode_names), (
            f"Missing tool_mode on agent-controllable inputs: {expected - tool_mode_names}"
        )
        # Secrets and selector fields should never be marked as tool-controllable.
        forbidden = {"token", "api_endpoint", "database_name", "collection_name", "keyspace"}
        assert forbidden.isdisjoint(tool_mode_names), (
            f"Sensitive/selector fields must not be tool_mode: {forbidden & tool_mode_names}"
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class TestStringify:
    def test_primitives_pass_through(self):
        assert _stringify("abc") == "abc"
        assert _stringify(1) == 1
        assert _stringify(1.5) == 1.5
        assert _stringify(True) is True  # noqa: FBT003

    def test_none_returns_none(self):
        assert _stringify(None) is None

    def test_objects_stringified(self):
        class Id:
            def __str__(self):
                return "object-id"

        assert _stringify(Id()) == "object-id"


class TestCoerceDocuments:
    def test_empty_value(self):
        assert _coerce_documents(None) == []
        assert _coerce_documents("") == []

    def test_single_dict_wrapped(self):
        result = _coerce_documents({"a": 1})
        assert result == [{"a": 1}]

    def test_list_passes_through(self):
        docs = [{"a": 1}, {"b": 2}]
        assert _coerce_documents(docs) == docs

    def test_rejects_non_dict_entries(self):
        with pytest.raises(ValueError, match="non-dict entries"):
            _coerce_documents([{"a": 1}, "not-a-dict"])

    def test_rejects_wrong_type(self):
        with pytest.raises(ValueError, match="Documents must be a list"):
            _coerce_documents(42)


# ----------------------------------------------------------------------
# UI: operation visibility toggling
# ----------------------------------------------------------------------


class TestOperationVisibility:
    def _make_build_config(self) -> dict:
        """Build a config dict containing every toggle-able field."""
        fields = set().union(*OPERATION_FIELDS.values())
        return {field: {"show": True} for field in fields}

    def test_find_shows_query_fields(self):
        config = self._make_build_config()
        AstraDBDataAPIComponent._apply_operation_visibility(config, OP_FIND)
        assert config["filter_query"]["show"] is True
        assert config["limit"]["show"] is True
        assert config["document"]["show"] is False
        assert config["update"]["show"] is False

    def test_insert_one_shows_document(self):
        config = self._make_build_config()
        AstraDBDataAPIComponent._apply_operation_visibility(config, OP_INSERT_ONE)
        assert config["document"]["show"] is True
        assert config["documents"]["show"] is False
        assert config["filter_query"]["show"] is False

    def test_insert_many_shows_documents_and_ordered(self):
        config = self._make_build_config()
        AstraDBDataAPIComponent._apply_operation_visibility(config, OP_INSERT_MANY)
        assert config["documents"]["show"] is True
        assert config["ordered"]["show"] is True
        assert config["document"]["show"] is False

    def test_update_ops_show_filter_update_upsert(self):
        for op in (OP_UPDATE_ONE, OP_UPDATE_MANY):
            config = self._make_build_config()
            AstraDBDataAPIComponent._apply_operation_visibility(config, op)
            assert config["filter_query"]["show"] is True
            assert config["update"]["show"] is True
            assert config["upsert"]["show"] is True
            assert config["document"]["show"] is False

    def test_count_shows_upper_bound(self):
        config = self._make_build_config()
        AstraDBDataAPIComponent._apply_operation_visibility(config, OP_COUNT)
        assert config["filter_query"]["show"] is True
        assert config["upper_bound"]["show"] is True

    def test_estimated_count_hides_everything(self):
        config = self._make_build_config()
        AstraDBDataAPIComponent._apply_operation_visibility(config, OP_ESTIMATED_COUNT)
        for key, value in config.items():
            assert value["show"] is False, f"Field '{key}' should be hidden for Estimated Count"


# ----------------------------------------------------------------------
# Operation dispatch
# ----------------------------------------------------------------------


class TestFindOperation:
    def test_find_returns_list_of_data(self, component_with_collection, mock_collection):
        mock_collection.find.return_value = iter([{"_id": "1", "name": "Ada"}, {"_id": "2", "name": "Grace"}])
        component_with_collection.operation = OP_FIND
        component_with_collection.filter_query = {"active": True}
        component_with_collection.limit = 10

        result = component_with_collection.run_operation()

        mock_collection.find.assert_called_once()
        call_kwargs = mock_collection.find.call_args.kwargs
        assert call_kwargs["filter"] == {"active": True}
        assert call_kwargs["limit"] == 10

        assert len(result) == 2
        assert all(isinstance(d, Data) for d in result)
        assert result[0].data == {"_id": "1", "name": "Ada"}

    def test_find_omits_empty_options(self, component_with_collection, mock_collection):
        mock_collection.find.return_value = iter([])
        component_with_collection.operation = OP_FIND

        component_with_collection.run_operation()

        kwargs = mock_collection.find.call_args.kwargs
        assert "projection" not in kwargs
        assert "sort" not in kwargs
        assert "limit" not in kwargs
        assert "skip" not in kwargs
        assert "include_similarity" not in kwargs

    def test_find_respects_skip_projection_sort(self, component_with_collection, mock_collection):
        mock_collection.find.return_value = iter([])
        component_with_collection.operation = OP_FIND
        component_with_collection.projection = {"name": 1}
        component_with_collection.sort = {"$vectorize": "hello"}
        component_with_collection.skip = 5
        component_with_collection.limit = 20
        component_with_collection.include_similarity = True

        component_with_collection.run_operation()

        kwargs = mock_collection.find.call_args.kwargs
        assert kwargs["projection"] == {"name": 1}
        assert kwargs["sort"] == {"$vectorize": "hello"}
        assert kwargs["skip"] == 5
        assert kwargs["limit"] == 20
        assert kwargs["include_similarity"] is True

    def test_find_raw_result(self, component_with_collection, mock_collection):
        mock_collection.find.return_value = iter([{"a": 1}, {"a": 2}])
        component_with_collection.operation = OP_FIND

        raw = component_with_collection.raw_result()

        assert isinstance(raw, Data)
        assert raw.data["count"] == 2
        assert raw.data["documents"] == [{"a": 1}, {"a": 2}]


class TestFindOneOperation:
    def test_find_one_with_match(self, component_with_collection, mock_collection):
        mock_collection.find_one.return_value = {"_id": "1", "name": "Ada"}
        component_with_collection.operation = OP_FIND_ONE
        component_with_collection.filter_query = {"_id": "1"}

        result = component_with_collection.run_operation()

        mock_collection.find_one.assert_called_once()
        kwargs = mock_collection.find_one.call_args.kwargs
        assert kwargs["filter"] == {"_id": "1"}
        # ``limit`` / ``skip`` are not valid for find_one -- make sure we don't leak them.
        assert "limit" not in kwargs
        assert "skip" not in kwargs
        assert len(result) == 1
        assert result[0].data == {"_id": "1", "name": "Ada"}

    def test_find_one_no_match_returns_empty(self, component_with_collection, mock_collection):
        mock_collection.find_one.return_value = None
        component_with_collection.operation = OP_FIND_ONE
        component_with_collection.filter_query = {"_id": "missing"}

        assert component_with_collection.run_operation() == []


class TestInsertOneOperation:
    def test_insert_one_success(self, component_with_collection, mock_collection):
        mock_result = Mock()
        mock_result.inserted_id = "inserted-id-123"
        mock_collection.insert_one.return_value = mock_result

        component_with_collection.operation = OP_INSERT_ONE
        component_with_collection.document = {"name": "Ada"}

        result = component_with_collection.run_operation()

        mock_collection.insert_one.assert_called_once_with({"name": "Ada"})
        assert len(result) == 1
        assert result[0].data == {"inserted_id": "inserted-id-123"}

    def test_insert_one_rejects_non_dict(self, component_with_collection):
        component_with_collection.operation = OP_INSERT_ONE
        component_with_collection.document = "not-a-dict"

        with pytest.raises(ValueError, match="Astra DB Data API 'Insert One' failed"):
            component_with_collection.run_operation()


class TestInsertManyOperation:
    def test_insert_many_success(self, component_with_collection, mock_collection):
        mock_result = Mock()
        mock_result.inserted_ids = ["id-1", "id-2", "id-3"]
        mock_collection.insert_many.return_value = mock_result

        component_with_collection.operation = OP_INSERT_MANY
        component_with_collection.documents = [{"a": 1}, {"a": 2}, {"a": 3}]
        component_with_collection.ordered = True

        result = component_with_collection.run_operation()

        mock_collection.insert_many.assert_called_once_with([{"a": 1}, {"a": 2}, {"a": 3}], ordered=True)
        assert result[0].data == {
            "inserted_ids": ["id-1", "id-2", "id-3"],
            "inserted_count": 3,
        }

    def test_insert_many_empty_rejected(self, component_with_collection):
        component_with_collection.operation = OP_INSERT_MANY
        component_with_collection.documents = []

        with pytest.raises(ValueError, match="non-empty list"):
            component_with_collection.run_operation()


class TestUpdateOperations:
    def test_update_one_requires_filter(self, component_with_collection):
        component_with_collection.operation = OP_UPDATE_ONE
        component_with_collection.filter_query = {}
        component_with_collection.update = {"$set": {"status": "x"}}

        with pytest.raises(ValueError, match="filter_query"):
            component_with_collection.run_operation()

    def test_update_one_requires_update_doc(self, component_with_collection):
        component_with_collection.operation = OP_UPDATE_ONE
        component_with_collection.filter_query = {"_id": "1"}
        component_with_collection.update = {}

        with pytest.raises(ValueError, match="update"):
            component_with_collection.run_operation()

    def test_update_one_success(self, component_with_collection, mock_collection):
        mock_result = Mock()
        mock_result.matched_count = 1
        mock_result.modified_count = 1
        mock_result.upserted_id = None
        mock_collection.update_one.return_value = mock_result

        component_with_collection.operation = OP_UPDATE_ONE
        component_with_collection.filter_query = {"_id": "1"}
        component_with_collection.update = {"$set": {"status": "active"}}
        component_with_collection.upsert = True

        result = component_with_collection.run_operation()

        mock_collection.update_one.assert_called_once_with({"_id": "1"}, {"$set": {"status": "active"}}, upsert=True)
        assert result[0].data["matched_count"] == 1
        assert result[0].data["modified_count"] == 1
        assert result[0].data["upserted_id"] is None

    def test_update_many_success(self, component_with_collection, mock_collection):
        mock_result = Mock()
        mock_result.matched_count = 5
        mock_result.modified_count = 5
        mock_result.upserted_id = None
        mock_collection.update_many.return_value = mock_result

        component_with_collection.operation = OP_UPDATE_MANY
        component_with_collection.filter_query = {"active": True}
        component_with_collection.update = {"$inc": {"version": 1}}

        result = component_with_collection.run_operation()

        mock_collection.update_many.assert_called_once_with({"active": True}, {"$inc": {"version": 1}}, upsert=False)
        assert result[0].data["modified_count"] == 5


class TestDeleteOperations:
    def test_delete_one(self, component_with_collection, mock_collection):
        mock_result = Mock()
        mock_result.deleted_count = 1
        mock_collection.delete_one.return_value = mock_result

        component_with_collection.operation = OP_DELETE_ONE
        component_with_collection.filter_query = {"_id": "1"}

        result = component_with_collection.run_operation()

        mock_collection.delete_one.assert_called_once_with({"_id": "1"})
        assert result[0].data == {"deleted_count": 1}

    def test_delete_many(self, component_with_collection, mock_collection):
        mock_result = Mock()
        mock_result.deleted_count = 42
        mock_collection.delete_many.return_value = mock_result

        component_with_collection.operation = OP_DELETE_MANY
        component_with_collection.filter_query = {"archived": True}

        result = component_with_collection.run_operation()

        mock_collection.delete_many.assert_called_once_with({"archived": True})
        assert result[0].data == {"deleted_count": 42}

    def test_delete_requires_filter(self, component_with_collection):
        component_with_collection.operation = OP_DELETE_ONE
        component_with_collection.filter_query = {}

        with pytest.raises(ValueError, match="filter_query"):
            component_with_collection.run_operation()


class TestCountOperations:
    def test_count_documents(self, component_with_collection, mock_collection):
        mock_collection.count_documents.return_value = 17

        component_with_collection.operation = OP_COUNT
        component_with_collection.filter_query = {"active": True}
        component_with_collection.upper_bound = 500

        result = component_with_collection.run_operation()

        mock_collection.count_documents.assert_called_once_with({"active": True}, upper_bound=500)
        assert result[0].data == {"count": 17, "upper_bound": 500}

    def test_estimated_count(self, component_with_collection, mock_collection):
        mock_collection.estimated_document_count.return_value = 1_000_000

        component_with_collection.operation = OP_ESTIMATED_COUNT

        result = component_with_collection.run_operation()

        mock_collection.estimated_document_count.assert_called_once_with()
        assert result[0].data == {"estimated_count": 1_000_000}


# ----------------------------------------------------------------------
# DataFrame output
# ----------------------------------------------------------------------


class TestDataFrameOutput:
    def test_as_dataframe_from_find(self, component_with_collection, mock_collection):
        mock_collection.find.return_value = iter(
            [
                {"name": "Ada", "age": 36},
                {"name": "Grace", "age": 85},
            ]
        )
        component_with_collection.operation = OP_FIND

        df = component_with_collection.as_dataframe()

        assert len(df) == 2
        assert set(df.columns) >= {"name", "age"}

    def test_as_dataframe_empty(self, component_with_collection, mock_collection):
        mock_collection.find.return_value = iter([])
        component_with_collection.operation = OP_FIND

        df = component_with_collection.as_dataframe()

        assert len(df) == 0


# ----------------------------------------------------------------------
# Error propagation
# ----------------------------------------------------------------------


class TestErrorPropagation:
    def test_unknown_operation_raises(self, component_with_collection):
        component_with_collection.operation = "Destroy The Universe"

        with pytest.raises(ValueError, match="Unsupported operation"):
            component_with_collection.run_operation()

    def test_astrapy_errors_wrapped(self, component_with_collection, mock_collection):
        mock_collection.find.side_effect = RuntimeError("boom")
        component_with_collection.operation = OP_FIND

        with pytest.raises(ValueError, match="Astra DB Data API 'Find' failed: boom"):
            component_with_collection.run_operation()

    def test_missing_collection_name_raises(self, component):
        component.collection_name = ""
        # Bypass the patched _get_collection to exercise the real path.
        with pytest.raises(ValueError, match="No collection selected"):
            component._get_collection()


# ----------------------------------------------------------------------
# update_build_config
# ----------------------------------------------------------------------


class TestUpdateBuildConfig:
    @pytest.mark.asyncio
    async def test_operation_change_toggles_fields(self, component):
        # Simulate the base behavior: reset_build_config if no token, so provide one.
        build_config = {
            "token": {"value": "tok"},
            "environment": {"value": "prod"},
            "database_name": {"value": "", "options": [], "options_metadata": [], "show": False},
            "api_endpoint": {"value": "", "options": []},
            "keyspace": {"value": "", "options": []},
            "collection_name": {"value": "", "options": [], "options_metadata": [], "show": False},
            "autodetect_collection": {"value": True},
            "operation": {"value": OP_FIND},
            # Fields managed by _apply_operation_visibility
            "filter_query": {"show": True},
            "projection": {"show": True},
            "sort": {"show": True},
            "limit": {"show": True},
            "skip": {"show": True},
            "include_similarity": {"show": True},
            "document": {"show": True},
            "documents": {"show": True},
            "ordered": {"show": True},
            "update": {"show": True},
            "upsert": {"show": True},
            "upper_bound": {"show": True},
        }

        # Switching to Insert One should hide find-style fields.
        with (
            patch.object(
                AstraDBDataAPIComponent,
                "get_database_list_static",
                return_value={},
            ),
            patch.object(
                AstraDBDataAPIComponent,
                "map_cloud_providers",
                return_value={},
            ),
        ):
            # Swap to a non-managed field so we don't trigger the full base reset,
            # then directly invoke the visibility helper via the operation branch.
            result = await component.update_build_config(build_config, OP_INSERT_ONE, "operation")

        assert result["document"]["show"] is True
        assert result["filter_query"]["show"] is False
        assert result["documents"]["show"] is False


# ----------------------------------------------------------------------
# astrapy-backed collection creation
# ----------------------------------------------------------------------


class TestCreateCollectionAstrapyOnly:
    """The override must not touch ``langchain-astradb``."""

    @pytest.mark.asyncio
    @patch("lfx.components.datastax.astradb_data_api.DataAPIClient")
    async def test_bring_your_own_dimension(self, mock_client_cls):
        mock_db = Mock()
        mock_client_cls.return_value.get_database.return_value = mock_db

        await AstraDBDataAPIComponent.create_collection_api(
            new_collection_name="c1",
            token="t",  # noqa: S106
            api_endpoint="https://x.apps.astra.datastax.com",
            keyspace="ks",
            dimension=1536,
        )

        mock_db.create_collection.assert_called_once()
        args, kwargs = mock_db.create_collection.call_args
        assert args[0] == "c1"
        assert kwargs["keyspace"] == "ks"
        definition = kwargs["definition"]
        assert definition is not None
        assert definition.vector is not None
        assert definition.vector.dimension == 1536
        # Vectorize service must NOT be set when dimension-only.
        assert definition.vector.service is None

    @pytest.mark.asyncio
    @patch("lfx.components.datastax.astradb_data_api.DataAPIClient")
    @patch.object(AstraDBDataAPIComponent, "get_vectorize_providers")
    async def test_vectorize_provider(self, mock_providers, mock_client_cls):
        mock_db = Mock()
        mock_client_cls.return_value.get_database.return_value = mock_db
        mock_providers.return_value = defaultdict(
            list,
            {"NVIDIA": ["nvidia", ["nv-embed-qa"]]},
        )

        await AstraDBDataAPIComponent.create_collection_api(
            new_collection_name="c2",
            token="t",  # noqa: S106
            api_endpoint="https://x.apps.astra.datastax.com",
            keyspace="ks",
            embedding_generation_provider="NVIDIA",
            embedding_generation_model="nv-embed-qa",
        )

        kwargs = mock_db.create_collection.call_args.kwargs
        definition = kwargs["definition"]
        assert definition.vector.service is not None
        assert definition.vector.service.provider == "nvidia"
        assert definition.vector.service.model_name == "nv-embed-qa"

    @pytest.mark.asyncio
    @patch("lfx.components.datastax.astradb_data_api.DataAPIClient")
    async def test_plain_collection_no_vector(self, mock_client_cls):
        """No dimension and no vectorize provider --> plain collection, no definition."""
        mock_db = Mock()
        mock_client_cls.return_value.get_database.return_value = mock_db

        await AstraDBDataAPIComponent.create_collection_api(
            new_collection_name="plain",
            token="t",  # noqa: S106
            api_endpoint="https://x.apps.astra.datastax.com",
            keyspace="ks",
            embedding_generation_provider="Bring your own",
        )

        kwargs = mock_db.create_collection.call_args.kwargs
        assert kwargs["definition"] is None

    @pytest.mark.asyncio
    async def test_missing_name_rejected(self):
        with pytest.raises(ValueError, match="Collection name is required"):
            await AstraDBDataAPIComponent.create_collection_api(
                new_collection_name="",
                token="t",  # noqa: S106
                api_endpoint="https://x.apps.astra.datastax.com",
            )

    @pytest.mark.asyncio
    @patch("lfx.components.datastax.astradb_data_api.DataAPIClient")
    @patch.object(AstraDBDataAPIComponent, "get_vectorize_providers")
    async def test_unknown_provider_rejected(self, mock_providers, mock_client_cls):
        mock_client_cls.return_value.get_database.return_value = Mock()
        mock_providers.return_value = defaultdict(list)

        with pytest.raises(ValueError, match="Unknown embedding provider"):
            await AstraDBDataAPIComponent.create_collection_api(
                new_collection_name="c3",
                token="t",  # noqa: S106
                api_endpoint="https://x.apps.astra.datastax.com",
                embedding_generation_provider="NotAProvider",
                embedding_generation_model="m",
            )

    @pytest.mark.asyncio
    @patch("lfx.components.datastax.astradb_data_api.DataAPIClient")
    async def test_no_langchain_astradb_import(self, mock_client_cls, monkeypatch):
        """The override must not import ``langchain_astradb``.

        We simulate that module being unavailable; the call must still succeed.
        """
        import sys

        monkeypatch.setitem(sys.modules, "langchain_astradb", None)

        mock_db = Mock()
        mock_client_cls.return_value.get_database.return_value = mock_db

        await AstraDBDataAPIComponent.create_collection_api(
            new_collection_name="no-lc",
            token="t",  # noqa: S106
            api_endpoint="https://x.apps.astra.datastax.com",
            dimension=512,
        )

        mock_db.create_collection.assert_called_once()
