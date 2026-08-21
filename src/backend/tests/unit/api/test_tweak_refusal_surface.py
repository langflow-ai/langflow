"""A refused tweak must reach the caller as a 422, not a 500.

The refusal is raised deep in ``process_tweaks``. Every run route wraps its body
in a broad ``except Exception`` that turns anything unrecognised into a server
error, which both hides the real status and discards the structured body naming
the refused keys. Each route therefore has to let ``TweakRefusedError`` through
on purpose, and that is easy to drop when a handler is next edited.
"""

from fastapi import status


async def test_refused_tweak_returns_422_on_the_v1_sync_run(client, simple_api_test, created_api_key):
    """``code`` is refused by the protected-field floor under every policy."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    node_id = simple_api_test["data"]["nodes"][0]["id"]
    payload = {
        "output_type": "text",
        "tweaks": {node_id: {"code": "import os; os.system('id')"}},
    }

    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "TWEAKS_REFUSED"
    assert detail["fields"] == ["code"]


async def test_an_allowed_tweak_still_runs_on_the_v1_sync_run(client, simple_api_test, created_api_key):
    """The refusal path must not make ordinary tweaks fail."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    node_id = next(
        node["id"] for node in simple_api_test["data"]["nodes"] if node["id"].startswith(("TextInput", "ChatInput"))
    )
    payload = {
        "output_type": "text",
        "tweaks": {node_id: {"input_value": "hello"}},
    }

    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json=payload)

    assert response.status_code == status.HTTP_200_OK, response.text


async def test_refused_tweak_returns_422_on_the_v1_advanced_run(client, simple_api_test, created_api_key):
    """The advanced-run route applies tweaks too, so it needs the same arm.

    Three routes call ``process_tweaks``. Each wraps its body in a broad
    ``except Exception``, so each has to let ``TweakRefusedError`` through on
    purpose. This one was missed on the first pass.
    """
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    node_id = simple_api_test["data"]["nodes"][0]["id"]
    payload = {
        "output_type": "text",
        "tweaks": {node_id: {"code": "import os; os.system('id')"}},
    }

    response = await client.post(f"/api/v1/run/advanced/{flow_id}", headers=headers, json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "TWEAKS_REFUSED"
    assert detail["fields"] == ["code"]
