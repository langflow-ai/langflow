"""A 1.12.x local Chroma store for the upgrade-then-erase tests, and helpers that run an approved erase."""

from __future__ import annotations

import sqlite3
import tarfile
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.requests import approve, create_builder_request, create_end_user_request
from langflow.services.database.models.data_subject_request import DataSubjectRequest, DataSubjectRequestSource
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope

from tests.unit.services.data_subjects._seed import create_user

FIXTURE = Path(__file__).resolve().parents[5] / "lfx/tests/unit/base/knowledge_bases/fixtures/chroma-1.5.9-local.tar.gz"
# The base is named after the fixture's collection, as 1.12.x named a Memory Base's collection after its KB.
KB_NAME = "fixture-l2"
OWNER = "memory-owner"
ALICE = "eu-alice-7f3"
BOB = "eu-bob-2c9"
TAGGED_CHUNKS = {"doc-1": ALICE, "doc-2": ALICE, "doc-3": BOB}


def install_legacy_store(root: Path, username: str) -> None:
    """A 1.12.x Memory Base: the real Chroma 1.5.9 fixture, with chunks stamped by end user."""
    source = root / username / KB_NAME
    with tarfile.open(FIXTURE) as archive:
        for member in archive:
            if not (member.isfile() and member.name.startswith("source/")):
                continue
            destination = source / Path(member.name).relative_to("source")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as stream:
                destination.write_bytes(stream.read())
    with closing(sqlite3.connect(source / "chroma.sqlite3")) as connection:
        for embedding_id, end_user in TAGGED_CHUNKS.items():
            (row_id,) = connection.execute(
                "SELECT e.id FROM embeddings e JOIN segments s ON e.segment_id = s.id "
                "JOIN collections c ON s.collection = c.id "
                "WHERE c.name = ? AND s.scope = 'METADATA' AND e.embedding_id = ?",
                (KB_NAME, embedding_id),
            ).fetchone()
            connection.execute(
                "INSERT INTO embedding_metadata (id, key, string_value) VALUES (?, 'end_user_id', ?)",
                (row_id, end_user),
            )
        connection.commit()


async def run(request_id: UUID) -> tuple[str | None, DataSubjectRequest]:
    status = await run_request(request_id)
    async with session_scope() as session:
        return status, await session.get(DataSubjectRequest, request_id)


async def erase_end_user(end_user: str, scope_flow_ids: list[UUID] | None = None):
    admin = await create_user(f"admin-{uuid4().hex[:8]}", superuser=True)
    async with session_scope() as session:
        request, _ = await create_end_user_request(
            session,
            end_user_id=end_user,
            scope_flow_ids=scope_flow_ids,
            requested_by=admin,
            source=DataSubjectRequestSource.API,
        )
        await approve(session, request, admin)
        request_id = request.id
    return await run(request_id)


async def erase_builder(user_id: UUID):
    admin = await create_user(f"admin-{uuid4().hex[:8]}", superuser=True)
    async with session_scope() as session:
        user = await session.get(User, user_id)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=admin, source=DataSubjectRequestSource.ADMIN
        )
        await approve(session, request, admin)
        request_id = request.id
    return await run(request_id)
