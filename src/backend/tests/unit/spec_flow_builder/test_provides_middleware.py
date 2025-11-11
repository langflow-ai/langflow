import time
import sys
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Build a minimal router app including our validate endpoint
def build_app(monkeypatch) -> TestClient:
    from langflow.spec_flow_builder import api as spec_api

    # Mock component catalog to avoid heavy imports
    fake_catalog: Dict[str, Any] = {
        "processing": {
            "Prompt Template": {
                "template": {
                    "code": {"value": "class PromptComponent(Component):\n    pass"}
                }
            },
        },
        "input_output": {
            "ChatInput": {
                "template": {
                    "code": {"value": "class ChatInput(Component):\n    pass"}
                }
            },
            "ChatOutput": {
                "template": {
                    "code": {"value": "class ChatOutput(Component):\n    pass"}
                }
            },
        },
        "agents": {
            "Agent": {
                "template": {
                    "code": {"value": "class AgentComponent(Component):\n    pass"}
                }
            },
        },
        "tools": {
            "KnowledgeHubSearch": {
                "template": {
                    "code": {"value": "class KnowledgeHubSearchComponent(Component):\n    pass"},
                    # Mark template as supporting tool-mode
                    "tool_config": {"tool_mode": True}
                }
            },
            "APIRequest": {
                "template": {
                    "code": {"value": "class APIRequestComponent(Component):\n    pass"}
                }
            },
        },
    }

    # Patch fetch_all_components to return fake catalog
    from langflow.spec_flow_builder.component_resolver import ComponentResolver

    async def _fake_fetch_all_components(self):
        self._cache = fake_catalog
        return fake_catalog

    monkeypatch.setattr(ComponentResolver, "fetch_all_components", _fake_fetch_all_components)

    # Patch inspector with a lightweight stub
    class StubSchema:
        def __init__(self, class_name: str):
            self.class_name = class_name
            self.module_path = f"langflow.components.{class_name.lower()}"
            # Inputs: agent accepts str/message; chatoutput accepts message; others produce outputs
            if class_name == "AgentComponent":
                self.inputs = [
                    {"name": "input_value", "field_type": "MessageInput"},
                    {"name": "system_message", "field_type": "StrInput"},
                    {"name": "tools", "field_type": "DataInput"},
                ]
                self.input_types = ["Message", "str", "Data"]
            elif class_name == "ChatOutput":
                self.inputs = [{"name": "input_value", "field_type": "MessageInput"}]
                self.input_types = ["Message"]
            else:
                self.inputs = []
                self.input_types = ["any"]

            # Outputs
            if class_name in {"ChatInput", "AgentComponent", "PromptComponent", "KnowledgeHubSearchComponent", "APIRequestComponent"}:
                self.outputs = [{"name": "output", "field_type": "Output"}]
                # Simplify type mapping
                if class_name in {"ChatInput", "AgentComponent"}:
                    self.output_types = ["Message"]
                elif class_name == "PromptComponent":
                    self.output_types = ["str"]
                else:
                    self.output_types = ["Data"]
            else:
                self.outputs = []
                self.output_types = ["any"]

        @property
        def name(self):
            return self.class_name

    class StubInspector:
        def get_component_schema(self, name: str):
            known = {
                "PromptComponent",
                "ChatInput",
                "ChatOutput",
                "AgentComponent",
                "KnowledgeHubSearchComponent",
                "APIRequestComponent",
            }
            return StubSchema(name) if name in known else None

        def get_component_io_mapping(self):
            return {
                "PromptComponent": {"input_field": "template", "output_field": "output", "output_types": ["str"], "input_types": ["str"]},
                "ChatInput": {"input_field": "message", "output_field": "output", "output_types": ["Message"], "input_types": ["Message"]},
                "AgentComponent": {"input_field": "input_value", "output_field": "output", "output_types": ["Message"], "input_types": ["Message", "str", "Data"]},
                "KnowledgeHubSearchComponent": {"input_field": "search_query", "output_field": "output", "output_types": ["Data"], "input_types": ["str"]},
                "APIRequestComponent": {"input_field": "parameters", "output_field": "output", "output_types": ["Data"], "input_types": ["Data"]},
                "ChatOutput": {"input_field": "input_value", "output_field": "output", "output_types": ["Message"], "input_types": ["Message"]},
            }

        def validate_component_connection(self, source_comp, target_comp, source_output, target_input):
            # Accept if types intersect
            src = self.get_component_schema(source_comp)
            tgt = self.get_component_schema(target_comp)
            if not src or not tgt:
                return {"valid": False, "error": "Component schema not found"}
            compatible = any(t in tgt.input_types for t in src.output_types)
            return {
                "valid": compatible,
                "source_types": src.output_types,
                "target_types": tgt.input_types,
                "error": None if compatible else "Type mismatch between components",
            }

    # Patch the inspector in the middleware module import path
    import langflow.spec_flow_builder.provides_validator as pm

    monkeypatch.setitem(
        sys.modules,
        "langflow.services.spec.component_schema_inspector",
        type("mod", (), {"ComponentSchemaInspector": StubInspector}),
    )

    app = FastAPI()
    app.include_router(spec_api.router)
    return TestClient(app)


