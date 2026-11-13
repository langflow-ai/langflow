import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import UploadFile
from langflow.api.v2.file_replace import record_appended_user_file
from langflow.api.v2.files import upload_user_file
from langflow.services.database.models.file.model import File as UserFile
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session_service, get_settings_service, session_scope
from langflow.services.storage.local import LocalStorageService
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
