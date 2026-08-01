from __future__ import annotations

import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from lfx.schema.data import Data
from lfx_bundles.milvus import milvus as milvus_module

if TYPE_CHECKING:
    import pytest

_DEFAULT_METADATA_TYPES = (str, bool, int, float, dict)


class _RejectingMilvus:
    """Model Milvus' default scalar and JSON metadata contract."""

    def __init__(self, **_kwargs: Any) -> None:
        self.documents: list[Any] = []

    def add_documents(self, documents: list[Any]) -> None:
        for document in documents:
            for field_name, value in document.metadata.items():
                if not isinstance(value, _DEFAULT_METADATA_TYPES):
                    msg = f"Unrecognized datatype for {field_name}."
                    raise ValueError(msg)  # noqa: TRY004 - Match the provider error reported in #9936.
        self.documents.extend(documents)


def _install_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    package = ModuleType("langchain_milvus")
    package.__path__ = []
    vectorstores = ModuleType("langchain_milvus.vectorstores")
    vectorstores.Milvus = _RejectingMilvus
    package.vectorstores = vectorstores

    monkeypatch.setitem(sys.modules, "langchain_milvus", package)
    monkeypatch.setitem(sys.modules, "langchain_milvus.vectorstores", vectorstores)


def test_build_vector_store_filters_metadata_requiring_explicit_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_provider(monkeypatch)
    monkeypatch.setattr(milvus_module, "validate_connector_url_for_ssrf", lambda _uri: None)

    component = milvus_module.MilvusVectorStoreComponent().set(
        uri="milvus_demo.db",
        password="",
        connection_args={},
        collection_name="langflow",
        collection_description="",
        consistency_level="Session",
        index_params={},
        search_params={},
        drop_old=False,
        embedding=MagicMock(name="embedding"),
        primary_field="pk",
        text_field="text",
        vector_field="vector",
        timeout=None,
        ingest_data=[
            Data(
                data={
                    "text": "document",
                    "files": [],
                    "tags": ["one"],
                    "nested": {"key": "value"},
                    "nullable": None,
                    "source": "fixture.txt",
                    "page": 1,
                    "verified": True,
                    "score": 0.5,
                }
            )
        ],
    )

    store = component.build_vector_store()

    assert len(store.documents) == 1
    document = store.documents[0]
    assert document.page_content == "document"
    assert document.metadata == {
        "source": "fixture.txt",
        "page": 1,
        "verified": True,
        "score": 0.5,
        "nested": {"key": "value"},
    }