def test_valid_connections(monkeypatch):
    client = build_app(monkeypatch)

    yaml_spec = """
components:
  - id: eoc-prompt
    name: Agent Instructions
    type: PromptComponent
    provides:
      - useAs: system_prompt
        in: eoc-agent
  - id: eoc-request
    name: EOC Check Request
    type: ChatInput
    provides:
      - useAs: input
        in: eoc-agent
  - id: eoc-agent
    name: EOC Validation Agent
    type: AgentComponent
    provides:
      - useAs: input
        in: eoc-formatter
  - id: eoc-search
    name: EOC Document Search
    type: KnowledgeHubSearchComponent
    asTools: true
    provides:
      - useAs: tools
        in: eoc-agent
  - id: eoc-formatter
    name: EOC Validation Results
    type: ChatOutput
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "errors" in body
    assert len(body["errors"]) == 0


def test_invalid_target_id(monkeypatch):
    client = build_app(monkeypatch)

    yaml_spec = """
components:
  - id: prompt
    type: PromptComponent
    provides:
      - useAs: system_prompt
        in: missing-agent
  - id: agent
    type: AgentComponent
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    body = resp.json()
    assert any("unknown target id" in e.lower() for e in body.get("detail", {}).get("errors", []))


def test_component_cannot_accept_input(monkeypatch):
    client = build_app(monkeypatch)

    # Patch inspector to make ChatOutput not accept inputs
    import langflow.spec_flow_builder.provides_validator as pm
    StubInspector = sys.modules["langflow.services.spec.component_schema_inspector"].ComponentSchemaInspector

    class BadOutputStubInspector(StubInspector):
        def get_component_schema(self, name: str):
            schema = super().get_component_schema(name)
            if schema and name == "ChatOutput":
                schema.inputs = []
                schema.input_types = []
            return schema

    # Repatch
    sys.modules["langflow.services.spec.component_schema_inspector"].ComponentSchemaInspector = BadOutputStubInspector

    yaml_spec = """
components:
  - id: agent
    type: AgentComponent
    provides:
      - useAs: input
        in: sink
  - id: sink
    type: ChatOutput
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    body = resp.json()
    assert any("cannot accept inputs" in e.lower() for e in body.get("detail", {}).get("errors", []))


def test_tools_target_without_tools_input(monkeypatch):
    client = build_app(monkeypatch)

    yaml_spec = """
components:
  - id: search
    type: KnowledgeHubSearchComponent
    asTools: true
    provides:
      - useAs: tools
        in: sink
  - id: sink
    type: ChatOutput
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    body = resp.json()
    assert any("does not expose a 'tools' input" in e for e in body.get("detail", {}).get("errors", []))


def test_as_tools_must_use_tools(monkeypatch):
    client = build_app(monkeypatch)

    yaml_spec = """
components:
  - id: search
    type: KnowledgeHubSearchComponent
    asTools: true
    provides:
      - useAs: input
        in: agent
  - id: agent
    type: AgentComponent
"""

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    body = resp.json()
    assert any("must only use useAs: 'tools'" in e for e in body.get("detail", {}).get("errors", []))


def test_malformed_yaml(monkeypatch):
    client = build_app(monkeypatch)

    yaml_spec = """
components: {}
"""
    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400


def test_yaml_parsing_error(monkeypatch):
    client = build_app(monkeypatch)

    yaml_spec = """
components:
  - id: a
    type: AgentComponent
    provides: [
      - useAs: input
        in: b
"""  # missing closing

    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    assert resp.status_code == 400
    assert "yaml parsing error" in resp.json().get("detail", {}).get("errors", [""])[0].lower()


def test_performance_large_yaml(monkeypatch):
    client = build_app(monkeypatch)

    # Generate large spec with chained provides
    parts = ["components:"]
    num = 500
    for i in range(num):
        comp_type = "ChatInput" if i == 0 else ("AgentComponent" if i % 3 == 0 else "PromptComponent")
        target = f"comp-{i+1}" if i < num - 1 else "sink"
        use_as = "input" if comp_type != "PromptComponent" else "system_prompt"
        parts.append(
            f"  - id: comp-{i}\n    type: {comp_type}\n    provides:\n      - useAs: {use_as}\n        in: {target}"
        )
    parts.append("  - id: sink\n    type: ChatOutput")
    yaml_spec = "\n".join(parts)

    start = time.time()
    resp = client.post("/spec-builder/validate", json={"yaml_content": yaml_spec})
    duration = time.time() - start

    # Should complete within a reasonable time
    assert resp.status_code in (200, 400)
    assert duration < 2.5