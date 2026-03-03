"""End-to-end scenario runner for deployment creation API.

This script focuses on deployment creation scenarios for the watsonx adapter.
It provisions a provider account, creates reference config/snapshot resources,
runs a scenario matrix for POST /api/v1/deployments, and always performs
best-effort cleanup in reverse dependency order.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import load_dotenv

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNPROCESSABLE_CONTENT = 422
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_NOT_FOUND = 404

_INVALID_WXO_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]")


@dataclass(slots=True)
class ScenarioResult:
    name: str
    expected_statuses: set[int]
    actual_status: int
    ok: bool
    response_excerpt: str


class DeploymentCreateE2E:
    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        provider_backend_url: str,
        provider_api_key: str,
        provider_key: str,
        project_id: str,
        keep_resources: bool,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.timeout_seconds = timeout_seconds
        self.provider_backend_url = provider_backend_url
        self.provider_api_key = provider_api_key
        self.provider_key = provider_key
        self.project_id = project_id
        self.keep_resources = keep_resources

        self.client: httpx.AsyncClient | None = None

        self.provider_id: str | None = None
        self.provider_was_created = False
        self.created_deployment_ids: set[str] = set()
        self.created_flow_ids: set[str] = set()
        self.created_project_ids: set[str] = set()

        self.out_of_scope_checkpoint_id: str | None = None
        self.explicit_mismatch_project_id: str | None = None

        self.run_suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]

    async def run(self) -> int:
        print("Starting deployment-create E2E scenario runner...")
        print(
            "Run config: "
            f"base_url={self.base_url}, "
            f"provider_key={self.provider_key}, "
            f"project_id={self.project_id}, "
            f"keep_resources={self.keep_resources}"
        )
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds)

        exit_code = 0
        try:
            await self._create_provider_account()
            ref_checkpoint_id_primary = await self._create_reference_checkpoint(label="checkpoint-ref-primary")
            ref_checkpoint_id_secondary = await self._create_reference_checkpoint(label="checkpoint-ref-secondary")
            out_of_scope_project_id = await self._create_project(label="history-out-of-scope")
            self.out_of_scope_checkpoint_id = await self._create_reference_checkpoint(
                label="checkpoint-out-of-scope",
                folder_id=out_of_scope_project_id,
            )
            self.explicit_mismatch_project_id = await self._create_project(label="history-explicit-target")

            scenario_results = await self._run_create_scenarios(
                reference_checkpoint_ids=[ref_checkpoint_id_primary, ref_checkpoint_id_secondary],
            )
            all_results = [*scenario_results]
            self._print_summary(all_results)

            failing = [result for result in all_results if not result.ok]
            if failing:
                exit_code = 1
        finally:
            try:
                if not self.keep_resources:
                    await self._cleanup_resources()
            finally:
                await self.client.aclose()
                self.client = None

        return exit_code

    async def _create_provider_account(self) -> None:
        existing_provider_id = await self._find_matching_provider_id()
        if existing_provider_id:
            self.provider_id = existing_provider_id
            self.provider_was_created = False
            print(f"Reusing existing provider account: {self.provider_id}")
            return

        payload = {
            "provider_key": self.provider_key,
            "backend_url": self.provider_backend_url,
            "api_key": self.provider_api_key,
        }
        response = await self._request("POST", "/api/v1/deployments/providers/", json_body=payload)
        self._expect_status(response, {201}, "create provider account")
        body = response.json()
        self.provider_id = str(body["id"])
        self.provider_was_created = True
        print(f"Provider account created: {self.provider_id}")

    async def _find_matching_provider_id(self) -> str | None:
        if self.provider_key != "watsonx-orchestrate":
            return None
        expected_account_id = self._derive_watsonx_account_id_from_backend_url()
        if not expected_account_id:
            return None

        try:
            response = await self._request(
                "GET",
                "/api/v1/deployments/providers/?page=1&size=100",
            )
        except httpx.HTTPError as exc:
            print(f"[warning] provider lookup failed; will attempt provider create: {exc}")
            return None
        if response.status_code != HTTP_OK:
            return None
        payload = response.json()
        providers = payload.get("deployment_providers")
        if not isinstance(providers, list):
            return None
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            if provider.get("provider_key") != "watsonx-orchestrate":
                continue
            if provider.get("backend_url") != self.provider_backend_url:
                continue
            if provider.get("account_id") != expected_account_id:
                continue
            provider_id = provider.get("id")
            if isinstance(provider_id, str) and provider_id.strip():
                return provider_id
        return None

    def _derive_watsonx_account_id_from_backend_url(self) -> str | None:
        parsed = urlparse(self.provider_backend_url)
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        try:
            instances_index = path_segments.index("instances")
        except ValueError:
            return None
        account_index = instances_index + 1
        if account_index >= len(path_segments):
            return None
        account_id = path_segments[account_index].strip()
        return account_id or None

    async def _create_reference_checkpoint(self, *, label: str, folder_id: str | None = None) -> str:
        flow_id = await self._create_reference_flow(label=label, folder_id=folder_id)
        response = await self._request("POST", f"/api/v1/flows/{flow_id}/history/", json_body={})
        self._expect_status(response, {201}, "create reference checkpoint")
        checkpoint_id = str(response.json()["id"])
        print(f"Reference checkpoint created: {checkpoint_id}")
        return checkpoint_id

    async def _create_project(self, *, label: str) -> str:
        payload = {
            "name": self._mk_name(f"proj-{label}"),
            "description": "project for deployment create e2e scenarios",
            "flows_list": [],
            "components_list": [],
        }
        response = await self._request("POST", "/api/v1/projects/", json_body=payload)
        self._expect_status(response, {HTTP_CREATED}, "create project")
        project_id = str(response.json()["id"])
        self.created_project_ids.add(project_id)
        print(f"Project created: {project_id}")
        return project_id

    async def _create_reference_flow(self, *, label: str, folder_id: str | None = None) -> str:
        payload = {
            "name": self._mk_name(f"flow-{label}"),
            "description": "reference flow for deployment create scenarios",
            "data": self._build_flow_data_payload(),
            "is_component": False,
        }
        if folder_id is not None:
            payload["folder_id"] = folder_id
        response = await self._request("POST", "/api/v1/flows/", json_body=payload)
        self._expect_status(response, {201}, "create reference flow")
        flow_id = str(response.json()["id"])
        self.created_flow_ids.add(flow_id)
        print(f"Reference flow created: {flow_id}")
        return flow_id

    async def _run_create_scenarios(
        self,
        *,
        reference_checkpoint_ids: list[str],
    ) -> list[ScenarioResult]:
        self._require_provider_id()
        reference_checkpoint_id = reference_checkpoint_ids[0]
        reference_checkpoint_id_2 = reference_checkpoint_ids[1]
        out_of_scope_checkpoint_id = self.out_of_scope_checkpoint_id
        explicit_mismatch_project_id = self.explicit_mismatch_project_id
        if out_of_scope_checkpoint_id is None or explicit_mismatch_project_id is None:
            msg = "Out-of-scope checkpoint setup is missing."
            raise RuntimeError(msg)

        scenarios = [
            {
                "name": "create_flow_versions_ref_config",
                "expected": {HTTP_BAD_REQUEST},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [reference_checkpoint_id]},
                    config={"reference_id": "cfg-ref-does-not-exist"},
                ),
            },
            {
                "name": "create_flow_versions_raw_config",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [reference_checkpoint_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-create")},
                ),
            },
            {
                "name": "create_flow_versions_raw_payloads_rejected",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"raw_payloads": [self._build_flow_payload(label="flow-raw")]},
                    config={"reference_id": "cfg-ref-does-not-exist"},
                ),
            },
            {
                "name": "create_no_flow_versions_no_config",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                ),
            },
            {
                "name": "create_flow_versions_with_two_ids",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [reference_checkpoint_id, reference_checkpoint_id_2]},
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-two-refs")},
                ),
            },
            {
                "name": "create_flow_versions_with_mixed_project_ids",
                "expected": {HTTP_NOT_FOUND},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [reference_checkpoint_id, out_of_scope_checkpoint_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-mixed-project-refs")},
                ),
            },
            {
                "name": "create_flow_versions_without_project_id_outside_default_project",
                "expected": {HTTP_NOT_FOUND},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [out_of_scope_checkpoint_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-outside-default")},
                ),
            },
            {
                "name": "create_flow_versions_with_explicit_project_mismatch",
                "expected": {HTTP_NOT_FOUND},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [out_of_scope_checkpoint_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-explicit-mismatch")},
                    project_id=explicit_mismatch_project_id,
                ),
            },
            {
                "name": "create_flow_versions_with_both_ids_and_raw",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={
                        "ids": [reference_checkpoint_id],
                        "raw_payloads": [self._build_flow_payload(label="flow-both")],
                    },
                    config={"reference_id": "cfg-ref-does-not-exist"},
                ),
            },
            {
                "name": "create_config_with_both_reference_and_raw",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    flow_versions={"ids": [reference_checkpoint_id]},
                    config={
                        "reference_id": "cfg-ref-does-not-exist",
                        "raw_payload": self._build_config_payload(label="cfg-both"),
                    },
                ),
            },
            {
                "name": "create_with_unsupported_mcp_type",
                "expected": {HTTP_BAD_REQUEST},
                "payload": self._build_create_payload(
                    deployment_type="mcp",
                    flow_versions={"ids": [reference_checkpoint_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-mcp")},
                ),
            },
        ]

        results: list[ScenarioResult] = []
        for index, scenario in enumerate(scenarios, start=1):
            print(f"[{index}/{len(scenarios)}] Running {scenario['name']} ...")
            response = await self._request(
                "POST",
                "/api/v1/deployments",
                json_body=scenario["payload"],
            )

            status_code = response.status_code
            ok = status_code in scenario["expected"]
            print(f"[{scenario['name']}] status={status_code}, expected={sorted(scenario['expected'])}")
            if status_code == HTTP_CREATED:
                try:
                    response_payload = response.json()
                    deployment_id = str(response_payload["id"])
                    self.created_deployment_ids.add(deployment_id)

                    print(
                        f"[{scenario['name']}] tracked deployment_id={deployment_id}, "
                        f"config_id={response_payload.get('config_id')}, "
                        f"snapshot_ids={response_payload.get('snapshot_ids') or []}"
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"[warning] created deployment missing id: {exc}")

            excerpt = self._excerpt_response(response)
            results.append(
                ScenarioResult(
                    name=str(scenario["name"]),
                    expected_statuses=set(scenario["expected"]),
                    actual_status=status_code,
                    ok=ok,
                    response_excerpt=excerpt,
                )
            )
        return results

    def _build_create_payload(
        self,
        *,
        deployment_type: str,
        flow_versions: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider_id": self.provider_id,
            "spec": {
                "name": self._mk_name(f"dep-{deployment_type}"),
                "description": "e2e deployment create scenario",
                "type": deployment_type,
            },
        }
        if flow_versions is not None:
            payload["flow_versions"] = flow_versions
        if config is not None:
            payload["config"] = config
        if project_id is not None:
            payload["project_id"] = project_id
        return payload

    def _build_flow_payload(self, *, label: str) -> dict[str, Any]:
        flow_id = str(uuid4())
        return {
            "id": flow_id,
            "name": self._mk_name(label),
            "description": "e2e flow payload",
            "data": self._build_flow_data_payload(),
            "tags": ["e2e", "deployment-create"],
            "provider_data": {
                "project_id": self.project_id,
            },
        }

    def _build_flow_data_payload(self) -> dict[str, Any]:
        chat_input_node_id = f"ChatInput-{uuid4().hex[:8]}"
        chat_output_node_id = f"ChatOutput-{uuid4().hex[:8]}"
        # Watsonx tool export requires a ChatInput node in the flow graph.
        return {
            "nodes": [
                {
                    "id": chat_input_node_id,
                    "type": "genericNode",
                    "position": {"x": 100, "y": 100},
                    "data": {
                        "type": "ChatInput",
                        "id": chat_input_node_id,
                        "node": {
                            "display_name": "Chat Input",
                            "base_classes": ["str"],
                            "template": {
                                "_type": "CustomComponent",
                                "message": {
                                    "name": "message",
                                    "display_name": "message",
                                    "type": "str",
                                    "value": "",
                                    "required": False,
                                    "show": True,
                                },
                            },
                        },
                    },
                },
                {
                    "id": chat_output_node_id,
                    "type": "genericNode",
                    "position": {"x": 400, "y": 100},
                    "data": {
                        "type": "ChatOutput",
                        "id": chat_output_node_id,
                        "node": {
                            "display_name": "Chat Output",
                            "base_classes": ["str"],
                            "template": {
                                "_type": "CustomComponent",
                                "is_ai": {
                                    "name": "is_ai",
                                    "display_name": "is_ai",
                                    "type": "bool",
                                    "value": True,
                                    "required": True,
                                    "show": True,
                                },
                                "message": {
                                    "name": "message",
                                    "display_name": "message",
                                    "type": "Text",
                                    "value": "",
                                    "required": False,
                                    "show": True,
                                },
                            },
                        },
                    },
                },
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }

    def _build_config_payload(self, *, label: str) -> dict[str, Any]:
        return {
            "name": self._mk_name(label),
            "description": "e2e config payload",
            "environment_variables": {},
        }

    async def _cleanup_resources(self) -> None:
        self._require_client()
        provider_id = self.provider_id
        print("Cleaning up created resources (best effort)...")
        print(
            "Cleanup plan: "
            f"{len(self.created_deployment_ids)} deployments, "
            f"{len(self.created_flow_ids)} flows, "
            f"{len(self.created_project_ids)} projects, "
            "1 provider account"
        )

        if provider_id:
            for deployment_id in sorted(self.created_deployment_ids):
                await self._best_effort_delete(
                    path=f"/api/v1/deployments/{deployment_id}",
                    resource_type="DEPLOYMENT",
                    resource_id=deployment_id,
                )
        elif self.created_deployment_ids:
            print("Skipping deployment cleanup because provider_id is unavailable.")
        for flow_id in sorted(self.created_flow_ids):
            await self._best_effort_delete(
                path=f"/api/v1/flows/{flow_id}",
                resource_type="FLOW",
                resource_id=flow_id,
            )
        for project_id in sorted(self.created_project_ids):
            await self._best_effort_delete(
                path=f"/api/v1/projects/{project_id}",
                resource_type="PROJECT",
                resource_id=project_id,
            )
        if provider_id:
            if self.provider_was_created:
                await self._best_effort_delete(
                    path=f"/api/v1/deployments/providers/{provider_id}",
                    resource_type="PROVIDER",
                    resource_id=provider_id,
                )
            else:
                print(f"Skipping provider cleanup because provider is reused: {provider_id}")

    async def _best_effort_delete(self, *, path: str, resource_type: str, resource_id: str) -> None:
        print(f"DELETING {resource_type}: ID={resource_id}")
        response = await self._request("DELETE", path)
        if response.status_code in {HTTP_OK, HTTP_ACCEPTED, HTTP_NO_CONTENT}:
            print(f"DELETED {resource_type}")
            return
        if response.status_code == HTTP_NOT_FOUND:
            print(f"{resource_type} ALREADY ABSENT: ID={resource_id}")
            return
        if response.status_code not in {HTTP_OK, HTTP_ACCEPTED, HTTP_NO_CONTENT, HTTP_NOT_FOUND}:
            print(
                f"[cleanup-warning] {resource_type} ID={resource_id} -> "
                f"{response.status_code}: {self._excerpt_response(response)}"
            )

    async def _request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
        self._require_client()
        return await self.client.request(
            method=method,
            url=path,
            headers=self.headers,
            json=json_body,
        )

    def _expect_status(self, response: httpx.Response, expected: set[int], label: str) -> None:
        if response.status_code not in expected:
            msg = (
                f"{label} failed; expected {sorted(expected)}, got {response.status_code}. "
                f"Response: {self._excerpt_response(response)}"
            )
            raise RuntimeError(msg)

    def _excerpt_response(self, response: httpx.Response, *, max_len: int = 400) -> str:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type.lower():
            try:
                payload = response.json()
                serialized = json.dumps(payload, ensure_ascii=True)
                return serialized[:max_len]
            except Exception as exc:  # noqa: BLE001
                print(f"[warning] failed to decode json response excerpt: {exc}")
        text = response.text or ""
        return text[:max_len]

    def _mk_name(self, prefix: str) -> str:
        raw = f"{prefix}_{self.run_suffix}_{uuid4().hex[:6]}"
        normalized = _INVALID_WXO_NAME_CHARS.sub("_", raw)
        if not normalized or not normalized[0].isalpha():
            normalized = f"n_{normalized}"
        return normalized

    def _require_provider_id(self) -> None:
        if not self.provider_id:
            msg = "Provider account has not been created yet."
            raise RuntimeError(msg)

    def _require_client(self) -> None:
        if self.client is None:
            msg = "HTTP client is not initialized."
            raise RuntimeError(msg)

    def _print_summary(self, results: list[ScenarioResult]) -> None:
        print("\nScenario Summary")
        print("-" * 90)
        for result in results:
            expected = ",".join(str(item) for item in sorted(result.expected_statuses))
            verdict = "PASS" if result.ok else "FAIL"
            print(f"{verdict:<5} | {result.name:<46} | expected={expected:<8} got={result.actual_status:<4}")
            if not result.ok:
                print(f"       response: {result.response_excerpt}")
        print("-" * 90)


async def _build_auth_headers(
    *,
    api_key: str | None,
) -> dict[str, str]:
    if not api_key:
        msg = "Provide LANGFLOW_API_KEY (or pass --api-key)."
        raise RuntimeError(msg)
    return {"x-api-key": api_key}


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        msg = f"Environment variable '{name}' is required."
        raise RuntimeError(msg)
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run E2E deployment-create scenario matrix for watsonx adapter.")
    parser.add_argument("--base-url", default=os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860"))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("E2E_TIMEOUT_SECONDS", "30")))
    parser.add_argument("--provider-key", default=os.getenv("WXO_PROVIDER_KEY", "watsonx-orchestrate"))
    parser.add_argument("--project-id", default=os.getenv("WXO_PROJECT_ID", "e2e-project"))
    parser.add_argument("--api-key", default=(os.getenv("LANGFLOW_API_KEY") or os.getenv("LANGFLOW_TOKEN")))
    parser.add_argument("--keep-resources", action="store_true")
    return parser.parse_args()


async def _main() -> int:
    # Load local .env values for script defaults.
    load_dotenv()
    args = _parse_args()
    provider_backend_url = _get_required_env("WXO_INSTANCE_URL")
    provider_api_key = _get_required_env("WXO_API_KEY")

    headers = await _build_auth_headers(
        api_key=args.api_key,
    )

    runner = DeploymentCreateE2E(
        base_url=args.base_url,
        headers=headers,
        timeout_seconds=args.timeout_seconds,
        provider_backend_url=provider_backend_url,
        provider_api_key=provider_api_key,
        provider_key=args.provider_key,
        project_id=args.project_id,
        keep_resources=args.keep_resources,
    )
    return await runner.run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
