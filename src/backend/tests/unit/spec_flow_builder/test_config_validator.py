import sys
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def build_app(monkeypatch, fake_catalog: Dict[str, Any]) -> TestClient:
    from langflow.spec_flow_builder import api as spec_api

    # Patch fetch_all_components to return provided fake catalog
    from langflow.spec_flow_builder.component_resolver import ComponentResolver

    async def _fake_fetch_all_components(self):
        self._cache = fake_catalog
        return fake_catalog

    monkeypatch.setattr(ComponentResolver, "fetch_all_components", _fake_fetch_all_components)

    # Lightweight inspector stub sufficient for cases without provides
    class StubSchema:
        def __init__(self, class_name: str):
            self.class_name = class_name
            self.module_path = f"langflow.components.{class_name.lower()}"
            self.inputs = []
            self.input_types = ["any"]
            self.outputs = []
            self.output_types = ["any"]

        @property
        def name(self):
            return self.class_name

    class StubInspector:
        def get_component_schema(self, name: str):
            return StubSchema(name)

        def get_component_io_mapping(self):
            return {}

        def validate_component_connection(self, source_comp, target_comp, source_output, target_input):
            return {"valid": True, "error": None}

    monkeypatch.setitem(
        sys.modules,
        "langflow.services.spec.component_schema_inspector",
        type("mod", (), {"ComponentSchemaInspector": StubInspector}),
    )

    app = FastAPI()
    app.include_router(spec_api.router)
    return TestClient(app)


def test_config_unknown_key(monkeypatch):
    fake_catalog: Dict[str, Any] = {
        "tools": {
            "APIRequest": {
                "template": {
                    "code": {"value": "class APIRequestComponent(Component):\n    pass"},
                    # Deliberately exclude 'url' to trigger unknown key
                    "headers": {"type": "dict"},
                    "body": {"type": "dict"},
                }
            }
        }
    }

    client = build_app(monkeypatch, fake_catalog)

    yaml_spec = """
components:
  - id: svc
    type: APIRequestComponent
    config:
      url: "http://example.com"
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    body = resp.json()
    assert any("Unknown config key 'url'" in e for e in body.get("detail", {}).get("errors", []))


def test_config_headers_body_type_ignored(monkeypatch):
    fake_catalog: Dict[str, Any] = {
        "tools": {
            "APIRequest": {
                "template": {
                    "code": {"value": "class APIRequestComponent(Component):\n    pass"},
                    # Include keys so they are recognized, but type/list is ignored
                    "headers": {"type": "dict"},
                    "body": {"type": "dict"},
                }
            }
        }
    }

    client = build_app(monkeypatch, fake_catalog)

    yaml_spec = """
components:
  - id: svc
    type: APIRequestComponent
    config:
      headers:
        - name: "Content-Type"
          value: "application/json"
      body:
        - key: "a"
          value: 1
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "errors" in body and len(body["errors"]) == 0


def test_config_missing_required_not_enforced(monkeypatch):
    fake_catalog: Dict[str, Any] = {
        "input_output": {
            "ChatInput": {
                "template": {
                    # Provide a code value so resolver can map class name
                    "code": {"value": "class ChatInput(Component):\n    pass"},
                    # Include 'message' so it's a known key and not flagged
                    "message": {"type": "str"},
                }
            }
        }
    }

    client = build_app(monkeypatch, fake_catalog)

    yaml_spec = """
components:
  - id: req
    type: ChatInput
    config:
      message: "hello"
"""

    # No error even though 'code' is defined in template and missing
    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 200
    body = resp.json()
    assert "errors" in body and len(body["errors"]) == 0


def test_config_type_enforced_for_known_key(monkeypatch):
    fake_catalog: Dict[str, Any] = {
        "input_output": {
            "ChatInput": {
                "template": {
                    # Provide a code value so resolver can map class name
                    "code": {"value": "class ChatInput(Component):\n    pass"},
                    "temperature": {"type": "float"},
                }
            }
        }
    }

    client = build_app(monkeypatch, fake_catalog)

    yaml_spec = """
components:
  - id: req
    type: ChatInput
    config:
      temperature: "hot"
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    body = resp.json()
    assert any("expected float, got str" in e for e in body.get("detail", {}).get("errors", []))