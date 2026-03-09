"""Direct Watsonx adapter scenario runner.

Runs create scenario matrices against WatsonxOrchestrateDeploymentService
directly (no `/api/v1/deployments` calls).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MethodType, SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import HTTPException
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from langflow.services.adapters.deployment.watsonx_orchestrate import (
    WatsonxOrchestrateDeploymentService,
    WxOCredentials,
)
from lfx.services.adapters.deployment.exceptions import (
    DeploymentConflictError,
    DeploymentError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseFlowArtifact,
    ConfigItem,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentType,
    SnapshotItems,
)

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE_CONTENT = 422
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_NOT_FOUND = 404

_INVALID_WXO_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]")


class DummySettingsService:
    def __init__(self) -> None:
        self.settings = SimpleNamespace()


@dataclass(slots=True)
class ScenarioResult:
    name: str
    expected_statuses: set[int]
    actual_status: int
    ok: bool
    detail: str


class WatsonxAdapterDirectE2E:
    def __init__(
        self,
        *,
        provider_backend_url: str,
        provider_api_key: str,
        project_id: str,
        mode: str,
        keep_resources: bool,
    ) -> None:
        self.provider_backend_url = provider_backend_url
        self.provider_api_key = provider_api_key
        self.project_id = project_id
        self.mode = mode
        self.keep_resources = keep_resources
        self.run_suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]

        self.user_id = str(uuid4())
        self.db = object()
        self.provider_id = uuid4()
        self.service = WatsonxOrchestrateDeploymentService(DummySettingsService())

        import langflow.services.adapters.deployment.watsonx_orchestrate.client as _client_mod

        _client_mod.get_current_provider_id = lambda: self.provider_id  # type: ignore[assignment]

        _original_resolve = _client_mod.resolve_wxo_client_credentials

        async def _resolve_credentials(*, user_id, db, provider_id):  # noqa: ARG001
            return WxOCredentials(instance_url=self.provider_backend_url, api_key=self.provider_api_key)

        _client_mod.resolve_wxo_client_credentials = _resolve_credentials  # type: ignore[assignment]

        self.created_deployment_ids: set[str] = set()
        self.created_snapshot_ids: set[str] = set()
        self.created_config_ids: set[str] = set()

    async def run(self) -> int:
        print("Starting watsonx direct adapter runner...")
        print(f"mode={self.mode} project_id={self.project_id} keep_resources={self.keep_resources}")

        results: list[ScenarioResult] = []
        if self.mode in {"live", "both"}:
            results.extend(await self._run_live_scenarios())
        if self.mode in {"failpoint", "both"}:
            results.extend(await self._run_failpoint_scenarios())

        self._print_summary(results)
        if not self.keep_resources:
            await self._cleanup_resources()
        return 1 if any(not result.ok for result in results) else 0

    async def _run_live_scenarios(self) -> list[ScenarioResult]:
        duplicate_name = self._mk_name("dup_snapshot")
        scenarios = [
            {
                "name": "live_create_success",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_live_success")],
                    config=self._build_config_payload(label="cfg_live_success"),
                ),
            },
            {
                "name": "live_invalid_config_reference",
                "expected": {HTTP_BAD_REQUEST},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_live_invalid_ref")],
                    config_reference_id="cfg_ref_not_supported",
                ),
            },
            {
                "name": "live_duplicate_snapshot_names_conflict",
                "expected": {HTTP_CONFLICT},
                "payload": self._build_create_payload(
                    snapshots=[
                        self._build_flow_payload(label="snap_dup_a", name_override=duplicate_name),
                        self._build_flow_payload(label="snap_dup_b", name_override=duplicate_name),
                    ],
                    config=self._build_config_payload(label="cfg_live_dup"),
                ),
            },
        ]
        return await self._run_scenarios(scenarios)

    async def _run_failpoint_scenarios(self) -> list[ScenarioResult]:
        scenarios = [
            {
                "name": "fp_retry_create_config_then_success",
                "expected": {HTTP_CREATED},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_fp_retry")],
                    config=self._build_config_payload(label="cfg_fp_retry"),
                ),
                "inject": {
                    "create_config": {"fail_first_n": 2, "error_type": "runtime", "message": "fp_create_config_retry"}
                },
            },
            {
                "name": "fp_non_retryable_create_agent_conflict",
                "expected": {HTTP_CONFLICT},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_fp_conflict")],
                    config=self._build_config_payload(label="cfg_fp_conflict"),
                ),
                "inject": {
                    "create_agent": {
                        "fail_first_n": 1,
                        "error_type": "http",
                        "status_code": HTTP_CONFLICT,
                        "message": "fp_create_agent_conflict",
                    }
                },
            },
            {
                "name": "fp_create_agent_failure_triggers_rollback",
                "expected": {HTTP_INTERNAL_SERVER_ERROR},
                "detail_contains": "fp_create_agent_final",
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_fp_rollback")],
                    config=self._build_config_payload(label="cfg_fp_rollback"),
                ),
                "inject": {
                    "create_agent": {
                        "fail_first_n": 3,
                        "error_type": "runtime",
                        "message": "fp_create_agent_final",
                    },
                    "rollback_delete_config": {
                        "fail_first_n": 2,
                        "error_type": "runtime",
                        "message": "fp_rollback_delete_config",
                    },
                },
            },
        ]
        return await self._run_scenarios(scenarios)

    async def _run_scenarios(self, scenarios: list[dict[str, Any]]) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        for index, scenario in enumerate(scenarios, start=1):
            print(f"\n[{index}/{len(scenarios)}] {scenario['name']}")
            status_code, detail, created = await self._run_create(scenario["payload"], inject=scenario.get("inject"))
            detail_contains = str(scenario.get("detail_contains") or "").strip()
            detail_ok = not detail_contains or detail_contains in detail
            ok = status_code in scenario["expected"] and detail_ok

            if created:
                self.created_deployment_ids.add(created["deployment_id"])
                self.created_snapshot_ids.update(created["snapshot_ids"])
                if created["config_id"]:
                    self.created_config_ids.add(created["config_id"])

            results.append(
                ScenarioResult(
                    name=scenario["name"],
                    expected_statuses=set(scenario["expected"]),
                    actual_status=status_code,
                    ok=ok,
                    detail=detail[:600],
                )
            )
        return results

    async def _run_create(
        self,
        payload: DeploymentCreate,
        *,
        inject: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[int, str, dict[str, Any] | None]:
        originals: dict[str, Any] = {}
        try:
            if inject:
                self._apply_injections(inject, originals)

            result = await self.service.create(user_id=self.user_id, payload=payload, db=self.db)
        except DeploymentConflictError as exc:
            return HTTP_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return HTTP_UNPROCESSABLE_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return HTTP_BAD_REQUEST, exc.message, None
        except DeploymentError as exc:
            return HTTP_INTERNAL_SERVER_ERROR, exc.message, None
        except HTTPException as exc:
            return int(exc.status_code), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return HTTP_INTERNAL_SERVER_ERROR, str(exc), None
        else:
            created = {
                "deployment_id": str(result.id),
                "config_id": str(result.config_id) if result.config_id else None,
                "snapshot_ids": {str(item) for item in (result.snapshot_ids or [])},
            }
            return HTTP_CREATED, "created", created
        finally:
            for attr_name, original in originals.items():
                setattr(self.service, attr_name, original)

    def _apply_injections(self, inject: dict[str, dict[str, Any]], originals: dict[str, Any]) -> None:
        mapping = {
            "create_config": "_process_config",
            "create_snapshots": "_process_flow_snapshots",
            "create_agent": "_create_agent_deployment",
            "rollback_delete_agent": "_delete_agent_if_exists",
            "rollback_delete_tool": "_delete_tool_if_exists",
            "rollback_delete_config": "_delete_config_if_exists",
        }

        for stage, config in inject.items():
            method_name = mapping.get(stage)
            if method_name is None:
                continue
            original = getattr(self.service, method_name)
            originals[method_name] = original
            counter = {"value": 0}
            fail_first_n = int(config.get("fail_first_n", 0))
            error_type = str(config.get("error_type", "runtime")).strip().lower()
            message = str(config.get("message") or f"injected failure: {stage}")
            status_code = int(config.get("status_code", HTTP_INTERNAL_SERVER_ERROR))

            async def _wrapped(
                _self,
                *args,
                __orig=original,
                __ctr=counter,
                __n=fail_first_n,
                __type=error_type,
                __msg=message,
                __status=status_code,
                **kwargs,
            ):
                __ctr["value"] += 1
                if __ctr["value"] <= __n:
                    if __type == "http":
                        raise HTTPException(status_code=__status, detail=__msg)
                    raise RuntimeError(__msg)
                return await __orig(*args, **kwargs)

            setattr(self.service, method_name, MethodType(_wrapped, self.service))

    def _build_create_payload(
        self,
        *,
        snapshots: list[BaseFlowArtifact],
        config: DeploymentConfig | None = None,
        config_reference_id: str | None = None,
        resource_name_prefix: str | None = None,
    ) -> DeploymentCreate:
        provider_spec = None
        if resource_name_prefix is not None:
            provider_spec = {"global_resource_name_prefix": resource_name_prefix}
        spec = BaseDeploymentData(
            name=self._mk_name("dep_agent"),
            description="direct adapter scenario",
            type=DeploymentType.AGENT,
            provider_spec=provider_spec,
        )
        config_item = ConfigItem(reference_id=config_reference_id) if config_reference_id else None
        if config is not None:
            config_item = ConfigItem(raw_payload=config)
        return DeploymentCreate(spec=spec, snapshot=SnapshotItems(raw_payloads=snapshots), config=config_item)

    def _build_flow_payload(self, *, label: str, name_override: str | None = None) -> BaseFlowArtifact:
        return BaseFlowArtifact(
            id=UUID(str(uuid4())),
            name=name_override or self._mk_name(label),
            description="direct adapter flow payload",
            data=self._build_flow_data_payload(),
            tags=["e2e", "watsonx-direct-adapter"],
            provider_data={"project_id": self.project_id},
        )

    def _build_config_payload(self, *, label: str) -> DeploymentConfig:
        return DeploymentConfig(
            name=self._mk_name(label),
            description="direct adapter config payload",
            environment_variables={},
        )

    def _build_flow_data_payload(self) -> dict[str, Any]:
        chat_input_node_id = f"ChatInput-{uuid4().hex[:8]}"
        chat_output_node_id = f"ChatOutput-{uuid4().hex[:8]}"
        return {
            "nodes": [
                {
                    "id": chat_input_node_id,
                    "type": "genericNode",
                    "position": {"x": 100, "y": 100},
                    "data": {
                        "type": "ChatInput",
                        "id": chat_input_node_id,
                        "node": {"template": {"_type": "CustomComponent"}},
                    },
                },
                {
                    "id": chat_output_node_id,
                    "type": "genericNode",
                    "position": {"x": 400, "y": 100},
                    "data": {
                        "type": "ChatOutput",
                        "id": chat_output_node_id,
                        "node": {"template": {"_type": "CustomComponent"}},
                    },
                },
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }

    async def _cleanup_resources(self) -> None:
        clients = await self.service._get_provider_clients(user_id=self.user_id, db=self.db)  # noqa: SLF001
        for deployment_id in sorted(self.created_deployment_ids):
            with suppress(Exception):
                await self.service.delete(user_id=self.user_id, deployment_id=deployment_id, db=self.db)

        for snapshot_id in sorted(self.created_snapshot_ids):
            try:
                await asyncio.to_thread(clients.tool.delete, snapshot_id)
            except ClientAPIException as exc:
                if exc.response.status_code != HTTP_NOT_FOUND:
                    print(f"[cleanup-warning] snapshot {snapshot_id}: {exc}")

        for config_id in sorted(self.created_config_ids):
            try:
                await asyncio.to_thread(clients.connections.delete, config_id)
            except ClientAPIException as exc:
                if exc.response.status_code != HTTP_NOT_FOUND:
                    print(f"[cleanup-warning] config {config_id}: {exc}")

    def _mk_name(self, prefix: str) -> str:
        raw = f"{prefix}_{self.run_suffix}_{uuid4().hex[:6]}"
        normalized = _INVALID_WXO_NAME_CHARS.sub("_", raw)
        if not normalized or not normalized[0].isalpha():
            normalized = f"n_{normalized}"
        return normalized

    def _print_summary(self, results: list[ScenarioResult]) -> None:
        print("\nScenario Summary")
        print("-" * 90)
        for result in results:
            expected = ",".join(str(item) for item in sorted(result.expected_statuses))
            verdict = "PASS" if result.ok else "FAIL"
            print(f"{verdict:<5} | {result.name:<46} | expected={expected:<8} got={result.actual_status:<4}")
            if not result.ok:
                print(f"       detail: {result.detail}")
        print("-" * 90)


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        msg = f"Environment variable '{name}' is required."
        raise RuntimeError(msg)
    return value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run direct Watsonx adapter matrix (live + failpoints).")
    parser.add_argument("--project-id", default=os.getenv("WXO_PROJECT_ID", "e2e-project"))
    parser.add_argument("--mode", choices=["live", "failpoint", "both"], default=os.getenv("WXO_E2E_MODE", "both"))
    parser.add_argument("--keep-resources", action="store_true")
    return parser.parse_args()


async def _main() -> int:
    load_dotenv()
    args = _parse_args()
    runner = WatsonxAdapterDirectE2E(
        provider_backend_url=_get_required_env("WXO_INSTANCE_URL"),
        provider_api_key=_get_required_env("WXO_API_KEY"),
        project_id=args.project_id,
        mode=args.mode,
        keep_resources=args.keep_resources,
    )
    return await runner.run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
