"""End-user files outside the database: erased only when they provably belong to that person."""

from pathlib import Path

import pytest
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.requests import approve, create_end_user_request
from langflow.services.data_subjects.storage_steps import KIND_SKIPPED, SKIPPED_SHARED_ACROSS_FLOWS
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service, session_scope
from lfx.utils.end_user_storage import end_user_folder_owners, end_user_folder_segment, record_end_user_folder

from tests.unit.services.data_subjects._seed import create_user


def _config_dir() -> Path:
    return Path(get_settings_service().settings.config_dir)


def _folder_with(name: str, *files: str) -> Path:
    folder = _config_dir() / name
    folder.mkdir(parents=True, exist_ok=True)
    for file_name in files:
        (folder / file_name).write_text(file_name, encoding="utf-8")
    return folder


async def _erase(end_user: str, admin, flow_ids=None):
    async with session_scope() as session:
        request, _ = await create_end_user_request(
            session,
            end_user_id=end_user,
            scope_flow_ids=flow_ids,
            requested_by=admin,
            source=DataSubjectRequestSource.API,
        )
        await approve(session, request, admin)
        plan, request_id = list(request.pending_paths or []), request.id
    return plan, await run_request(request_id)


@pytest.mark.usefixtures("client")
async def test_should_keep_a_config_folder_that_save_to_file_never_wrote():
    admin = await create_user("storage-admin-1", superuser=True)
    unrelated = _folder_with("shared-runtime", "runtime.bin")

    _, status = await _erase("shared-runtime", admin)

    assert status == DataSubjectRequestStatus.DONE.value
    assert (unrelated / "runtime.bin").exists()


@pytest.mark.usefixtures("client")
async def test_should_erase_the_save_folder_recorded_for_that_end_user():
    admin = await create_user("storage-admin-2", superuser=True)
    record_end_user_folder(_config_dir(), "carol", "carol")
    folder = _folder_with("carol", "report.txt")

    _, status = await _erase("carol", admin)

    assert status == DataSubjectRequestStatus.DONE.value
    assert not folder.exists()
    assert end_user_folder_owners(_config_dir(), "carol") is None


@pytest.mark.usefixtures("client")
async def test_should_keep_a_save_folder_shared_with_another_end_user():
    admin = await create_user("storage-admin-3", superuser=True)
    record_end_user_folder(_config_dir(), "a_b", "a@b")
    record_end_user_folder(_config_dir(), "a_b", "a_b")
    folder = _folder_with("a_b", "theirs.txt")

    _, status = await _erase("a_b", admin)

    assert status == DataSubjectRequestStatus.DONE.value
    assert (folder / "theirs.txt").exists()


@pytest.mark.usefixtures("client")
async def test_should_erase_encoded_and_owned_legacy_folders_without_erasing_another_user(tmp_path, monkeypatch):
    """The erase plan must find new saves and old saves while preserving other identities."""
    admin = await create_user("storage-admin-encoded", superuser=True)
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    first, second = "a/b", "a?b"
    first_segment, second_segment = end_user_folder_segment(first), end_user_folder_segment(second)
    record_end_user_folder(_config_dir(), first_segment, first, exclusive=True)
    record_end_user_folder(_config_dir(), second_segment, second, exclusive=True)
    record_end_user_folder(_config_dir(), "a_b", first)
    first_folder = _folder_with(first_segment, "report.txt")
    second_folder = _folder_with(second_segment, "report.txt")
    legacy_folder = _folder_with("a_b", "old.txt")

    _, status = await _erase(first, admin)

    assert status == DataSubjectRequestStatus.DONE.value
    assert not first_folder.exists()
    assert not legacy_folder.exists()
    assert (second_folder / "report.txt").exists()
    assert end_user_folder_owners(_config_dir(), first_segment) is None
    assert end_user_folder_owners(_config_dir(), second_segment) == frozenset({second})


@pytest.mark.usefixtures("client")
async def test_should_erase_legacy_files_for_an_identity_over_the_new_encoding_limit(tmp_path, monkeypatch):
    """The new save limit must not prevent cleanup of files written before it existed."""
    admin = await create_user("storage-admin-long", superuser=True)
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    identity = "a" * 146
    record_end_user_folder(_config_dir(), identity, identity)
    legacy_folder = _folder_with(identity, "old.txt")

    _, status = await _erase(identity, admin)

    assert status == DataSubjectRequestStatus.DONE.value
    assert not legacy_folder.exists()


@pytest.mark.usefixtures("client")
async def test_should_keep_identity_wide_files_when_the_request_is_scoped_to_some_flows():
    admin = await create_user("storage-admin-4", superuser=True)
    owner = await create_user("storage-owner")
    async with session_scope() as session:
        included, excluded = Flow(name="included", user_id=owner), Flow(name="excluded", user_id=owner)
        session.add_all([included, excluded])
        await session.flush()
        included_id = included.id
    record_end_user_folder(_config_dir(), "dana", "dana")
    folder = _folder_with("dana", "from-included.txt", "from-excluded.txt")

    plan, status = await _erase("dana", admin, flow_ids=[included_id])

    assert status == DataSubjectRequestStatus.DONE.value
    assert plan == [{"kind": KIND_SKIPPED, "value": SKIPPED_SHARED_ACROSS_FLOWS}]
    assert (folder / "from-included.txt").exists()
    assert (folder / "from-excluded.txt").exists()


@pytest.mark.usefixtures("client")
async def test_should_plan_identity_wide_files_when_the_request_covers_every_flow():
    admin = await create_user("storage-admin-5", superuser=True)
    record_end_user_folder(_config_dir(), "erin", "erin")
    folder = _folder_with("erin", "from-any-flow.txt")

    plan, status = await _erase("erin", admin)

    assert status == DataSubjectRequestStatus.DONE.value
    assert [item["kind"] for item in plan] == ["fs_sandbox", "save_file_dir", "save_file_dir"]
    assert not folder.exists()
