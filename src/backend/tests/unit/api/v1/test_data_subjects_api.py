import io
import json
import zipfile
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import col, select

from tests.unit.erase_helpers import wait_for_erase
from tests.unit.services.data_subjects._seed import create_user, end_user_message


@pytest.fixture
def feature_on(monkeypatch):
    monkeypatch.setattr(FEATURE_FLAGS, "data_subject_requests", True)


async def _new_user(client: AsyncClient, admin_headers: dict, username: str) -> tuple[str, dict]:
    created = await client.post(
        "api/v1/users/", json={"username": username, "password": "password-123"}, headers=admin_headers
    )
    assert created.status_code == status.HTTP_201_CREATED, created.text
    user_id = created.json()["id"]
    await client.patch(f"api/v1/users/{user_id}", json={"is_active": True}, headers=admin_headers)
    login = await client.post("api/v1/login", data={"username": username, "password": "password-123"})
    assert login.status_code == status.HTTP_200_OK, login.text
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_should_answer_404_on_every_route_when_the_flag_is_off(client: AsyncClient, logged_in_headers_super_user):
    assert not FEATURE_FLAGS.data_subject_requests
    listing = await client.get("api/v1/data-subjects/requests", headers=logged_in_headers_super_user)
    own = await client.post("api/v1/users/me/deletion-request", headers=logged_in_headers_super_user)

    assert listing.status_code == status.HTTP_404_NOT_FOUND
    assert own.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.usefixtures("feature_on")
