from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.chroma import ChromaVectorStoreComponent
from lfx.components.FAISS.faiss import FaissVectorStoreComponent
from lfx.components.vectorstores.local_db import LocalDBComponent
from lfx.utils.file_path_security import LocalFileAccessError


@contextmanager
def restricted_file_access(config_dir: Path):
    settings_service = MagicMock()
    settings_service.settings.restrict_local_file_access = True
    settings_service.settings.config_dir = str(config_dir)
    settings_service.settings.database_url = ""
    with patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service):
        yield


def test_chroma_rejects_persist_directory_outside_user_scope(tmp_path: Path) -> None:
    component = ChromaVectorStoreComponent(_user_id="attacker").set(
        collection_name="shared",
        persist_directory=str(tmp_path / "outside"),
        embedding=None,
        ingest_data=[],
        limit=None,
    )

    with (
        restricted_file_access(tmp_path / "config"),
        patch("langchain_chroma.Chroma", return_value=MagicMock()),
        pytest.raises(LocalFileAccessError),
    ):
        component.build_vector_store()


def test_local_db_rejects_before_creating_outside_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    component = LocalDBComponent(_user_id="attacker").set(
        mode="Ingest",
        collection_name="shared",
        persist_directory=str(outside),
        embedding=None,
        ingest_data=[],
        limit=None,
    )

    with (
        restricted_file_access(tmp_path / "config"),
        patch("langchain_chroma.Chroma", return_value=MagicMock()),
        pytest.raises(LocalFileAccessError),
    ):
        component.build_vector_store()

    assert not (outside / "vector_stores" / "shared").exists()


def test_faiss_rejects_persist_directory_outside_user_scope(tmp_path: Path) -> None:
    component = FaissVectorStoreComponent(_user_id="attacker").set(
        persist_directory=str(tmp_path / "outside"),
    )

    with restricted_file_access(tmp_path / "config"), pytest.raises(LocalFileAccessError):
        component.get_persist_directory()
