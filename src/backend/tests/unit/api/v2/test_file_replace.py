import io
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException, UploadFile
from langflow.api.v2.file_replace import record_appended_user_file
from langflow.api.v2.files import upload_user_file
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session_service, get_settings_service, session_scope
from langflow.services.storage.local import LocalStorageService
from lfx.components.files_and_knowledge.save_file import SaveToFileComponent
from lfx.schema.dataframe import DataFrame
from lfx.utils.file_path_security import user_storage_scope
from sqlmodel import select

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """The server's local storage, kept in this test's directory.

    The generic lookup can hand back lfx's stand-in in this suite.
    """
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    return LocalStorageService(get_session_service(), get_settings_service())


async def _upload(storage, user_id, name: str, content: str):
    data = content.encode("utf-8")
    async with session_scope() as session:
        return await upload_user_file(
            file=UploadFile(filename=name, file=io.BytesIO(data), size=len(data)),
            session=session,
            current_user=await session.get(User, user_id),
            storage_service=storage,
            settings_service=get_settings_service(),
        )


async def _record(storage, user_id, file_path: Path):
    async with session_scope() as session:
        return await record_appended_user_file(file_path, session, await session.get(User, user_id), storage)


async def _entries(user_id) -> list[UserFile]:
    async with session_scope() as session:
        return list((await session.exec(select(UserFile).where(UserFile.user_id == user_id))).all())


def _stored_path(storage, entry) -> Path:
    namespace, name = entry.path.rsplit("/", 1)
    return Path(storage.build_full_path(namespace, name))


async def test_an_append_to_the_stored_file_updates_its_entry(active_user, storage):
    first = await _upload(storage, active_user.id, "ledger.csv", "a,b\n1,2\n")
    stored = _stored_path(storage, first)
    with stored.open("a", encoding="utf-8", newline="") as handle:
        handle.write("4,3\n")

    recorded = await _record(storage, active_user.id, stored)

    [entry] = await _entries(active_user.id)
    assert (recorded.id, recorded.path) == (first.id, first.path) == (entry.id, entry.path)
    assert entry.size == recorded.size == len(b"a,b\n1,2\n4,3\n")


async def test_a_copy_outside_the_users_storage_is_not_recorded_over_their_file(active_user, storage, tmp_path):
    await _upload(storage, active_user.id, "ledger.csv", "a,b\n1,2\n")
    elsewhere = tmp_path / "elsewhere" / "ledger.csv"
    elsewhere.parent.mkdir()
    elsewhere.write_text("x\n", encoding="utf-8")

    assert await _record(storage, active_user.id, elsewhere) is None
    [entry] = await _entries(active_user.id)
    assert entry.size == len(b"a,b\n1,2\n")
    assert _stored_path(storage, entry).read_text(encoding="utf-8") == "a,b\n1,2\n"


async def test_a_file_no_entry_stores_is_not_recorded(active_user, storage):
    loose = Path(storage.build_full_path(f"user-{active_user.id}", "ledger.csv"))
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text("a,b\n1,2\n", encoding="utf-8")

    assert await _record(storage, active_user.id, loose) is None
    assert await _entries(active_user.id) == []


async def test_remote_storage_is_never_recorded_in_place(active_user, storage):
    first = await _upload(storage, active_user.id, "ledger.csv", "a,b\n1,2\n")

    assert await _record(MagicMock(), active_user.id, _stored_path(storage, first)) is None


async def _append_with_save_file(storage, user_id, monkeypatch, name: str, fmt: str, rows: dict):
    """Run Write File with Append on, writing into the user's own storage folder."""
    folder = Path(storage.build_full_path(user_storage_scope(user_id), name)).parent
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(folder)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "restrict_local_file_access", False)
    monkeypatch.setattr(settings, "storage_type", "local")
    component = SaveToFileComponent(_user_id=str(user_id))
    component.set_attributes(
        {
            "input": DataFrame(pd.DataFrame(rows)),
            "file_name": Path(name).stem,
            "local_format": fmt,
            "storage_location": [{"name": "Local"}],
            "append_mode": True,
        }
    )
    with patch("lfx.components.files_and_knowledge.save_file.get_storage_service", return_value=storage):
        return await component.save_to_file()


async def test_a_denied_append_leaves_the_stored_file_unchanged(active_user, storage, monkeypatch):
    first = await _upload(storage, active_user.id, "ledger.csv", "a,b\n1,2\n")
    stored = _stored_path(storage, first)

    with (
        patch(
            "langflow.api.v2.file_replace.ensure_file_permission",
            side_effect=HTTPException(status_code=403, detail="denied"),
        ),
        pytest.raises(HTTPException),
    ):
        await _append_with_save_file(storage, active_user.id, monkeypatch, "ledger.csv", "csv", {"a": [3], "b": [4]})

    assert stored.read_bytes() == b"a,b\n1,2\n"
    [entry] = await _entries(active_user.id)
    assert entry.size == len(b"a,b\n1,2\n")


async def test_an_append_without_a_user_leaves_the_stored_file_unchanged(active_user, storage, monkeypatch):
    first = await _upload(storage, active_user.id, "ledger.csv", "a,b\n1,2\n")

    with (
        patch.object(SaveToFileComponent, "user_id", new_callable=PropertyMock, return_value=None),
        pytest.raises(ValueError, match="User ID is required"),
    ):
        await _append_with_save_file(storage, active_user.id, monkeypatch, "ledger.csv", "csv", {"a": [3], "b": [4]})

    assert _stored_path(storage, first).read_bytes() == b"a,b\n1,2\n"


async def test_an_allowed_append_updates_the_stored_file_and_its_entry(active_user, storage, monkeypatch):
    first = await _upload(storage, active_user.id, "ledger.csv", "a,b\n1,2\n")
    stored = _stored_path(storage, first)

    await _append_with_save_file(storage, active_user.id, monkeypatch, "ledger.csv", "csv", {"b": [4], "a": [3]})

    assert stored.read_bytes() == b"a,b\n1,2\n3,4\n"
    [entry] = await _entries(active_user.id)
    assert (entry.id, entry.size) == (first.id, len(b"a,b\n1,2\n3,4\n"))


async def test_an_excel_overwrite_with_append_on_keeps_the_previous_entry(active_user, storage, monkeypatch):
    workbook = io.BytesIO()
    pd.DataFrame({"a": [1]}).to_excel(workbook, index=False)
    data = workbook.getvalue()
    async with session_scope() as session:
        first = await upload_user_file(
            file=UploadFile(filename="ledger.xlsx", file=io.BytesIO(data), size=len(data)),
            session=session,
            current_user=await session.get(User, active_user.id),
            storage_service=storage,
            settings_service=get_settings_service(),
        )

    await _append_with_save_file(storage, active_user.id, monkeypatch, "ledger.xlsx", "excel", {"a": [2]})

    entries = await _entries(active_user.id)
    assert len(entries) == 2
    previous = next(entry for entry in entries if entry.id == first.id)
    assert previous.size == len(data)
