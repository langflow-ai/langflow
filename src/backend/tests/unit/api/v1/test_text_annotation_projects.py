import io

import pytest
from fastapi import status
from httpx import AsyncClient

NER_PROJECT_PAYLOAD = {
    "name": "NER Demo",
    "description": "person/org tagging",
    "task_type": "ner",
    "entity_labels": [
        {"value": "person", "background": "#FFA39E"},
        {"value": "org", "background": "#5cada0"},
    ],
}

CLASSIFICATION_PROJECT_PAYLOAD = {
    "name": "Sentiment",
    "description": "sentiment demo",
    "task_type": "classification",
    "category_labels": [
        {"value": "positive"},
        {"value": "negative"},
    ],
}

BASE_URL = "api/v1/text-annotation-projects"


async def _create_project(client: AsyncClient, headers, payload=None) -> dict:
    response = await client.post(f"{BASE_URL}/", json=payload or NER_PROJECT_PAYLOAD, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _add_tasks(client: AsyncClient, headers, project_id: str, texts: list[str]) -> list[dict]:
    response = await client.post(
        f"{BASE_URL}/{project_id}/tasks",
        json={"tasks": [{"text": t} for t in texts]},
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def _ner_result(text: str, start: int, end: int, label: str) -> dict:
    return {
        "id": "span-1",
        "type": "labels",
        "from_name": "label",
        "to_name": "text",
        "origin": "manual",
        "value": {"start": start, "end": end, "text": text[start:end], "labels": [label]},
    }


async def test_create_text_annotation_project(client: AsyncClient, logged_in_headers):
    result = await _create_project(client, logged_in_headers)

    assert result["name"] == NER_PROJECT_PAYLOAD["name"]
    assert result["task_type"] == "ner"
    assert result["entity_labels"] == NER_PROJECT_PAYLOAD["entity_labels"]
    assert result["task_count"] == 0
    assert result["labeled_count"] == 0
    assert "id" in result


async def test_create_project_duplicate_name_rejected(client: AsyncClient, logged_in_headers):
    await _create_project(client, logged_in_headers)
    response = await client.post(f"{BASE_URL}/", json=NER_PROJECT_PAYLOAD, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_project_duplicate_label_rejected(client: AsyncClient, logged_in_headers):
    payload = {
        "name": "bad labels",
        "task_type": "ner",
        "entity_labels": [{"value": "person"}, {"value": "person"}],
    }
    response = await client.post(f"{BASE_URL}/", json=payload, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_list_projects_reports_task_and_labeled_counts(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    tasks = await _add_tasks(client, logged_in_headers, project["id"], ["hello world", "goodbye world"])
    result = [_ner_result("hello world", 0, 5, "person")]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{tasks[0]['id']}/annotations",
        json={"result": result},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await client.get(f"{BASE_URL}/", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    results = response.json()
    assert len(results) == 1
    assert results[0]["task_count"] == 2
    assert results[0]["labeled_count"] == 1


async def test_read_project_detail_includes_tasks(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    tasks = await _add_tasks(client, logged_in_headers, project["id"], ["Alice works at Acme"])

    response = await client.get(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    detail = response.json()
    assert detail["task_count"] == 1
    assert len(detail["tasks"]) == 1
    assert detail["tasks"][0]["id"] == tasks[0]["id"]
    assert detail["tasks"][0]["text"] == "Alice works at Acme"
    assert detail["tasks"][0]["is_labeled"] is False


async def test_update_project_labels(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    response = await client.patch(
        f"{BASE_URL}/{project['id']}",
        json={"entity_labels": [{"value": "location", "background": "#000000"}]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["entity_labels"][0]["value"] == "location"


async def test_delete_project_removes_tasks(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    await _add_tasks(client, logged_in_headers, project["id"], ["to be deleted"])
    response = await client.delete(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    response = await client.get(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_save_annotations_validates_label_set(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["hello world"]))[0]
    bad_result = [_ner_result("hello world", 0, 5, "not-a-label")]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": bad_result},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_save_annotations_validates_offsets(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["short"]))[0]
    bad_result = [_ner_result("short", 0, 999, "person")]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": bad_result},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_save_annotations_rejects_type_mismatch(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["hello"]))[0]
    choices_result = [
        {
            "id": "c1",
            "type": "choices",
            "from_name": "choice",
            "to_name": "text",
            "value": {"choices": ["person"]},
        }
    ]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": choices_result},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_classification_round_trip(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers, CLASSIFICATION_PROJECT_PAYLOAD)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["I love this product"]))[0]
    result = [
        {
            "id": "c1",
            "type": "choices",
            "from_name": "choice",
            "to_name": "text",
            "origin": "manual",
            "value": {"choices": ["positive"]},
        }
    ]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": result},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await client.get(f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["result"][0]["value"]["choices"] == ["positive"]


async def test_delete_task(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["delete me"]))[0]
    response = await client.delete(f"{BASE_URL}/{project['id']}/tasks/{task['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    response = await client.get(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    assert response.json()["task_count"] == 0


# --------------------------------------------------------------------------- #
# CSV import
# --------------------------------------------------------------------------- #


async def test_import_csv_with_header(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    csv_content = "title,body\nrow one,first text here\nrow two,second text here\n"
    response = await client.post(
        f"{BASE_URL}/{project['id']}/import/csv",
        files={"file": ("data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"text_column": "body", "name_column": "title"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["created"] == 2

    detail = await client.get(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    tasks = detail.json()["tasks"]
    assert tasks[0]["text"] == "first text here"
    assert tasks[0]["name"] == "row one"
    assert tasks[0]["source"] == "csv"


async def test_import_csv_gbk_encoding(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    csv_content = "文本\n张三在北京工作\n"
    response = await client.post(
        f"{BASE_URL}/{project['id']}/import/csv",
        files={"file": ("data.csv", io.BytesIO(csv_content.encode("gb18030")), "text/csv")},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    detail = await client.get(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    assert detail.json()["tasks"][0]["text"] == "张三在北京工作"


async def test_import_csv_unknown_column_rejected(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    csv_content = "body\nhello\n"
    response = await client.post(
        f"{BASE_URL}/{project['id']}/import/csv",
        files={"file": ("data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"text_column": "missing"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# --------------------------------------------------------------------------- #
# Database import (sqlite via SQLAlchemy URI)
# --------------------------------------------------------------------------- #


async def _make_sqlite_db(tmp_path) -> str:
    import sqlalchemy as sa

    db_path = tmp_path / "import_source.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE docs (id INTEGER PRIMARY KEY, content TEXT)"))
        conn.execute(
            sa.text("INSERT INTO docs (content) VALUES (:c)"),
            [{"c": "db text one"}, {"c": "db text two"}, {"c": None}],
        )
    engine.dispose()
    return f"sqlite:///{db_path}"


async def test_import_from_database(client: AsyncClient, logged_in_headers, tmp_path):
    uri = await _make_sqlite_db(tmp_path)
    project = await _create_project(client, logged_in_headers)

    preview = await client.post(
        f"{BASE_URL}/{project['id']}/import/database/preview",
        json={"connection_uri": uri, "table_name": "docs"},
        headers=logged_in_headers,
    )
    assert preview.status_code == status.HTTP_200_OK, preview.text
    assert preview.json()["columns"] == ["id", "content"]
    assert len(preview.json()["rows"]) == 3

    response = await client.post(
        f"{BASE_URL}/{project['id']}/import/database",
        json={"connection_uri": uri, "table_name": "docs", "text_column": "content"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    # NULL rows are skipped.
    assert response.json()["created"] == 2
    assert response.json()["skipped"] == 1

    detail = await client.get(f"{BASE_URL}/{project['id']}", headers=logged_in_headers)
    assert detail.json()["tasks"][0]["source"] == "database"


async def test_import_from_database_bad_table(client: AsyncClient, logged_in_headers, tmp_path):
    uri = await _make_sqlite_db(tmp_path)
    project = await _create_project(client, logged_in_headers)
    response = await client.post(
        f"{BASE_URL}/{project['id']}/import/database",
        json={"connection_uri": uri, "table_name": "missing", "text_column": "content"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_import_from_database_bad_column(client: AsyncClient, logged_in_headers, tmp_path):
    uri = await _make_sqlite_db(tmp_path)
    project = await _create_project(client, logged_in_headers)
    response = await client.post(
        f"{BASE_URL}/{project['id']}/import/database",
        json={"connection_uri": uri, "table_name": "docs", "text_column": "missing"},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Available" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


async def _build_labeled_ner_project(client: AsyncClient, headers) -> dict:
    project = await _create_project(client, headers)
    task = (await _add_tasks(client, headers, project["id"], ["张三在北京工作"]))[0]
    result = [
        {
            "id": "s1",
            "type": "labels",
            "from_name": "label",
            "to_name": "text",
            "origin": "manual",
            "value": {"start": 0, "end": 2, "text": "张三", "labels": ["person"]},
        },
        {
            "id": "s2",
            "type": "labels",
            "from_name": "label",
            "to_name": "text",
            "origin": "manual",
            "value": {"start": 3, "end": 5, "text": "北京", "labels": ["org"]},
        },
    ]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": result},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return project


async def test_export_conll_char_level_bio(client: AsyncClient, logged_in_headers):
    project = await _build_labeled_ner_project(client, logged_in_headers)
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=conll", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    lines = response.text.strip().split("\n")
    assert lines[0] == "张 B-person"
    assert lines[1] == "三 I-person"
    assert lines[2] == "在 O"
    assert lines[3] == "北 B-org"
    assert lines[4] == "京 I-org"


async def test_export_conll_word_level_bio(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["Alice works at Acme Corp"]))[0]
    result = [
        {
            "id": "s1",
            "type": "labels",
            "from_name": "label",
            "to_name": "text",
            "origin": "manual",
            "value": {"start": 0, "end": 5, "text": "Alice", "labels": ["person"]},
        },
        {
            "id": "s2",
            "type": "labels",
            "from_name": "label",
            "to_name": "text",
            "origin": "manual",
            "value": {"start": 15, "end": 24, "text": "Acme Corp", "labels": ["org"]},
        },
    ]
    response = await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": result},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=conll", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    lines = response.text.strip().split("\n")
    assert lines[0] == "Alice B-person"
    assert "Acme B-org" in lines
    assert "Corp I-org" in lines


async def test_export_csv_ner(client: AsyncClient, logged_in_headers):
    project = await _build_labeled_ner_project(client, logged_in_headers)
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=csv", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.text
    assert "text,start,end,span_text,label" in body
    assert "张三在北京工作,0,2,张三,person" in body
    assert "张三在北京工作,3,5,北京,org" in body


async def test_export_csv_classification(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers, CLASSIFICATION_PROJECT_PAYLOAD)
    task = (await _add_tasks(client, logged_in_headers, project["id"], ["great stuff"]))[0]
    result = [
        {
            "id": "c1",
            "type": "choices",
            "from_name": "choice",
            "to_name": "text",
            "origin": "manual",
            "value": {"choices": ["positive"]},
        }
    ]
    await client.put(
        f"{BASE_URL}/{project['id']}/tasks/{task['id']}/annotations",
        json={"result": result},
        headers=logged_in_headers,
    )
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=csv", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "text,label" in response.text
    assert "great stuff,positive" in response.text


async def test_export_json_label_studio_shape(client: AsyncClient, logged_in_headers):
    project = await _build_labeled_ner_project(client, logged_in_headers)
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=json", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["data"]["text"] == "张三在北京工作"
    result = payload[0]["annotations"][0]["result"]
    assert result[0]["type"] == "labels"
    assert result[0]["value"]["labels"] == ["person"]


async def test_export_conll_rejected_for_classification(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers, CLASSIFICATION_PROJECT_PAYLOAD)
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=conll", headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_export_rejects_unknown_format(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    response = await client.get(f"{BASE_URL}/{project['id']}/export?format=xml", headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.fixture
async def second_user_headers(client):
    """Log in as a second, distinct user (mirrors ``test_endpoints.py``)."""
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_auth_service, session_scope
    from sqlmodel import select

    username = "second_text_annotation_user"
    password = "testpassword"  # noqa: S105  # pragma: allowlist secret

    async with session_scope() as session:
        stmt = select(User).where(User.username == username)
        user = (await session.exec(stmt)).first()
        if user is None:
            user = User(
                username=username,
                password=get_auth_service().get_password_hash(password),
                is_active=True,
                is_superuser=False,
            )
            session.add(user)
            await session.flush()

    login_response = await client.post("api/v1/login", data={"username": username, "password": password})
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


async def test_projects_are_owner_scoped(client: AsyncClient, logged_in_headers, second_user_headers):
    project = await _create_project(client, logged_in_headers)

    response = await client.get(f"{BASE_URL}/", headers=second_user_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []
    response = await client.get(f"{BASE_URL}/{project['id']}", headers=second_user_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_endpoints_require_authentication(client: AsyncClient):
    response = await client.get(f"{BASE_URL}/")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
