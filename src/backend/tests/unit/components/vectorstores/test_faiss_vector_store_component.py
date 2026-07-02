from pathlib import Path
from typing import Any

import pytest
from langchain_core.documents import Document
from lfx.components.FAISS.faiss import FaissVectorStoreComponent
from lfx.schema.data import Data


class _FakeFAISS:
    def __init__(self, documents: list[Document]) -> None:
        self._documents = documents

    @classmethod
    def from_documents(cls, documents: list[Document], embedding: Any) -> "_FakeFAISS":  # noqa: ARG003
        return cls(documents)

    @classmethod
    def load_local(
        cls,
        folder_path: str,
        embeddings: Any,  # noqa: ARG003
        index_name: str,
        allow_dangerous_deserialization: bool,  # noqa: FBT001
    ) -> "_FakeFAISS":
        if not allow_dangerous_deserialization:
            msg = "Dangerous deserialization is disabled."
            raise ValueError(msg)
        index_path = Path(folder_path) / f"{index_name}.faiss"
        return cls([Document(page_content=index_path.read_text())])

    def save_local(self, folder_path: str, index_name: str) -> None:
        index_path = Path(folder_path) / f"{index_name}.faiss"
        index_path.write_text(self._documents[0].page_content)

    def similarity_search(self, query: str, k: int) -> list[Document]:  # noqa: ARG002
        return self._documents[:k]


def _component(user_id: str, persist_directory: Path, document: str, search_query: str) -> FaissVectorStoreComponent:
    return FaissVectorStoreComponent(_user_id=user_id).set(
        index_name="shared_index",
        persist_directory=str(persist_directory),
        ingest_data=[Data(text=document)],
        embedding=object(),
        search_query=search_query,
        number_of_results=1,
        allow_dangerous_deserialization=True,
    )


def test_faiss_persist_directory_is_scoped_by_user(tmp_path: Path) -> None:
    owner_component = _component("owner-user", tmp_path, "owner document", "owner")
    attacker_component = _component("attacker-user", tmp_path, "attacker document", "attacker")

    owner_path = owner_component.get_persist_directory()
    attacker_path = attacker_component.get_persist_directory()

    assert owner_path != attacker_path
    assert owner_path.parent == attacker_path.parent
    assert tmp_path in owner_path.parents
    assert tmp_path in attacker_path.parents


def test_faiss_same_namespace_cannot_load_another_users_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    attacker_document = "ATTACKER_PRESEEDED_FAISS_DOCUMENT"
    owner_document = "OWNER_EXPECTED_FAISS_DOCUMENT"

    monkeypatch.setattr("lfx.components.FAISS.faiss.FAISS", _FakeFAISS)

    attacker_component = _component("attacker-user", tmp_path, attacker_document, "attacker")
    attacker_results = attacker_component.search_documents()
    assert attacker_results[0].text == attacker_document

    owner_component = _component("owner-user", tmp_path, owner_document, "owner")
    owner_results = owner_component.search_documents()

    assert owner_results[0].text == owner_document
    assert owner_results[0].text != attacker_document


def test_faiss_index_name_cannot_escape_user_scope(tmp_path: Path) -> None:
    component = _component("owner-user", tmp_path, "owner document", "owner").set(index_name="../attacker")

    with pytest.raises(ValueError, match="FAISS index name must be a file name"):
        component.get_index_name()


@pytest.mark.parametrize(
    "index_name",
    [
        "D:shared",  # Windows drive-relative prefix escapes the per-user directory
        "C:",  # bare drive letter
        ":",  # bare colon
        "a:b",  # embedded colon
        ".",  # current directory reference
        "..",  # parent directory reference
        "...",  # all-dot name
    ],
)
def test_faiss_index_name_rejects_drive_qualified_names(tmp_path: Path, index_name: str) -> None:
    component = _component("owner-user", tmp_path, "owner document", "owner").set(index_name=index_name)

    with pytest.raises(ValueError, match="FAISS index name must be a file name"):
        component.get_index_name()


def test_faiss_index_name_accepts_portable_file_name(tmp_path: Path) -> None:
    component = _component("owner-user", tmp_path, "owner document", "owner").set(index_name="my_index")

    assert component.get_index_name() == "my_index"


def test_faiss_persist_directory_is_unscoped_without_runtime_user(tmp_path: Path) -> None:
    component = FaissVectorStoreComponent().set(persist_directory=str(tmp_path))

    assert component.get_persist_directory() == tmp_path.resolve()
