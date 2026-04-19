"""Astra DB Data API component.

A thin, modern Langflow component that exposes the full document-based
Data API surface of DataStax Astra DB using **only** the ``astrapy`` SDK.

The component inherits :class:`lfx.base.datastax.astradb_base.AstraDBBaseComponent`
to reuse the polished database / collection / keyspace selector UI (including
the in-app "Create new database" and "Create new collection" dialogs).
Unlike :class:`AstraDBVectorStoreComponent`, no ``langchain-astradb`` code path
is used at runtime --- every operation goes through ``astrapy`` directly.

Supported operations (selectable via the operation tab):

* Find             --- ``collection.find``
* Find One         --- ``collection.find_one``
* Insert One       --- ``collection.insert_one``
* Insert Many      --- ``collection.insert_many``
* Update One       --- ``collection.update_one``
* Update Many      --- ``collection.update_many``
* Delete One       --- ``collection.delete_one``
* Delete Many      --- ``collection.delete_many``
* Count Documents  --- ``collection.count_documents``
* Estimated Count  --- ``collection.estimated_document_count``
"""

from __future__ import annotations

from typing import Any

from astrapy import Collection, DataAPIClient, Database
from astrapy.info import (
    CollectionDefinition,
    CollectionVectorOptions,
    VectorServiceOptions,
)

from lfx.base.datastax.astradb_base import AstraDBBaseComponent
from lfx.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    NestedDictInput,
    Output,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

# Operation option constants -- kept as module-level constants so the UI
# tab values and the dispatcher stay in sync with a single source of truth.
OP_FIND = "Find"
OP_FIND_ONE = "Find One"
OP_INSERT_ONE = "Insert One"
OP_INSERT_MANY = "Insert Many"
OP_UPDATE_ONE = "Update One"
OP_UPDATE_MANY = "Update Many"
OP_DELETE_ONE = "Delete One"
OP_DELETE_MANY = "Delete Many"
OP_COUNT = "Count Documents"
OP_ESTIMATED_COUNT = "Estimated Count"

ALL_OPERATIONS: tuple[str, ...] = (
    OP_FIND,
    OP_FIND_ONE,
    OP_INSERT_ONE,
    OP_INSERT_MANY,
    OP_UPDATE_ONE,
    OP_UPDATE_MANY,
    OP_DELETE_ONE,
    OP_DELETE_MANY,
    OP_COUNT,
    OP_ESTIMATED_COUNT,
)

# Per-operation icons surfaced in the operation dropdown. Icon names mirror
# those used elsewhere in Langflow for a consistent look.
OPERATION_ICONS: dict[str, str] = {
    OP_FIND: "Search",
    OP_FIND_ONE: "SearchCheck",
    OP_INSERT_ONE: "Plus",
    OP_INSERT_MANY: "CopyPlus",
    OP_UPDATE_ONE: "Pencil",
    OP_UPDATE_MANY: "PencilLine",
    OP_DELETE_ONE: "Trash",
    OP_DELETE_MANY: "Trash2",
    OP_COUNT: "Hash",
    OP_ESTIMATED_COUNT: "Sigma",
}

# Groups of inputs that each operation needs. Centralising this makes the
# dynamic show/hide logic trivial to audit and extend.
OPERATION_FIELDS: dict[str, set[str]] = {
    OP_FIND: {"filter_query", "projection", "sort", "limit", "skip", "include_similarity"},
    OP_FIND_ONE: {"filter_query", "projection", "sort", "include_similarity"},
    OP_INSERT_ONE: {"document"},
    OP_INSERT_MANY: {"documents", "ordered"},
    OP_UPDATE_ONE: {"filter_query", "update", "upsert"},
    OP_UPDATE_MANY: {"filter_query", "update", "upsert"},
    OP_DELETE_ONE: {"filter_query"},
    OP_DELETE_MANY: {"filter_query"},
    OP_COUNT: {"filter_query", "upper_bound"},
    OP_ESTIMATED_COUNT: set(),
}

# Default count upper bound (``count_documents`` in astrapy requires one).
DEFAULT_COUNT_UPPER_BOUND = 1000
# Default find limit -- guard against unbounded scans in the UI path.
DEFAULT_FIND_LIMIT = 100

