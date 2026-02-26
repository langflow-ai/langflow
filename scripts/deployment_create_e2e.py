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
        self.created_deployment_ids: set[str] = set()
        self.created_snapshot_ids: set[str] = set()
        self.created_config_ids: set[str] = set()

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
            ref_config_id = await self._create_reference_config()
            ref_snapshot_id_primary = await self._create_reference_snapshot(label="snapshot-ref-primary")
            ref_snapshot_id_secondary = await self._create_reference_snapshot(label="snapshot-ref-secondary")

            snapshot_results = await self._run_snapshot_create_scenarios()

            scenario_results = await self._run_create_scenarios(
                reference_config_id=ref_config_id,
                reference_snapshot_ids=[ref_snapshot_id_primary, ref_snapshot_id_secondary],
            )
            all_results = [*snapshot_results, *scenario_results]
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
        payload = {
            "provider_key": self.provider_key,
            "backend_url": self.provider_backend_url,
            "api_key": self.provider_api_key,
        }
        response = await self._request("POST", "/api/v1/deployments/providers/", json_body=payload)
        self._expect_status(response, {201}, "create provider account")
        body = response.json()
        self.provider_id = str(body["id"])
        print(f"Provider account created: {self.provider_id}")

    async def _create_reference_config(self) -> str:
        self._require_provider_id()
        config_name = self._mk_name("cfg-ref")
        payload = {
            "name": config_name,
            "description": "reference config for deployment create scenarios",
            "environment_variables": {},
        }
        response = await self._request(
            "POST",
            f"/api/v1/deployments/configs?provider_id={self.provider_id}",
            json_body=payload,
        )
        self._expect_status(response, {201}, "create reference config")
        config_id = str(response.json()["id"])
        self.created_config_ids.add(config_id)
        print(f"Reference config created: {config_id}")
        return config_id

    async def _create_reference_snapshot(self, *, label: str) -> str:
        self._require_provider_id()
        flow_payload = self._build_flow_payload(label=label)
        payload = {
            "artifact_type": "flow",
            "raw_payloads": [flow_payload],
        }
        response = await self._request(
            "POST",
            f"/api/v1/deployments/snapshots?provider_id={self.provider_id}",
            json_body=payload,
        )
        self._expect_status(response, {201}, "create reference snapshot")
        snapshot_id = str(response.json()["ids"][0])
        self.created_snapshot_ids.add(snapshot_id)
        print(f"Reference snapshot created: {snapshot_id}")
        return snapshot_id

    async def _run_snapshot_create_scenarios(self) -> list[ScenarioResult]:
        self._require_provider_id()
        provider_id = self.provider_id

        scenarios = [
            {
                "name": "snapshot_create_single_raw_payload",
                "expected": {HTTP_CREATED},
                "payload": {
                    "artifact_type": "flow",
                    "raw_payloads": [self._build_flow_payload(label="snapshot-single")],
                },
            },
            {
                "name": "snapshot_create_multiple_raw_payloads",
                "expected": {HTTP_CREATED},
                "payload": {
                    "artifact_type": "flow",
                    "raw_payloads": [
                        self._build_flow_payload(label="snapshot-multi-a"),
                        self._build_flow_payload(label="snapshot-multi-b"),
                    ],
                },
            },
        ]

        results: list[ScenarioResult] = []
        for index, scenario in enumerate(scenarios, start=1):
            print(f"[snapshot {index}/{len(scenarios)}] Running {scenario['name']} ...")
            response = await self._request(
                "POST",
                f"/api/v1/deployments/snapshots?provider_id={provider_id}",
                json_body=scenario["payload"],
            )
            status_code = response.status_code
            ok = status_code in scenario["expected"]
            print(f"[{scenario['name']}] status={status_code}, expected={sorted(scenario['expected'])}")

            if status_code == HTTP_CREATED:
                try:
                    response_payload = response.json()
                    for snapshot_id in response_payload.get("ids") or []:
                        self.created_snapshot_ids.add(str(snapshot_id))
                    print(f"[{scenario['name']}] tracked_snapshot_ids={response_payload.get('ids') or []}")
                except Exception as exc:  # noqa: BLE001
                    print(f"[warning] snapshot create response parse failed: {exc}")

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

    async def _run_create_scenarios(
        self,
        *,
        reference_config_id: str,
        reference_snapshot_ids: list[str],
    ) -> list[ScenarioResult]:
        self._require_provider_id()
        provider_id = self.provider_id
        reference_snapshot_id = reference_snapshot_ids[0]
        reference_snapshot_id_2 = reference_snapshot_ids[1]

        scenarios = [
            {
                "name": "create_ref_snapshot_ref_config",
                "expected": {HTTP_BAD_REQUEST},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={"artifact_type": "flow", "reference_ids": [reference_snapshot_id]},
                    config={"reference_id": reference_config_id},
                ),
            },
            {
                "name": "create_ref_snapshot_raw_config",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={"artifact_type": "flow", "reference_ids": [reference_snapshot_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-create")},
                ),
            },
            {
                "name": "create_raw_snapshot_ref_config_rejected",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={"artifact_type": "flow", "raw_payloads": [self._build_flow_payload(label="flow-raw")]},
                    config={"reference_id": reference_config_id},
                ),
            },
            {
                "name": "create_raw_snapshot_raw_config_rejected",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={"artifact_type": "flow", "raw_payloads": [self._build_flow_payload(label="flow-raw2")]},
                    config={"raw_payload": self._build_config_payload(label="cfg-raw2")},
                ),
            },
            {
                "name": "create_no_snapshot_no_config",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                ),
            },
            {
                "name": "create_snapshot_with_two_reference_ids",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={
                        "artifact_type": "flow",
                        "reference_ids": [reference_snapshot_id, reference_snapshot_id_2],
                    },
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-two-refs")},
                ),
            },
            {
                "name": "create_snapshot_with_two_raw_payloads_rejected",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={
                        "artifact_type": "flow",
                        "raw_payloads": [
                            self._build_flow_payload(label="flow-a"),
                            self._build_flow_payload(label="flow-b"),
                        ],
                    },
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-two-raw")},
                ),
            },
            {
                "name": "create_snapshot_with_both_reference_and_raw",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={
                        "artifact_type": "flow",
                        "reference_ids": [reference_snapshot_id],
                        "raw_payloads": [self._build_flow_payload(label="flow-both")],
                    },
                    config={"reference_id": reference_config_id},
                ),
            },
            {
                "name": "create_config_with_both_reference_and_raw",
                "expected": {HTTP_UNPROCESSABLE_CONTENT},
                "payload": self._build_create_payload(
                    deployment_type="agent",
                    snapshot={"artifact_type": "flow", "reference_ids": [reference_snapshot_id]},
                    config={
                        "reference_id": reference_config_id,
                        "raw_payload": self._build_config_payload(label="cfg-both"),
                    },
                ),
            },
            {
                "name": "create_with_unsupported_mcp_type",
                "expected": {HTTP_BAD_REQUEST},
                "payload": self._build_create_payload(
                    deployment_type="mcp",
                    snapshot={"artifact_type": "flow", "reference_ids": [reference_snapshot_id]},
                    config={"raw_payload": self._build_config_payload(label="cfg-raw-for-mcp")},
                ),
            },
        ]

        results: list[ScenarioResult] = []
        for index, scenario in enumerate(scenarios, start=1):
            print(f"[{index}/{len(scenarios)}] Running {scenario['name']} ...")
            response = await self._request(
                "POST",
                f"/api/v1/deployments?provider_id={provider_id}",
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

                    provider_result = response_payload.get("provider_result") or {}
                    created_config_id = provider_result.get("created_config_id")
                    if created_config_id:
                        self.created_config_ids.add(str(created_config_id))

                    for snapshot_id in provider_result.get("created_snapshot_ids") or []:
                        self.created_snapshot_ids.add(str(snapshot_id))

                    print(
                        f"[{scenario['name']}] tracked deployment_id={deployment_id}, "
                        f"created_config_id={created_config_id}, "
                        f"created_snapshot_ids={provider_result.get('created_snapshot_ids') or []}"
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
        snapshot: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "spec": {
                "name": self._mk_name(f"dep-{deployment_type}"),
                "description": "e2e deployment create scenario",
                "type": deployment_type,
            }
        }
        if snapshot is not None:
            payload["snapshot"] = snapshot
        if config is not None:
            payload["config"] = config
        return payload

    def _build_flow_payload(self, *, label: str) -> dict[str, Any]:
        flow_id = str(uuid4())
        chat_input_node_id = f"ChatInput-{uuid4().hex[:8]}"
        chat_output_node_id = f"ChatOutput-{uuid4().hex[:8]}"
        return {
            "id": flow_id,
            "name": self._mk_name(label),
            "description": "e2e flow payload",
            "data": {
                # Watsonx tool export requires a ChatInput node in the flow graph.
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
            },
            "tags": ["e2e", "deployment-create"],
            "provider_data": {
                "project_id": self.project_id,
            },
        }

    def _build_config_payload(self, *, label: str) -> dict[str, Any]:
        return {
            "name": self._mk_name(label),
            "description": "e2e config payload",
            "environment_variables": {},
        }

    async def _cleanup_resources(self) -> None:
        self._require_client()
        self._require_provider_id()
        provider_id = self.provider_id
        print("Cleaning up created resources (best effort)...")
        print(
            "Cleanup plan: "
            f"{len(self.created_deployment_ids)} deployments, "
            f"{len(self.created_snapshot_ids)} snapshots, "
            f"{len(self.created_config_ids)} configs, "
            "1 provider account"
        )

        for deployment_id in sorted(self.created_deployment_ids):
            await self._best_effort_delete(
                path=f"/api/v1/deployments/{deployment_id}?provider_id={provider_id}",
                resource_type="DEPLOYMENT",
                resource_id=deployment_id,
            )
        for snapshot_id in sorted(self.created_snapshot_ids):
            await self._best_effort_delete(
                path=f"/api/v1/deployments/snapshots/{snapshot_id}?provider_id={provider_id}",
                resource_type="SNAPSHOT",
                resource_id=snapshot_id,
            )
        for config_id in sorted(self.created_config_ids):
            await self._best_effort_delete(
                path=f"/api/v1/deployments/configs/{config_id}?provider_id={provider_id}",
                resource_type="CONFIG",
                resource_id=config_id,
            )

        await self._best_effort_delete(
            path=f"/api/v1/deployments/providers/{provider_id}",
            resource_type="PROVIDER",
            resource_id=provider_id,
        )

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
