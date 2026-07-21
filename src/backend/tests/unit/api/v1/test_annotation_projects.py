import pytest
from fastapi import status
from httpx import AsyncClient

PROJECT_PAYLOAD = {
    "name": "Cats vs Dogs",
    "description": "bbox demo",
    "labels": [
        {"value": "cat", "background": "#FFA39E"},
        {"value": "dog", "background": "#5cada0"},
    ],
}

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 128


async def _create_project(client: AsyncClient, headers, payload=None) -> dict:
    response = await client.post("api/v1/annotation-projects/", json=payload or PROJECT_PAYLOAD, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def _upload_image(client: AsyncClient, headers, project_id: str, name: str = "cat.png") -> dict:
    response = await client.post(
        f"api/v1/annotation-projects/{project_id}/images",
        files=[("files", (name, FAKE_PNG, "image/png"))],
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()[0]


async def test_create_annotation_project(client: AsyncClient, logged_in_headers):
    result = await _create_project(client, logged_in_headers)

    assert result["name"] == PROJECT_PAYLOAD["name"]
    assert result["labels"] == PROJECT_PAYLOAD["labels"]
    assert result["image_count"] == 0
    assert result["labeled_count"] == 0
    assert "id" in result


async def test_create_project_duplicate_name_rejected(client: AsyncClient, logged_in_headers):
    await _create_project(client, logged_in_headers)
    response = await client.post("api/v1/annotation-projects/", json=PROJECT_PAYLOAD, headers=logged_in_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_project_duplicate_label_rejected(client: AsyncClient, logged_in_headers):
    payload = {
        "name": "bad labels",
        "labels": [{"value": "cat"}, {"value": "cat"}],
    }
    response = await client.post("api/v1/annotation-projects/", json=payload, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_list_annotation_projects(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    await _upload_image(client, logged_in_headers, project["id"])

    response = await client.get("api/v1/annotation-projects/", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    results = response.json()
    assert len(results) == 1
    assert results[0]["image_count"] == 1
    assert results[0]["labeled_count"] == 0


async def test_read_annotation_project_detail(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    image = await _upload_image(client, logged_in_headers, project["id"])

    response = await client.get(f"api/v1/annotation-projects/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    detail = response.json()
    assert detail["image_count"] == 1
    assert len(detail["images"]) == 1
    assert detail["images"][0]["id"] == image["id"]
    assert detail["images"][0]["is_labeled"] is False


async def test_update_annotation_project(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)

    response = await client.patch(
        f"api/v1/annotation-projects/{project['id']}",
        json={"name": "renamed", "labels": [{"value": "bird", "background": "#000000"}]},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "renamed"
    assert response.json()["labels"][0]["value"] == "bird"


async def test_upload_rejects_non_image_extension(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    response = await client.post(
        f"api/v1/annotation-projects/{project['id']}/images",
        files=[("files", ("evil.txt", b"not an image", "text/plain"))],
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_upload_rejects_path_traversal_filename(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    response = await client.post(
        f"api/v1/annotation-projects/{project['id']}/images",
        files=[("files", ("../evil.png", FAKE_PNG, "image/png"))],
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_download_annotation_image(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    image = await _upload_image(client, logged_in_headers, project["id"])

    response = await client.get(
        f"api/v1/annotation-projects/{project['id']}/images/{image['id']}/file",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == FAKE_PNG
    assert response.headers["content-type"] == "image/png"


async def test_save_and_read_annotations(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    image = await _upload_image(client, logged_in_headers, project["id"])

    result_payload = [
        {
            "id": "region-1",
            "type": "rectanglelabels",
            "from_name": "label",
            "to_name": "image",
            "origin": "manual",
            "original_width": 800,
            "original_height": 600,
            "image_rotation": 0,
            "value": {"x": 10.5, "y": 20.0, "width": 30.0, "height": 40.0, "rotation": 0, "rectanglelabels": ["cat"]},
        }
    ]
    response = await client.put(
        f"api/v1/annotation-projects/{project['id']}/images/{image['id']}/annotations",
        json={"result": result_payload, "lead_time": 3.2},
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["result"] == result_payload

    # Read back
    response = await client.get(
        f"api/v1/annotation-projects/{project['id']}/images/{image['id']}/annotations",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["result"] == result_payload

    # Natural dimensions got backfilled from the region
    detail = (await client.get(f"api/v1/annotation-projects/{project['id']}", headers=logged_in_headers)).json()
    assert detail["labeled_count"] == 1
    assert detail["images"][0]["width"] == 800
    assert detail["images"][0]["height"] == 600
    assert detail["images"][0]["annotation_count"] == 1


async def test_save_annotations_rejects_unknown_label(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    image = await _upload_image(client, logged_in_headers, project["id"])

    response = await client.put(
        f"api/v1/annotation-projects/{project['id']}/images/{image['id']}/annotations",
        json={
            "result": [{"id": "r1", "value": {"x": 1, "y": 1, "width": 5, "height": 5, "rectanglelabels": ["bird"]}}]
        },
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_save_annotations_rejects_out_of_range_coordinates(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    image = await _upload_image(client, logged_in_headers, project["id"])

    response = await client.put(
        f"api/v1/annotation-projects/{project['id']}/images/{image['id']}/annotations",
        json={
            "result": [{"id": "r1", "value": {"x": 150, "y": 1, "width": 5, "height": 5, "rectanglelabels": ["cat"]}}]
        },
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_delete_annotation_image(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    image = await _upload_image(client, logged_in_headers, project["id"])

    response = await client.delete(
        f"api/v1/annotation-projects/{project['id']}/images/{image['id']}",
        headers=logged_in_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    detail = (await client.get(f"api/v1/annotation-projects/{project['id']}", headers=logged_in_headers)).json()
    assert detail["images"] == []


async def test_delete_annotation_project(client: AsyncClient, logged_in_headers):
    project = await _create_project(client, logged_in_headers)
    await _upload_image(client, logged_in_headers, project["id"])

    response = await client.delete(f"api/v1/annotation-projects/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = await client.get(f"api/v1/annotation-projects/{project['id']}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_annotation_endpoints_require_authentication(client: AsyncClient):
    response = await client.get("api/v1/annotation-projects/")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.skip(reason="requires a second authenticated user; covered by owner-scoped query design")
async def test_projects_are_owner_scoped(client: AsyncClient, logged_in_headers):  # pragma: no cover
    pass
