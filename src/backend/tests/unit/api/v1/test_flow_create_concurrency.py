"""Concurrent creates of the same flow name must each land on a free name."""

import asyncio
import sqlite3
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1 import flows as flows_module
from sqlalchemy.exc import IntegrityError

CONCURRENT_CREATES = 6


async def test_concurrent_creates_of_the_same_name_all_succeed(client: AsyncClient, logged_in_headers):
    """Every racer passes the "is this name free" read, so the insert has to settle it.

    Two browser tabs (or two Playwright workers sharing the auto-login user) that
    click "New Flow" together both read "no such name yet". The loser must be
    renamed to the next free suffix, exactly as a sequential create would be,
    instead of being told the name it never chose is not unique.
    """
    name = f"create-race-{uuid4()}"

    responses = await asyncio.gather(
        *(
            client.post("api/v1/flows/", json={"name": name, "data": {}}, headers=logged_in_headers)
            for _ in range(CONCURRENT_CREATES)
        )
    )

    assert [response.status_code for response in responses] == [status.HTTP_201_CREATED] * CONCURRENT_CREATES, [
        response.text for response in responses
    ]
    names = sorted(response.json()["name"] for response in responses)
    assert names == sorted([name, *(f"{name} ({number})" for number in range(1, CONCURRENT_CREATES))])
    assert len({response.json()["id"] for response in responses}) == CONCURRENT_CREATES


async def test_concurrent_creates_of_the_same_endpoint_name_all_succeed(client: AsyncClient, logged_in_headers):
    """The endpoint name is de-duplicated by the same read-then-insert, so it races the same way."""
    endpoint_name = f"create-race-{uuid4().hex}"

    responses = await asyncio.gather(
        *(
            client.post(
                "api/v1/flows/",
                json={"name": f"create-race-endpoint-{uuid4()}", "endpoint_name": endpoint_name, "data": {}},
                headers=logged_in_headers,
            )
            for _ in range(CONCURRENT_CREATES)
        )
    )

    assert [response.status_code for response in responses] == [status.HTTP_201_CREATED] * CONCURRENT_CREATES, [
        response.text for response in responses
    ]
    endpoint_names = sorted(response.json()["endpoint_name"] for response in responses)
    assert endpoint_names == sorted(
        [endpoint_name, *(f"{endpoint_name}-{number}" for number in range(1, CONCURRENT_CREATES))]
    )


@pytest.mark.parametrize(
    ("constraint", "retried"),
    [
        ("flow.user_id, flow.name", True),
        ("flow.user_id, flow.endpoint_name", True),
        ("flow.id", False),
        ("unrelated.name", False),
    ],
)
def test_only_a_lost_race_for_a_deduplicated_column_is_retried(constraint, retried):
    """A caller-chosen ID that collides stays a conflict: no retry can make it free."""
    driver_error = sqlite3.IntegrityError(f"UNIQUE constraint failed: {constraint}")
    integrity_error = IntegrityError("INSERT INTO flow ...", {}, driver_error)

    assert flows_module._lost_deduplication_race(integrity_error) is retried