async def test_should_forbid_the_queue_when_caller_is_not_an_administrator(
    client: AsyncClient, logged_in_headers_super_user
):
    _, headers = await _new_user(client, logged_in_headers_super_user, f"plain-{uuid4().hex[:8]}")

    response = await client.get("api/v1/data-subjects/requests", headers=headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.usefixtures("feature_on")
async def test_should_let_a_builder_request_repeat_and_withdraw(client: AsyncClient, logged_in_headers_super_user):
    _, headers = await _new_user(client, logged_in_headers_super_user, f"maria-{uuid4().hex[:8]}")

    first = await client.post("api/v1/users/me/deletion-request", headers=headers)
    again = await client.post("api/v1/users/me/deletion-request", headers=headers)
    current = await client.get("api/v1/users/me/deletion-request", headers=headers)
    withdrawn = await client.delete("api/v1/users/me/deletion-request", headers=headers)

    assert first.status_code == status.HTTP_201_CREATED
    assert again.status_code == status.HTTP_200_OK
    assert again.json()["id"] == first.json()["id"]
    assert current.json()["status"] == "requested"
    assert withdrawn.json()["status"] == "withdrawn"
    request_url = f"api/v1/data-subjects/requests/{first.json()['id']}"
    queued = await client.get(request_url, headers=logged_in_headers_super_user)
    assert queued.json()["subject_label"] is not None


@pytest.mark.usefixtures("feature_on")
async def test_should_keep_who_asked_when_a_request_is_refused(client: AsyncClient, logged_in_headers_super_user):
    end_user_id = f"held-{uuid4().hex[:8]}"
    created = await client.post(
        "api/v1/data-subjects/requests",
        json={"subject_type": "end_user", "end_user_id": end_user_id},
        headers=logged_in_headers_super_user,
    )

    refused = await client.post(
        f"api/v1/data-subjects/requests/{created.json()['id']}/refuse",
        json={"note": "Legal hold"},
        headers=logged_in_headers_super_user,
    )

    assert refused.status_code == status.HTTP_200_OK, refused.text
    assert refused.json()["status"] == "refused"
    assert refused.json()["subject_label"] == end_user_id


@pytest.mark.usefixtures("feature_on")
async def test_should_refuse_the_only_superuser_asking_to_be_deleted(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    async with session_scope() as session:
        others = (
            await session.exec(select(User).where(col(User.is_superuser).is_(True), User.id != active_super_user.id))
        ).all()
        for other in others:
            other.is_active = False
            session.add(other)

    response = await client.post("api/v1/users/me/deletion-request", headers=logged_in_headers_super_user)

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert response.json()["detail"]["code"] == "last_administrator"


@pytest.mark.usefixtures("feature_on")
async def test_should_let_another_administrator_approve_an_administrator_leaving(
    client: AsyncClient, logged_in_headers_super_user
):
    username = f"admin-{uuid4().hex[:8]}"
    await create_user(username, superuser=True)
    login = await client.post("api/v1/login", data={"username": username, "password": "test-password-123"})
    leaving = {"Authorization": f"Bearer {login.json()['access_token']}"}

    asked = await client.post("api/v1/users/me/deletion-request", headers=leaving)
    own_approval = await client.post(f"api/v1/data-subjects/requests/{asked.json()['id']}/approve", headers=leaving)
    other_approval = await client.post(
        f"api/v1/data-subjects/requests/{asked.json()['id']}/approve", headers=logged_in_headers_super_user
    )

    assert asked.status_code == status.HTTP_201_CREATED, asked.text
    assert own_approval.status_code == status.HTTP_403_FORBIDDEN
    assert own_approval.json()["detail"]["code"] == "self_approval"
    assert other_approval.status_code == status.HTTP_202_ACCEPTED, other_approval.text


@pytest.mark.usefixtures("feature_on")
async def test_should_refuse_a_deletion_request_made_with_an_api_key(client: AsyncClient, logged_in_headers_super_user):
    _, headers = await _new_user(client, logged_in_headers_super_user, f"keyed-{uuid4().hex[:8]}")
    key = await client.post("api/v1/api_key/", json={"name": "k"}, headers=headers)
    assert key.status_code == status.HTTP_200_OK, key.text

    client.cookies.clear()
    response = await client.post("api/v1/users/me/deletion-request", headers={"x-api-key": key.json()["api_key"]})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.headers["X-Langflow-Error-Code"] == "interactive_login_required"


@pytest.mark.usefixtures("feature_on")
async def test_should_show_badge_filter_and_erase_after_admin_approval(
    client: AsyncClient, logged_in_headers_super_user
):
    user_id, headers = await _new_user(client, logged_in_headers_super_user, f"leaver-{uuid4().hex[:8]}")
    requested = await client.post("api/v1/users/me/deletion-request", headers=headers)

    listing = await client.get("api/v1/users/?deletion_requested=true", headers=logged_in_headers_super_user)
    queue = await client.get("api/v1/data-subjects/requests?open_only=true", headers=logged_in_headers_super_user)
    dry_run = await client.get(
        f"api/v1/data-subjects/requests/{requested.json()['id']}/dry-run", headers=logged_in_headers_super_user
    )
    approved = await client.post(
        f"api/v1/data-subjects/requests/{requested.json()['id']}/approve", headers=logged_in_headers_super_user
    )
    await wait_for_erase(requested.json()["id"])

    assert [user["id"] for user in listing.json()["users"]] == [user_id]
    assert listing.json()["deletion_requests"] == {user_id: "requested"}
    assert queue.json()["total_count"] == 1
    assert dry_run.json()["blocked_by"] is None
    assert approved.status_code == status.HTTP_202_ACCEPTED
    async with session_scope() as session:
        assert await session.get(User, UUID(user_id)) is None


@pytest.mark.usefixtures("feature_on")
async def test_should_find_a_builder_by_username_or_email(client: AsyncClient, logged_in_headers_super_user):
    tag = uuid4().hex[:8]
    email = f"Leaving.Person-{tag}@Example.com"
    user_id, _ = await _new_user(client, logged_in_headers_super_user, email)

    by_email = await client.post(
        "api/v1/data-subjects/requests",
        json={"subject_type": "builder", "username": email.lower()},
        headers=logged_in_headers_super_user,
    )
    exact = await client.post(
        "api/v1/data-subjects/find",
        json={"subject_type": "builder", "username": email},
        headers=logged_in_headers_super_user,
    )
    missing = await client.post(
        "api/v1/data-subjects/find",
        json={"subject_type": "builder", "username": f"nobody-{tag}@example.com"},
        headers=logged_in_headers_super_user,
    )
    both = await client.post(
        "api/v1/data-subjects/find",
        json={"subject_type": "builder", "username": email, "user_id": user_id},
        headers=logged_in_headers_super_user,
    )

    assert by_email.status_code == status.HTTP_201_CREATED, by_email.text
    assert by_email.json()["subject_user_id"] == user_id
    assert by_email.json()["subject_label"] == email
    assert exact.status_code == status.HTTP_200_OK, exact.text
    assert missing.status_code == status.HTTP_404_NOT_FOUND
    assert missing.json()["detail"]["code"] == "subject_not_found"
    assert both.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.usefixtures("feature_on")
async def test_should_suggest_end_user_ids_by_part_of_the_id(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    tag = uuid4().hex[:6]
    async with session_scope() as session:
        flow = Flow(name=f"search-{tag}", user_id=active_super_user.id)
        session.add(flow)
        await session.flush()
        session.add_all(
            [
                end_user_message(flow.id, f"Julia-{tag}", "hi"),
                end_user_message(flow.id, f"Julia-{tag}", "again"),
                end_user_message(flow.id, f"julio-{tag}", "hello"),
                end_user_message(flow.id, f"marcos-{tag}", f"julia-{tag} is my friend"),
            ]
        )

    found = await client.get(
        "api/v1/data-subjects/end-users", params={"search": "JUL"}, headers=logged_in_headers_super_user
    )
    narrowed = await client.get(
        "api/v1/data-subjects/end-users", params={"search": f"ia-{tag}"}, headers=logged_in_headers_super_user
    )
    too_short = await client.get(
        "api/v1/data-subjects/end-users", params={"search": "j"}, headers=logged_in_headers_super_user
    )

    assert found.status_code == status.HTTP_200_OK, found.text
    ours = [match for match in found.json() if match["end_user_id"].endswith(tag)]
    assert ours == [
        {"end_user_id": f"Julia-{tag}", "messages": 2},
        {"end_user_id": f"julio-{tag}", "messages": 1},
    ]
    assert narrowed.json() == [{"end_user_id": f"Julia-{tag}", "messages": 2}]
    assert too_short.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.usefixtures("feature_on")
async def test_should_export_and_erase_an_end_user_through_the_api(
    client: AsyncClient, logged_in_headers_super_user, active_super_user
):
    async with session_scope() as session:
        flow = Flow(name="assistant", user_id=active_super_user.id)
        session.add(flow)
        await session.flush()
        session.add_all(
            [end_user_message(flow.id, "pedro-42", "pedro@example.com"), end_user_message(flow.id, "ana-7", "ana")]
        )
        flow_id = flow.id

    created = await client.post(
        "api/v1/data-subjects/requests",
        json={"subject_type": "end_user", "end_user_id": "pedro-42"},
        headers=logged_in_headers_super_user,
    )
    request_id = created.json()["id"]
    exported = await client.get(
        f"api/v1/data-subjects/requests/{request_id}/export", headers=logged_in_headers_super_user
    )
    approved = await client.post(
        f"api/v1/data-subjects/requests/{request_id}/approve", headers=logged_in_headers_super_user
    )
    await wait_for_erase(request_id)
    remaining = await client.post(
        "api/v1/data-subjects/find",
        json={"subject_type": "end_user", "end_user_id": "ana-7"},
        headers=logged_in_headers_super_user,
    )

    assert created.status_code == status.HTTP_201_CREATED
    archive = zipfile.ZipFile(io.BytesIO(exported.content))
    messages = json.loads(archive.read("messages.json"))
    assert [m["text"] for m in messages] == ["pedro@example.com"]
    assert json.loads(archive.read("manifest.json"))["subject_type"] == "end_user"
    assert approved.status_code == status.HTTP_202_ACCEPTED
    assert remaining.json()["counts"]["messages"] == 1
    async with session_scope() as session:
        assert await session.get(Flow, flow_id) is not None


@pytest.mark.usefixtures("feature_on")
async def test_should_reject_an_ambiguous_end_user_id_with_a_stable_code(
    client: AsyncClient, logged_in_headers_super_user
):
    response = await client.post(
        "api/v1/data-subjects/requests",
        json={"subject_type": "end_user", "end_user_id": "tenant::user"},
        headers=logged_in_headers_super_user,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"]["code"] == "invalid_end_user_id"
    assert response.headers["X-Langflow-Error-Code"] == "invalid_end_user_id"


@pytest.mark.usefixtures("feature_on")
async def test_should_record_who_asked_from_how_the_admin_signed_in(client: AsyncClient, logged_in_headers_super_user):
    key = await client.post("api/v1/api_key/", json={"name": "integration"}, headers=logged_in_headers_super_user)
    assert key.status_code == status.HTTP_200_OK, key.text

    console = await client.post(
        "api/v1/data-subjects/requests",
        json={"subject_type": "end_user", "end_user_id": f"console-{uuid4().hex[:8]}"},
        headers=logged_in_headers_super_user,
    )
    client.cookies.clear()
    integration = await client.post(
        "api/v1/data-subjects/requests",
        json={"subject_type": "end_user", "end_user_id": f"app-{uuid4().hex[:8]}"},
        headers={"x-api-key": key.json()["api_key"]},
    )

    assert console.status_code == status.HTTP_201_CREATED, console.text
    assert console.json()["source"] == "admin"
    assert integration.status_code == status.HTTP_201_CREATED, integration.text
    assert integration.json()["source"] == "api"


async def test_should_accept_admin_delete_with_202_even_when_the_flag_is_off(
    client: AsyncClient, logged_in_headers_super_user
):
    user_id, _ = await _new_user(client, logged_in_headers_super_user, f"gone-{uuid4().hex[:8]}")

    response = await client.delete(f"api/v1/users/{user_id}", headers=logged_in_headers_super_user)
    await wait_for_erase(response.json()["request_id"])

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["detail"] == "User deletion started"
    async with session_scope() as session:
        assert await session.get(User, UUID(user_id)) is None
