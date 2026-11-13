import io

import pytest
from fastapi import HTTPException, UploadFile
from langflow.api.v2.file_replace import replace_user_file
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


def _upload(name: str, content: str) -> UploadFile:
    data = content.encode("utf-8")
    return UploadFile(filename=name, file=io.BytesIO(data), size=len(data))


async def _send(sender, storage, user_id, name: str, content: str):
    async with session_scope() as session:
        user = await session.get(User, user_id)
        return await sender(
            file=_upload(name, content),
            session=session,
            current_user=user,
            storage_service=storage,
            settings_service=get_settings_service(),
        )


async def _entries(user_id) -> list[UserFile]:
    async with session_scope() as session:
        return list((await session.exec(select(UserFile).where(UserFile.user_id == user_id))).all())


async def _stored(storage, entry: UserFile) -> str:
    namespace, name = entry.path.rsplit("/", 1)
    return (await storage.get_file(flow_id=namespace, file_name=name)).decode("utf-8")


async def test_replacing_rewrites_the_existing_entry_instead_of_adding_a_copy(active_user, storage):
    first = await _send(upload_user_file, storage, active_user.id, "ledger.csv", "a,b\n1,2\n")

    replaced = await _send(replace_user_file, storage, active_user.id, "ledger.csv", "a,b\n1,2\n4,3\n")

    [entry] = await _entries(active_user.id)
    assert (replaced.id, replaced.path) == (first.id, first.path)
    assert entry.name == "ledger"
    assert await _stored(storage, entry) == "a,b\n1,2\n4,3\n"
    assert entry.size == replaced.size == len(b"a,b\n1,2\n4,3\n")


async def test_replacing_a_file_the_user_does_not_have_uploads_it(active_user, storage):
    created = await _send(replace_user_file, storage, active_user.id, "ledger.csv", "a,b\n1,2\n")

    [entry] = await _entries(active_user.id)
    assert (entry.id, entry.name) == (created.id, "ledger")
    assert await _stored(storage, entry) == "a,b\n1,2\n"


async def test_a_file_with_the_same_name_but_another_format_is_left_alone(active_user, storage):
    await _send(upload_user_file, storage, active_user.id, "ledger.txt", "notes")

    await _send(replace_user_file, storage, active_user.id, "ledger.csv", "a,b\n1,2\n")

    entries = {entry.name: entry for entry in await _entries(active_user.id)}
    assert sorted(entries) == ["ledger", "ledger (1)"]
    assert await _stored(storage, entries["ledger"]) == "notes"


async def test_replacing_refuses_content_over_the_upload_limit(active_user, storage, monkeypatch):
    await _send(upload_user_file, storage, active_user.id, "ledger.csv", "a,b\n1,2\n")
    monkeypatch.setattr(get_settings_service().settings, "max_file_size_upload", 0)

    with pytest.raises(HTTPException) as refusal:
        await _send(replace_user_file, storage, active_user.id, "ledger.csv", "a,b\n1,2\n4,3\n")

    assert refusal.value.status_code == 413
    [entry] = await _entries(active_user.id)
    assert await _stored(storage, entry) == "a,b\n1,2\n"
