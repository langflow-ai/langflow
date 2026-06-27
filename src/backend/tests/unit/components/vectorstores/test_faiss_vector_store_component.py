from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from lfx.components.FAISS.faiss import FaissVectorStoreComponent
from lfx.schema.data import Data


class _DeterministicEmbeddings(Embeddings):
    """Tiny deterministic embeddings for local FAISS tests without API keys."""

    def _embed(self, text: str) -> list[float]:
        bucket = sum(ord(char) for char in text) % 997
        return [bucket / 997.0, len(text) / 1000.0, 0.5]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def test_faiss_index_name_is_scoped_by_user(tmp_path: Path) -> None:
    mock_instance = MagicMock()

    with patch("lfx.components.FAISS.faiss.FAISS") as mock_faiss_class:
        mock_faiss_class.from_documents.return_value = mock_instance
        for user_id in ("owner-user", "attacker-user"):
            component = FaissVectorStoreComponent(_user_id=user_id).set(
                index_name="shared_index",
                persist_directory=str(tmp_path / "shared"),
                embedding=None,
                ingest_data=[],
            )
            component.build_vector_store()

    # save_local(folder_path, index_name) — index_name is the second positional arg.
    index_names = [call.args[1] for call in mock_instance.save_local.call_args_list]
    assert len(index_names) == 2
    assert index_names[0] != "shared_index"
    assert index_names[1] != "shared_index"
    assert index_names[0] != index_names[1]


def _persisted_texts(folder: Path, index_name: str, embeddings: Embeddings) -> list[str]:
    """Load a persisted FAISS index and return its stored document texts.

    Reading the docstore avoids ``similarity_search`` (a faiss/OpenMP knn path that
    can hard-abort under a dual-libomp environment) while still verifying exactly
    which documents a user's on-disk index contains.
    """
    store = FAISS.load_local(
        folder_path=str(folder),
        embeddings=embeddings,
        index_name=index_name,
        allow_dangerous_deserialization=True,
    )
    return [doc.page_content for doc in store.docstore._dict.values()]


def test_faiss_same_apparent_namespace_isolated_by_user(tmp_path: Path) -> None:
    shared_dir = tmp_path / "shared_faiss"
    embeddings = _DeterministicEmbeddings()

    owner_component = FaissVectorStoreComponent(_user_id="owner-user").set(
        index_name="shared_index",
        persist_directory=str(shared_dir),
        embedding=embeddings,
        ingest_data=[Data(text="owner-only-vector-private-content")],
    )
    owner_component.build_vector_store()

    # The attacker writes to the same directory + index name. Without per-user
    # scoping this would overwrite the owner's on-disk index files.
    attacker_component = FaissVectorStoreComponent(_user_id="attacker-user").set(
        index_name="shared_index",
        persist_directory=str(shared_dir),
        embedding=embeddings,
        ingest_data=[Data(text="attacker-vector-content")],
    )
    attacker_component.build_vector_store()

    owner_index = owner_component.get_scoped_index_name()
    attacker_index = attacker_component.get_scoped_index_name()

    # Each user gets a distinct, non-raw on-disk index name (no overwrite/collision).
    assert owner_index != "shared_index"
    assert attacker_index != "shared_index"
    assert owner_index != attacker_index
    faiss_files = sorted(p.name for p in shared_dir.glob("*.faiss"))
    assert faiss_files == sorted([f"{owner_index}.faiss", f"{attacker_index}.faiss"])

    # After the attacker's write, each user's persisted index holds only their data.
    owner_texts = _persisted_texts(shared_dir, owner_index, embeddings)
    assert owner_texts == ["owner-only-vector-private-content"]

    attacker_texts = _persisted_texts(shared_dir, attacker_index, embeddings)
    assert attacker_texts == ["attacker-vector-content"]
