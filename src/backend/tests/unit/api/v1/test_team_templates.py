from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope


async def test_team_template_crud_sanitizes_source_flow(client: AsyncClient, logged_in_headers, flow) -> None:
    source_data = {
        "nodes": [
            {
                "id": "node-1",
                "type": "genericNode",
                "data": {
                    "node": {
                        "template": {
                            "api_key": {
                                "value": "sk-private",  # pragma: allowlist secret
                                "password": True,
                                "show": True,
                                "type": "str",
                            },
                            "temperature": {"value": 0.2, "show": True, "type": "float"},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    async with session_scope() as session:
        db_flow = await session.get(Flow, flow.id)
        db_flow.data = source_data
        session.add(db_flow)
        await session.commit()

    create_response = await client.post(
        "api/v1/team-templates",
        headers=logged_in_headers,
        json={
            "source_flow_id": str(flow.id),
            "name": "Safe team template",
            "description": "A shared template",
            "category": "assistants",
            "tags": ["team"],
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()
    template = created["flow_data"]["nodes"][0]["data"]["node"]["template"]
    assert template["api_key"]["value"] == ""
    assert template["temperature"]["value"] == 0.2
    assert created["cleared_fields"] == 1

    list_response = await client.get("api/v1/team-templates", headers=logged_in_headers)
    assert list_response.status_code == status.HTTP_200_OK
    assert any(item["id"] == created["id"] for item in list_response.json()["items"])

    get_response = await client.get(f"api/v1/team-templates/{created['id']}", headers=logged_in_headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["source"] == "team"

    delete_response = await client.delete(f"api/v1/team-templates/{created['id']}", headers=logged_in_headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    missing_response = await client.get(f"api/v1/team-templates/{created['id']}", headers=logged_in_headers)
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND
