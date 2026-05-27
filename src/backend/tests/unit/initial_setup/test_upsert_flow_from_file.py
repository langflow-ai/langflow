"""Regression tests for find_existing_flow / upsert_flow_from_file.

Covers the CI/CD upgrade scenario where a flow file's id differs from the DB
row's id but the flow name is the same. Before the fix the loader hit the
``unique_flow_name`` UniqueConstraint on INSERT and Langflow failed to start.
"""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import orjson
import pytest
from langflow.initial_setup.setup import (
    find_existing_flow,
    get_or_create_default_folder,
    session_scope,
    upsert_flow_from_file,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from lfx.services.deps import get_settings_service
from sqlmodel import select


@contextmanager
def _overwrite_on_name_match(*, enabled: bool):
    """Temporarily override the load_flows_overwrite_on_name_match setting."""
    settings = get_settings_service().settings
    original = settings.load_flows_overwrite_on_name_match
    settings.load_flows_overwrite_on_name_match = enabled
    try:
        yield
    finally:
        settings.load_flows_overwrite_on_name_match = original


async def _create_flow(
    *,
    name: str,
    user_id,
    flow_id=None,
    endpoint_name=None,
    data=None,
) -> Flow:
    """Insert a minimal Flow row and return it."""
    async with session_scope() as session:
        folder = await get_or_create_default_folder(session, user_id)
        flow = Flow(
            id=flow_id or uuid4(),
            name=name,
            description="initial",
            data=data or {"nodes": [], "edges": []},
            user_id=user_id,
            folder_id=folder.id,
            endpoint_name=endpoint_name,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_by_name_when_id_differs() -> None:
    """Match by (user_id, name) when the file's id doesn't exist in the DB."""
    user_id = uuid4()
    original = await _create_flow(name="MyFlow", user_id=user_id)

    async with session_scope() as session:
        result = await find_existing_flow(
            session,
            flow_id=uuid4(),  # different from the one in the DB
            flow_endpoint_name=None,
            user_id=user_id,
            name="MyFlow",
        )
        assert result is not None
        assert result.id == original.id


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_returns_none_for_unmatched_name() -> None:
    user_id = uuid4()
    await _create_flow(name="MyFlow", user_id=user_id)

    async with session_scope() as session:
        result = await find_existing_flow(
            session,
            flow_id=uuid4(),
            flow_endpoint_name=None,
            user_id=user_id,
            name="OtherFlow",
        )
        assert result is None


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_id_match_still_wins() -> None:
    """The id branch still runs first; name fallback only fires on no id match."""
    user_id = uuid4()
    original = await _create_flow(name="N1", user_id=user_id)

    async with session_scope() as session:
        # Mismatched name -- should still match by id and return the original.
        result = await find_existing_flow(
            session,
            flow_id=original.id,
            flow_endpoint_name=None,
            user_id=user_id,
            name="N2",
        )
        assert result is not None
        assert result.id == original.id
        assert result.name == "N1"


@pytest.mark.usefixtures("client")
async def test_find_existing_flow_endpoint_name_scoped_by_user() -> None:
    """Endpoint-name lookup must not return another user's flow when user_id is supplied."""
    user_a = uuid4()
    user_b = uuid4()
    flow_a = await _create_flow(name="A", user_id=user_a, endpoint_name="shared")

    # user_b doesn't have any flow at all -- but unscoped lookup would still match flow_a.
    async with session_scope() as session:
        result = await find_existing_flow(
            session,
            flow_id=uuid4(),
            flow_endpoint_name="shared",
            user_id=user_b,
        )
        assert result is None, "endpoint_name lookup must be scoped by user_id"

        # Scoping to flow_a's user returns it.
        result = await find_existing_flow(
            session,
            flow_id=uuid4(),
            flow_endpoint_name="shared",
            user_id=user_a,
        )
        assert result is not None
        assert result.id == flow_a.id


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_updates_existing_by_name() -> None:
    """Reporter's CI/CD scenario with overwrite enabled: name match updates existing row."""
    user_id = uuid4()
    original = await _create_flow(
        name="MyFlow",
        user_id=user_id,
        data={"nodes": [], "edges": []},
    )

    file_id = uuid4()
    file_content = orjson.dumps(
        {
            "id": str(file_id),
            "name": "MyFlow",
            "description": "updated from file",
            "data": {"nodes": [{"id": "n1"}], "edges": []},
        }
    )

    with _overwrite_on_name_match(enabled=True):
        async with session_scope() as session:
            # Must not raise IntegrityError on the unique_flow_name constraint.
            await upsert_flow_from_file(file_content, "MyFlow", session, user_id)
            await session.commit()

    # Confirm: exactly one row, DB id preserved, content updated.
    async with session_scope() as session:
        flows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(flows) == 1
        updated = flows[0]
        assert updated.id == original.id, "DB id must be preserved on name-matched update"
        assert updated.description == "updated from file"
        assert updated.data == {"nodes": [{"id": "n1"}], "edges": []}


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_default_skips_name_match() -> None:
    """Default (overwrite=False): name match with differing id does NOT crash and does NOT overwrite."""
    user_id = uuid4()
    original = await _create_flow(
        name="MyFlow",
        user_id=user_id,
        data={"nodes": [{"id": "user-node"}], "edges": []},
    )

    file_id = uuid4()
    file_content = orjson.dumps(
        {
            "id": str(file_id),
            "name": "MyFlow",
            "description": "would overwrite",
            "data": {"nodes": [], "edges": []},
        }
    )

    async with session_scope() as session:
        # Must not raise IntegrityError; must not overwrite.
        await upsert_flow_from_file(file_content, "MyFlow", session, user_id)
        await session.commit()

    async with session_scope() as session:
        flows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(flows) == 1
        preserved = flows[0]
        assert preserved.id == original.id
        assert preserved.description == "initial"
        assert preserved.data == {"nodes": [{"id": "user-node"}], "edges": []}


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_creates_when_no_match() -> None:
    """Empty DB -> upsert creates the row with the file's id."""
    user_id = uuid4()
    # Need a default folder for the user so upsert can assign folder_id.
    async with session_scope() as session:
        await get_or_create_default_folder(session, user_id)

    file_id = uuid4()
    file_content = orjson.dumps(
        {
            "id": str(file_id),
            "name": "FreshFlow",
            "description": "brand new",
            "data": {"nodes": [], "edges": []},
        }
    )

    async with session_scope() as session:
        await upsert_flow_from_file(file_content, "FreshFlow", session, user_id)
        await session.commit()

    async with session_scope() as session:
        result = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(result) == 1
        assert result[0].id == file_id
        assert result[0].name == "FreshFlow"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_no_unique_violation_on_repeat() -> None:
    """Calling upsert twice with different file ids and the same name must not raise.

    With overwrite enabled this is the CI/CD nightly-rebuild path: second import updates.
    """
    user_id = uuid4()
    async with session_scope() as session:
        await get_or_create_default_folder(session, user_id)

    def make_payload(flow_id, description: str) -> bytes:
        return orjson.dumps(
            {
                "id": str(flow_id),
                "name": "Recurring",
                "description": description,
                "data": {"nodes": [], "edges": []},
            }
        )

    with _overwrite_on_name_match(enabled=True):
        # First import: row inserted with id=A.
        id_a = uuid4()
        async with session_scope() as session:
            await upsert_flow_from_file(make_payload(id_a, "first"), "Recurring", session, user_id)
            await session.commit()

        # Second import (e.g. nightly upgrade with regenerated UUIDs): same name, id=B.
        # Must update the existing row, not raise IntegrityError.
        id_b = uuid4()
        async with session_scope() as session:
            await upsert_flow_from_file(make_payload(id_b, "second"), "Recurring", session, user_id)
            await session.commit()

    async with session_scope() as session:
        rows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(rows) == 1
        assert rows[0].id == id_a, "DB id from first import is preserved"
        assert rows[0].description == "second"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_id_match_still_overwrites_id_field() -> None:
    """When matched by id, the existing setattr loop is unchanged (no regression)."""
    user_id = uuid4()
    original = await _create_flow(name="IdMatch", user_id=user_id)

    file_content = orjson.dumps(
        {
            "id": str(original.id),  # same id -> matched_by_id is True
            "name": "IdMatch",
            "description": "updated",
            "data": {"nodes": [], "edges": []},
        }
    )

    async with session_scope() as session:
        await upsert_flow_from_file(file_content, "IdMatch", session, user_id)
        await session.commit()

    async with session_scope() as session:
        rows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(rows) == 1
        assert rows[0].id == original.id
        assert rows[0].description == "updated"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_skips_name_match_when_overwrite_disabled() -> None:
    """When load_flows_overwrite_on_name_match=False, name-matched rows are NOT overwritten.

    Protects the case where a user edited a flow in the UI and Langflow restarts with a
    regenerated file id; the on-disk JSON should not silently wipe the user's changes.
    """
    user_id = uuid4()
    original = await _create_flow(
        name="UserEdited",
        user_id=user_id,
        data={"nodes": [{"id": "user-node"}], "edges": []},
    )

    with _overwrite_on_name_match(enabled=False):
        file_content = orjson.dumps(
            {
                "id": str(uuid4()),  # regenerated id -> name match only
                "name": "UserEdited",
                "description": "from disk (should be ignored)",
                "data": {"nodes": [], "edges": []},
            }
        )
        async with session_scope() as session:
            await upsert_flow_from_file(file_content, "UserEdited", session, user_id)
            await session.commit()

    async with session_scope() as session:
        rows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(rows) == 1
        assert rows[0].id == original.id
        # User's UI edits preserved -- file contents did not overwrite them.
        assert rows[0].description == "initial"
        assert rows[0].data == {"nodes": [{"id": "user-node"}], "edges": []}


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_ignores_relationship_keys_in_json() -> None:
    """BUG-001 regression: JSON keys that collide with SQLAlchemy relationships must not crash.

    Previously the loader used ``hasattr(existing, key)`` + ``setattr``. ``hasattr`` returns
    True for relationship attributes (``user``, ``folder``), and ``getattr`` on an unloaded
    relationship under an async session triggers an implicit lazy load outside greenlet
    context, raising ``MissingGreenlet`` ("greenlet_spawn has not been called; can't call
    await_only() here.") and crashing Langflow startup.
    """
    user_id = uuid4()
    original = await _create_flow(name="WithRel", user_id=user_id)

    file_content = orjson.dumps(
        {
            "id": str(uuid4()),  # name-matched path (different id)
            "name": "WithRel",
            "description": "updated",
            "data": {"nodes": [], "edges": []},
            # Adversarial keys that match Flow relationship attribute names.
            # The loader must skip these instead of triggering a lazy load.
            "user": {"id": str(uuid4()), "username": "ghost"},
            "folder": {"id": str(uuid4()), "name": "ghost-folder"},
        }
    )

    with _overwrite_on_name_match(enabled=True):
        async with session_scope() as session:
            await upsert_flow_from_file(file_content, "WithRel", session, user_id)

    async with session_scope() as session:
        rows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(rows) == 1
        assert rows[0].id == original.id
        assert rows[0].description == "updated"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_with_user_loaded_in_same_session() -> None:
    """BUG-001 regression: mimics ``load_flows_from_directory`` session shape.

    ``load_flows_from_directory`` loads the superuser into the session *before* calling
    ``upsert_flow_from_file``. With ``back_populates`` on ``User.flows``, setting
    ``existing.user_id`` (or relying on autoflush at commit) can attempt to sync the
    back-reference and load relationships lazily. Letting ``session_scope`` auto-commit
    here (no explicit ``await session.commit()``) is the exact production code path that
    crashed with ``MissingGreenlet``.
    """
    username = f"u_{uuid4().hex}"
    # Real User row + flow already linked, mirroring a flow created via the UI before
    # the load_flows_path file was added.
    async with session_scope() as session:
        user_row = User(
            username=username,
            password="x",  # noqa: S106
            is_active=True,
            is_superuser=True,
        )
        session.add(user_row)
        await session.flush()
        await session.refresh(user_row)
        user_id = user_row.id
        folder = await get_or_create_default_folder(session, user_id)
        session.add(
            Flow(
                id=uuid4(),
                name=f"le-1134-test-flow-{username}",
                description="initial",
                data={"nodes": [], "edges": []},
                user_id=user_id,
                folder_id=folder.id,
            )
        )

    file_content = orjson.dumps(
        {
            "id": str(uuid4()),  # different id -> name-match path
            "name": f"le-1134-test-flow-{username}",
            "description": "updated from file",
            "data": {"nodes": [{"id": "n1"}], "edges": []},
        }
    )

    with _overwrite_on_name_match(enabled=True):
        async with session_scope() as session:
            # Load *our* user into the session (mirrors load_flows_from_directory loading
            # the superuser). Filter by username so we don't pick up the default langflow
            # superuser the test fixture creates.
            stmt = select(User).where(User.username == username)
            loaded_user = (await session.exec(stmt)).first()
            assert loaded_user is not None
            await upsert_flow_from_file(file_content, f"le-1134-test-flow-{username}", session, loaded_user.id)
            # No explicit commit: session_scope must auto-commit without MissingGreenlet.

    async with session_scope() as session:
        rows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(rows) == 1
        assert rows[0].description == "updated from file"


@pytest.mark.usefixtures("client")
async def test_upsert_flow_from_file_id_match_still_overwrites_when_flag_disabled() -> None:
    """The flag only gates name-matched overwrites; id-matched overwrites are unchanged."""
    user_id = uuid4()
    original = await _create_flow(name="IdMatchFlag", user_id=user_id)

    with _overwrite_on_name_match(enabled=False):
        file_content = orjson.dumps(
            {
                "id": str(original.id),  # same id -> matched_by_id is True
                "name": "IdMatchFlag",
                "description": "updated via id-match",
                "data": {"nodes": [], "edges": []},
            }
        )
        async with session_scope() as session:
            await upsert_flow_from_file(file_content, "IdMatchFlag", session, user_id)
            await session.commit()

    async with session_scope() as session:
        rows = (await session.exec(select(Flow).where(Flow.user_id == user_id))).all()
        assert len(rows) == 1
        assert rows[0].description == "updated via id-match"
