# # build router
# router = APIRouter()


# @router.get("/all")
# def get_all():
#     return build_langchain_types_dict()


# Buil test for /all endpoint
from langflow.utils.constants import CUSTOM_TOOLS
from fastapi.testclient import TestClient


def test_get_all(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    # We need to test the custom nodes
    assert "ZeroShotPrompt" in json_response["prompts"]
    # All CUSTOM_TOOLS(dict) should be in the response
    assert all(tool in json_response["tools"] for tool in CUSTOM_TOOLS.keys())