# Fields specific to the operation that we toggle ``show`` on.
_OPERATION_TOGGLE_FIELDS: tuple[str, ...] = (
    "filter_query",
    "projection",
    "sort",
    "limit",
    "skip",
    "include_similarity",
    "document",
    "documents",
    "update",
    "upsert",
    "ordered",
    "upper_bound",
)


class AstraDBDataAPIComponent(AstraDBBaseComponent):
    """Direct ``astrapy`` Data API access for Astra DB collections.

    Inherits the standard Astra DB selector UI (database / keyspace /
    collection, plus the create-new dialogs) from
    :class:`AstraDBBaseComponent` and adds a single operation tab that
    drives a minimal, operation-specific set of inputs.
    """

    display_name: str = "Astra DB Data API"
    description: str = (
        "Run Data API operations (find, filter, insert, update, delete, "
        "count) against an Astra DB collection using astrapy directly."
    )
    documentation: str = "https://docs.datastax.com/en/astra-db-serverless/api-reference/overview.html"
    icon: str = "AstraDB"
    name: str = "AstraDBDataAPI"
    beta: bool = True

    inputs = [
        *AstraDBBaseComponent.inputs,
        DropdownInput(
            name="operation",
            display_name="Operation",
            info="Data API operation to run against the selected collection.",
            options=list(ALL_OPERATIONS),
            options_metadata=[{"icon": OPERATION_ICONS[op]} for op in ALL_OPERATIONS],
            value=OP_FIND,
            real_time_refresh=True,
            combobox=False,
            tool_mode=True,
        ),
        # -- Query / projection / sort ---------------------------------
        NestedDictInput(
            name="filter_query",
            display_name="Filter",
            info=(
                "MongoDB-style filter, e.g. "
                '{"status": "active", "age": {"$gte": 18}}. '
                "Leave empty to match all documents (not recommended for "
                "delete/update operations)."
            ),
            advanced=False,
            tool_mode=True,
        ),
        NestedDictInput(
            name="projection",
            display_name="Projection",
            info=('Fields to include (``1``/``true``) or exclude (``0``/``false``), e.g. {"name": 1, "email": 1}.'),
            advanced=True,
        ),
        NestedDictInput(
            name="sort",
            display_name="Sort",
            info=(
                "Sort specification -- ``1`` ascending, ``-1`` descending. "
                "Use ``$vector`` or ``$vectorize`` for vector search, e.g. "
                '{"$vectorize": "search query"}.'
            ),
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Maximum number of documents to return.",
            value=DEFAULT_FIND_LIMIT,
            advanced=False,
            tool_mode=True,
        ),
        IntInput(
            name="skip",
            display_name="Skip",
            info="Number of documents to skip.",
            value=0,
            advanced=True,
        ),
        BoolInput(
            name="include_similarity",
            display_name="Include Similarity",
            info="Include the ``$similarity`` score on each returned document (vector searches only).",
            value=False,
            advanced=True,
        ),
        # -- Writes -----------------------------------------------------
        NestedDictInput(
            name="document",
            display_name="Document",
            info='Single document to insert, e.g. {"name": "Ada", "age": 36}.',
            show=False,
            tool_mode=True,
        ),
        NestedDictInput(
            name="documents",
            display_name="Documents",
            info="List of documents to insert. Provide a JSON list, e.g. [{...}, {...}].",
            show=False,
            tool_mode=True,
        ),
        BoolInput(
            name="ordered",
            display_name="Ordered Insert",
            info="If enabled, inserts stop at the first error; otherwise errors are collected.",
            value=False,
            show=False,
            advanced=True,
        ),
        NestedDictInput(
            name="update",
            display_name="Update",
            info=(
                'Update operator document, e.g. {"$set": {"status": "archived"}}. '
                "Must use update operators (``$set``, ``$inc``, ``$push`` ...)."
            ),
            show=False,
            tool_mode=True,
        ),
        BoolInput(
            name="upsert",
            display_name="Upsert",
            info="Insert a new document if no match is found.",
            value=False,
            show=False,
            advanced=True,
        ),
        # -- Count ------------------------------------------------------
        IntInput(
            name="upper_bound",
            display_name="Count Upper Bound",
            info="Maximum count astrapy will scan to for ``Count Documents``.",
            value=DEFAULT_COUNT_UPPER_BOUND,
            show=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="run_operation"),
        Output(display_name="Table", name="dataframe", method="as_dataframe"),
        Output(display_name="Raw Result", name="raw", method="raw_result"),
    ]

    # ----------------------------------------------------------------------
    # Override collection creation to use astrapy *directly*.
    # ----------------------------------------------------------------------

    @classmethod
    async def create_collection_api(  # type: ignore[override]
        cls,
        new_collection_name: str,
        token: str,
        api_endpoint: str,
        environment: str | None = None,
        keyspace: str | None = None,
        dimension: int | None = None,
        embedding_generation_provider: str | None = None,
        embedding_generation_model: str | None = None,
    ) -> Collection:
        """Create a new Astra DB collection using astrapy only.

        The base class implementation in :class:`AstraDBBaseComponent` uses
        ``_AstraDBCollectionEnvironment`` from ``langchain-astradb``. This
        override instead calls ``astrapy``'s :meth:`Database.create_collection`
        directly, building a :class:`CollectionDefinition` when
        server-side vectorize options are requested.

        Args:
            new_collection_name: Required collection name.
            token: Astra DB application token.
            api_endpoint: Full Astra DB API endpoint for the target database.
            environment: Astra environment (``prod`` / ``test`` / ``dev``).
            keyspace: Keyspace to create the collection in.
            dimension: Embedding dimension if using "Bring your own" embeddings.
            embedding_generation_provider: Display name of a configured
                vectorize provider, or ``"Bring your own"``.
            embedding_generation_model: Model name for the selected provider.

        Returns:
            The newly created :class:`astrapy.Collection`.

        Raises:
            ValueError: If ``new_collection_name`` is empty or if an
                unsupported provider configuration is supplied.
        """
        if not new_collection_name:
            msg = "Collection name is required to create a new collection."
            raise ValueError(msg)

        env = cls.get_environment(environment)
        client = DataAPIClient(environment=env)
        database = client.get_database(api_endpoint, token=token, keyspace=keyspace)

        # Build the vector options -- either bring-your-own (dimension only)
        # or a server-side vectorize provider.
        vector_options: CollectionVectorOptions | None = None
        if dimension:
            vector_options = CollectionVectorOptions(dimension=dimension)
        elif embedding_generation_provider and embedding_generation_provider != "Bring your own":
            providers = cls.get_vectorize_providers(token=token, environment=env, api_endpoint=api_endpoint)
            provider_key = providers.get(embedding_generation_provider, [None, []])[0]
            if provider_key is None:
                msg = (
                    f"Unknown embedding provider '{embedding_generation_provider}'. "
                    "Pass a dimension for a bring-your-own collection, or choose a "
                    "configured vectorize provider."
                )
                raise ValueError(msg)
            vector_options = CollectionVectorOptions(
                service=VectorServiceOptions(
                    provider=provider_key,
                    model_name=embedding_generation_model,
                ),
            )

        definition = CollectionDefinition(vector=vector_options) if vector_options else None
        return database.create_collection(
            new_collection_name,
            definition=definition,
            keyspace=keyspace,
        )

    # ----------------------------------------------------------------------
    # Dynamic UI -- show/hide operation-specific fields.
    # ----------------------------------------------------------------------

    async def update_build_config(
        self,
        build_config: dict,
        field_value: str | dict,
        field_name: str | None = None,
    ) -> dict:
        """Keep the base Astra DB selector behavior and toggle operation fields."""
        build_config = await super().update_build_config(build_config, field_value, field_name)

        # On operation change (or first render), toggle visibility of
        # operation-specific inputs.
        if field_name == "operation" or field_name is None:
            op_value = field_value if field_name == "operation" else build_config.get("operation", {}).get("value")
            self._apply_operation_visibility(build_config, op_value or OP_FIND)

        return build_config

    @classmethod
    def _apply_operation_visibility(cls, build_config: dict, operation: str) -> None:
        """Show/hide operation-specific fields based on the selected operation."""
        active = OPERATION_FIELDS.get(operation, set())
        for field in _OPERATION_TOGGLE_FIELDS:
            if field in build_config:
                build_config[field]["show"] = field in active

    # ----------------------------------------------------------------------
    # Collection accessor
    # ----------------------------------------------------------------------

    def _get_collection(self) -> Collection:
        """Return the resolved astrapy :class:`Collection` for this component."""
        if not self.collection_name:
            msg = "No collection selected. Choose or create a collection first."
            raise ValueError(msg)

        database: Database = self.get_database_object(api_endpoint=self.get_api_endpoint())
        return database.get_collection(self.collection_name, keyspace=self.get_keyspace())

    # ----------------------------------------------------------------------
    # Operation dispatch
    # ----------------------------------------------------------------------

    def run_operation(self) -> list[Data]:
        """Execute the selected operation and return results as ``list[Data]``.

        For write / count operations where a ``list[Data]`` isn't semantically
        meaningful, a single-element list wrapping a summary :class:`Data`
        object is returned so the output socket stays consistent.
        """
        result = self._dispatch()
        self.status = result
        return result

    def raw_result(self) -> Data:
        """Return the raw operation result as a single :class:`Data` object.

        Useful for inspecting the full ``astrapy`` response envelope
        (``inserted_ids``, ``matched_count``, ``modified_count`` ...).
        """
        raw = self._dispatch(raw=True)
        data = Data(data=raw if isinstance(raw, dict) else {"result": raw})
        self.status = data
        return data

    def as_dataframe(self) -> DataFrame:
        """Return results as a :class:`DataFrame` for easy tabular display."""
        rows = self.run_operation()
        return DataFrame([row.data for row in rows if isinstance(row, Data)])

    # ----------------------------------------------------------------------
    # Internal dispatcher
    # ----------------------------------------------------------------------

    def _dispatch(self, *, raw: bool = False) -> Any:
        operation = getattr(self, "operation", OP_FIND) or OP_FIND
        collection = self._get_collection()

        handlers = {
            OP_FIND: self._op_find,
            OP_FIND_ONE: self._op_find_one,
            OP_INSERT_ONE: self._op_insert_one,
            OP_INSERT_MANY: self._op_insert_many,
            OP_UPDATE_ONE: self._op_update_one,
            OP_UPDATE_MANY: self._op_update_many,
            OP_DELETE_ONE: self._op_delete_one,
            OP_DELETE_MANY: self._op_delete_many,
            OP_COUNT: self._op_count,
            OP_ESTIMATED_COUNT: self._op_estimated_count,
        }

        handler = handlers.get(operation)
        if handler is None:
            msg = f"Unsupported operation '{operation}'."
            raise ValueError(msg)

        try:
            return handler(collection, raw=raw)
        except Exception as exc:
            logger.exception("Astra DB Data API operation failed: %s", operation)
            msg = f"Astra DB Data API '{operation}' failed: {exc}"
            raise ValueError(msg) from exc

    # -- Handlers -----------------------------------------------------

    def _op_find(self, collection: Collection, *, raw: bool) -> Any:
        find_kwargs = self._build_find_kwargs()
        cursor = collection.find(**find_kwargs)
        docs = list(cursor)
        if raw:
            return {"count": len(docs), "documents": docs}
        return [Data(data=doc) for doc in docs]

    def _op_find_one(self, collection: Collection, *, raw: bool) -> Any:
        kwargs = self._build_find_kwargs(one=True)
        doc = collection.find_one(**kwargs)
        if raw:
            return {"document": doc}
        return [Data(data=doc)] if doc else []

    def _op_insert_one(self, collection: Collection, *, raw: bool) -> Any:
        document = self._require_mapping("document", self.document, allow_empty=False)
        result = collection.insert_one(document)
        payload = {"inserted_id": _stringify(result.inserted_id)}
        if raw:
            return payload
        return [Data(data=payload)]

    def _op_insert_many(self, collection: Collection, *, raw: bool) -> Any:
        documents = _coerce_documents(self.documents)
        if not documents:
            msg = "Insert Many requires a non-empty list of documents."
            raise ValueError(msg)
        result = collection.insert_many(documents, ordered=bool(self.ordered))
        payload = {
            "inserted_ids": [_stringify(_id) for _id in result.inserted_ids],
            "inserted_count": len(result.inserted_ids),
        }
        if raw:
            return payload
        return [Data(data=payload)]

    def _op_update_one(self, collection: Collection, *, raw: bool) -> Any:
        filter_q = self._require_mapping("filter_query", self.filter_query, allow_empty=False)
        update_doc = self._require_mapping("update", self.update, allow_empty=False)
        result = collection.update_one(filter_q, update_doc, upsert=bool(self.upsert))
        return self._format_update_result(result, raw=raw)

    def _op_update_many(self, collection: Collection, *, raw: bool) -> Any:
        filter_q = self._require_mapping("filter_query", self.filter_query, allow_empty=False)
        update_doc = self._require_mapping("update", self.update, allow_empty=False)
        result = collection.update_many(filter_q, update_doc, upsert=bool(self.upsert))
        return self._format_update_result(result, raw=raw)

    def _op_delete_one(self, collection: Collection, *, raw: bool) -> Any:
        filter_q = self._require_mapping("filter_query", self.filter_query, allow_empty=False)
        result = collection.delete_one(filter_q)
        payload = {"deleted_count": result.deleted_count}
        if raw:
            return payload
        return [Data(data=payload)]

    def _op_delete_many(self, collection: Collection, *, raw: bool) -> Any:
        filter_q = self._require_mapping("filter_query", self.filter_query, allow_empty=False)
        result = collection.delete_many(filter_q)
        payload = {"deleted_count": result.deleted_count}
        if raw:
            return payload
        return [Data(data=payload)]

    def _op_count(self, collection: Collection, *, raw: bool) -> Any:
        filter_q = self.filter_query or {}
        upper_bound = int(self.upper_bound or DEFAULT_COUNT_UPPER_BOUND)
        count = collection.count_documents(filter_q, upper_bound=upper_bound)
        payload = {"count": count, "upper_bound": upper_bound}
        if raw:
            return payload
        return [Data(data=payload)]

    def _op_estimated_count(self, collection: Collection, *, raw: bool) -> Any:
        count = collection.estimated_document_count()
        payload = {"estimated_count": count}
        if raw:
            return payload
        return [Data(data=payload)]

    # -- Helpers ------------------------------------------------------

    def _build_find_kwargs(self, *, one: bool = False) -> dict[str, Any]:
        """Build kwargs for ``find`` / ``find_one``, omitting empty values."""
        kwargs: dict[str, Any] = {"filter": self.filter_query or {}}

        if self.projection:
            kwargs["projection"] = self.projection
        if self.sort:
            kwargs["sort"] = self.sort
        if self.include_similarity:
            kwargs["include_similarity"] = True

        if not one:
            limit = int(self.limit) if self.limit else 0
            if limit > 0:
                kwargs["limit"] = limit
            skip = int(self.skip) if self.skip else 0
            if skip > 0:
                kwargs["skip"] = skip
        return kwargs

    @staticmethod
    def _format_update_result(result: Any, *, raw: bool) -> Any:
        payload = {
            "matched_count": getattr(result, "matched_count", None),
            "modified_count": getattr(result, "modified_count", None),
            "upserted_id": _stringify(getattr(result, "upserted_id", None)),
        }
        if raw:
            return payload
        return [Data(data=payload)]

    @staticmethod
    def _require_mapping(field_name: str, value: Any, *, allow_empty: bool = True) -> dict:
        """Validate that a field contains a mapping; raise a clear error otherwise."""
        if value is None or value == "":
            if allow_empty:
                return {}
            msg = f"Field '{field_name}' is required for this operation."
            raise ValueError(msg)
        if not isinstance(value, dict):
            msg = f"Field '{field_name}' must be a JSON object, got {type(value).__name__}."
            raise ValueError(msg)  # noqa: TRY004
        if not value and not allow_empty:
            msg = f"Field '{field_name}' must not be empty for this operation."
            raise ValueError(msg)
        return value


# ----------------------------------------------------------------------
# Module-level helpers (kept outside the class for easy unit-testing)
# ----------------------------------------------------------------------


def _stringify(value: Any) -> Any:
    """Best-effort stringification of Data API id types for JSON-serialisable output."""
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _coerce_documents(value: Any) -> list[dict[str, Any]]:
    """Accept either a ``list[dict]`` or a single ``dict`` and normalise to a list."""
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        # Singleton -- wrap into a list for convenience.
        return [value]
    if isinstance(value, list):
        bad = [i for i, item in enumerate(value) if not isinstance(item, dict)]
        if bad:
            msg = f"Documents list contains non-dict entries at index {bad[0]}."
            raise ValueError(msg)
        return value
    msg = f"Documents must be a list of JSON objects, got {type(value).__name__}."
    raise ValueError(msg)
