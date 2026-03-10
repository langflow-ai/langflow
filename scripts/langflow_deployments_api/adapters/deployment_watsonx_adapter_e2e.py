"""Direct Watsonx adapter scenario runner.

Runs scenario matrices against `WatsonxOrchestrateDeploymentService` directly
(no `/api/v1/deployments` calls).

Warning:
--------
This script performs live integration calls and creates real resources in
Watsonx Orchestrate (agents, snapshots/tools, and configs/connections).
By default, cleanup runs at the end of execution, but cleanup is best-effort:
if the process is interrupted or provider deletes fail, resources may remain.
Use `--keep-resources` only when you intentionally want to inspect leftovers.

Scenario catalog
----------------
Live create scenarios:
- `live_create_success`: creates config + snapshot + agent successfully (expects 201).
- `live_invalid_config_reference`: rejects config reference binding at create time (expects 400).
- `live_duplicate_snapshot_names_conflict`: rejects duplicate snapshot names in one request (expects 409).

Live lifecycle scenarios:
- `live_lifecycle_create_seed`: creates a seed deployment for lifecycle checks (expects 201).
- `live_list_contains_seed`: verifies list-by-id includes the seed deployment (expects 200).
- `live_get_seed`: fetches deployment details by id (expects 200).
- `live_update_seed_name_description`: updates deployment name/description (expects 200).
- `live_get_after_update_reflects_name`: confirms updated name is persisted (expects 200).
- `live_get_status_connected`: confirms status endpoint reports connected deployment (expects 200).
- `live_create_execution_success`: starts an execution run with valid message payload (expects 201).
- `live_get_execution_success`: fetches execution by returned execution id (expects 200).
- `live_delete_seed`: deletes seed deployment agent (expects 200).
- `live_get_after_delete_not_found`: confirms deleted deployment is no longer fetchable (expects 404).
- `live_status_after_delete_not_found_state`: confirms status reports not found state after delete (expects 200).

Live negative scenarios:
- `live_negative_create_seed`: creates a second seed deployment for negative-path checks (expects 201).
- `live_update_rejects_snapshot_patch`: rejects snapshot binding updates (unsupported operation, expects 400).
- `live_update_rejects_config_replacement`: rejects config replacement/unbind via patch (expects 400).
- `live_create_execution_rejects_empty_input`: rejects empty execution input payload (currently expects 500).
- `live_delete_missing_not_found`: delete on unknown deployment id returns not found (expects 404).
- `live_negative_delete_seed`: cleans up negative-path seed deployment (expects 200).

Failpoint scenarios:
- `fp_retry_create_config_then_success`: injects transient config-create failures; retries then succeeds (expects 201).
- `fp_non_retryable_create_agent_conflict`: injects non-retryable agent conflict (expects 409).
- `fp_create_agent_failure_triggers_rollback`: injects repeated agent-create failure and checks rollback (expects 500).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import types
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MethodType, SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import langflow.services.adapters.deployment.watsonx_orchestrate.core.retry as retry_module
import langflow.services.adapters.deployment.watsonx_orchestrate.service as service_module
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
    DeploymentNotFoundError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.adapters.deployment.schema import (
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    BaseFlowArtifact,
    ConfigDeploymentBindingUpdate,
    ConfigItem,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentListParams,
    DeploymentType,
    DeploymentUpdate,
    ExecutionCreate,
    SnapshotDeploymentBindingUpdate,
    SnapshotItems,
)

HTTP_OK = 200
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
        results = await self._run_scenarios(scenarios)
        results.extend(await self._run_live_lifecycle_scenarios())
        results.extend(await self._run_live_negative_scenarios())
        return results

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
                "detail_contains": "Please check server logs for details",
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
        originals: list[tuple[Any, str, Any]] = []
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
            for target, attr_name, original in originals:
                setattr(target, attr_name, original)

    async def _run_list(self, *, params: DeploymentListParams | None = None) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.list(user_id=self.user_id, db=self.db, params=params)
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_OK, "listed", result

    async def _run_get(self, deployment_id: str) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.get(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_OK, "fetched", result

    async def _run_update(self, deployment_id: str, payload: DeploymentUpdate) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.update(
                user_id=self.user_id,
                deployment_id=deployment_id,
                payload=payload,
                db=self.db,
            )
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_OK, "updated", result

    async def _run_status(self, deployment_id: str) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.get_status(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_OK, "status", result

    async def _run_create_execution(
        self,
        deployment_id: str,
        *,
        provider_data: dict[str, Any],
    ) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.create_execution(
                user_id=self.user_id,
                payload=ExecutionCreate(deployment_id=deployment_id, provider_data=provider_data),
                db=self.db,
            )
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_CREATED, "execution_created", result

    async def _run_get_execution(self, execution_id: str) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.get_execution(user_id=self.user_id, execution_id=execution_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_OK, "execution_fetched", result

    async def _run_delete(self, deployment_id: str) -> tuple[int, str, Any | None]:
        try:
            result = await self.service.delete(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return HTTP_NOT_FOUND, str(exc), None
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
            return HTTP_OK, "deleted", result

    def _build_result(
        self,
        *,
        name: str,
        expected: set[int],
        actual_status: int,
        detail: str,
        ok: bool,
    ) -> ScenarioResult:
        return ScenarioResult(
            name=name,
            expected_statuses=expected,
            actual_status=actual_status,
            ok=ok,
            detail=detail[:600],
        )

    async def _run_live_lifecycle_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        print("\n[life/1] live_lifecycle_create_seed")
        status_code, detail, created = await self._run_create(
            self._build_create_payload(
                snapshots=[self._build_flow_payload(label="snap_live_lifecycle_seed")],
                config=self._build_config_payload(label="cfg_live_lifecycle_seed"),
            )
        )
        create_ok = status_code == HTTP_CREATED and created is not None
        results.append(
            self._build_result(
                name="live_lifecycle_create_seed",
                expected={HTTP_CREATED},
                actual_status=status_code,
                detail=detail,
                ok=create_ok,
            )
        )
        if not create_ok or created is None:
            return results

        deployment_id = str(created["deployment_id"])
        self.created_deployment_ids.add(deployment_id)
        self.created_snapshot_ids.update(created["snapshot_ids"])
        if created["config_id"]:
            self.created_config_ids.add(str(created["config_id"]))

        print("[life/2] live_list_contains_seed")
        status_code, detail, list_result = await self._run_list(
            params=DeploymentListParams(deployment_ids=[deployment_id])
        )
        list_contains_seed = bool(
            list_result
            and any(str(deployment.id) == deployment_id for deployment in getattr(list_result, "deployments", []))
        )
        results.append(
            self._build_result(
                name="live_list_contains_seed",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_OK and list_contains_seed,
            )
        )

        print("[life/3] live_get_seed")
        status_code, detail, get_result = await self._run_get(deployment_id)
        got_seed = bool(get_result and str(get_result.id) == deployment_id)
        results.append(
            self._build_result(
                name="live_get_seed",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_OK and got_seed,
            )
        )

        updated_name = self._mk_name("dep_agent_updated")
        print("[life/4] live_update_seed_name_description")
        status_code, detail, _ = await self._run_update(
            deployment_id,
            DeploymentUpdate(
                spec=BaseDeploymentDataUpdate(
                    name=updated_name,
                    description="updated by direct adapter e2e",
                )
            ),
        )
        results.append(
            self._build_result(
                name="live_update_seed_name_description",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_OK,
            )
        )

        print("[life/5] live_get_after_update_reflects_name")
        status_code, detail, get_after_update = await self._run_get(deployment_id)
        updated_name_ok = bool(get_after_update and getattr(get_after_update, "name", None) == updated_name)
        results.append(
            self._build_result(
                name="live_get_after_update_reflects_name",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_OK and updated_name_ok,
            )
        )

        print("[life/6] live_get_status_connected")
        status_code, detail, status_result = await self._run_status(deployment_id)
        connected_ok = bool(status_result and getattr(status_result, "provider_data", {}).get("status") == "connected")
        results.append(
            self._build_result(
                name="live_get_status_connected",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_OK and connected_ok,
            )
        )

        print("[life/7] live_create_execution_success")
        status_code, detail, execution_create_result = await self._run_create_execution(
            deployment_id,
            provider_data={"message": {"role": "user", "content": "ping from direct adapter e2e"}},
        )
        has_execution_id = bool(execution_create_result and getattr(execution_create_result, "execution_id", None))
        results.append(
            self._build_result(
                name="live_create_execution_success",
                expected={HTTP_CREATED},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_CREATED and has_execution_id,
            )
        )

        execution_id_value = (
            execution_create_result.execution_id
            if execution_create_result and getattr(execution_create_result, "execution_id", None)
            else None
        )
        execution_id = str(execution_id_value) if execution_id_value else None

        if execution_id:
            print("[life/8] live_get_execution_success")
            status_code, detail, execution_status_result = await self._run_get_execution(execution_id)
            execution_ok = bool(
                execution_status_result and str(getattr(execution_status_result, "execution_id", "")) == execution_id
            )
            results.append(
                self._build_result(
                    name="live_get_execution_success",
                    expected={HTTP_OK},
                    actual_status=status_code,
                    detail=detail,
                    ok=status_code == HTTP_OK and execution_ok,
                )
            )

        print("[life/9] live_delete_seed")
        status_code, detail, _ = await self._run_delete(deployment_id)
        delete_ok = status_code == HTTP_OK
        if delete_ok:
            self.created_deployment_ids.discard(deployment_id)
        results.append(
            self._build_result(
                name="live_delete_seed",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=delete_ok,
            )
        )

        print("[life/10] live_get_after_delete_not_found")
        status_code, detail, _ = await self._run_get(deployment_id)
        results.append(
            self._build_result(
                name="live_get_after_delete_not_found",
                expected={HTTP_NOT_FOUND},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_NOT_FOUND,
            )
        )

        print("[life/11] live_status_after_delete_not_found_state")
        status_code, detail, status_after_delete = await self._run_status(deployment_id)
        status_not_found_ok = bool(
            status_after_delete and getattr(status_after_delete, "provider_data", {}).get("status") == "not found"
        )
        results.append(
            self._build_result(
                name="live_status_after_delete_not_found_state",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_OK and status_not_found_ok,
            )
        )

        return results

    async def _run_live_negative_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        print("\n[neg/1] live_negative_create_seed")
        status_code, detail, created = await self._run_create(
            self._build_create_payload(
                snapshots=[self._build_flow_payload(label="snap_live_negative_seed")],
                config=self._build_config_payload(label="cfg_live_negative_seed"),
            )
        )
        create_ok = status_code == HTTP_CREATED and created is not None
        results.append(
            self._build_result(
                name="live_negative_create_seed",
                expected={HTTP_CREATED},
                actual_status=status_code,
                detail=detail,
                ok=create_ok,
            )
        )
        if not create_ok or created is None:
            return results

        deployment_id = str(created["deployment_id"])
        self.created_deployment_ids.add(deployment_id)
        self.created_snapshot_ids.update(created["snapshot_ids"])
        if created["config_id"]:
            self.created_config_ids.add(str(created["config_id"]))

        print("[neg/2] live_update_rejects_snapshot_patch")
        status_code, detail, _ = await self._run_update(
            deployment_id,
            DeploymentUpdate(snapshot=SnapshotDeploymentBindingUpdate(add=[str(uuid4())])),
        )
        results.append(
            self._build_result(
                name="live_update_rejects_snapshot_patch",
                expected={HTTP_BAD_REQUEST},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_BAD_REQUEST,
            )
        )

        print("[neg/3] live_update_rejects_config_replacement")
        status_code, detail, _ = await self._run_update(
            deployment_id,
            DeploymentUpdate(config=ConfigDeploymentBindingUpdate(config_id=str(uuid4()))),
        )
        results.append(
            self._build_result(
                name="live_update_rejects_config_replacement",
                expected={HTTP_BAD_REQUEST},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_BAD_REQUEST,
            )
        )

        print("[neg/4] live_create_execution_rejects_empty_input")
        status_code, detail, _ = await self._run_create_execution(
            deployment_id,
            provider_data={"input": "   "},
        )
        results.append(
            self._build_result(
                name="live_create_execution_rejects_empty_input",
                expected={HTTP_UNPROCESSABLE_CONTENT},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_UNPROCESSABLE_CONTENT,
            )
        )

        print("[neg/5] live_delete_missing_not_found")
        status_code, detail, _ = await self._run_delete(str(uuid4()))
        results.append(
            self._build_result(
                name="live_delete_missing_not_found",
                expected={HTTP_NOT_FOUND},
                actual_status=status_code,
                detail=detail,
                ok=status_code == HTTP_NOT_FOUND,
            )
        )

        print("[neg/6] live_negative_delete_seed")
        status_code, detail, _ = await self._run_delete(deployment_id)
        delete_ok = status_code == HTTP_OK
        if delete_ok:
            self.created_deployment_ids.discard(deployment_id)
        results.append(
            self._build_result(
                name="live_negative_delete_seed",
                expected={HTTP_OK},
                actual_status=status_code,
                detail=detail,
                ok=delete_ok,
            )
        )

        return results

    def _apply_injections(self, inject: dict[str, dict[str, Any]], originals: list[tuple[Any, str, Any]]) -> None:
        mapping = {
            "create_config": (service_module, "process_config"),
            "create_snapshots": (service_module, "process_raw_flows_with_app_id"),
            "create_agent": (self.service, "_create_agent_deployment"),
            "rollback_delete_agent": (retry_module, "delete_agent_if_exists"),
            "rollback_delete_tool": (retry_module, "delete_tool_if_exists"),
            "rollback_delete_config": (retry_module, "delete_config_if_exists"),
        }

        for stage, config in inject.items():
            target_and_method = mapping.get(stage)
            if target_and_method is None:
                continue
            target, method_name = target_and_method
            original = getattr(target, method_name)
            originals.append((target, method_name, original))
            counter = {"value": 0}
            fail_first_n = int(config.get("fail_first_n", 0))
            error_type = str(config.get("error_type", "runtime")).strip().lower()
            message = str(config.get("message") or f"injected failure: {stage}")
            status_code = int(config.get("status_code", HTTP_INTERNAL_SERVER_ERROR))

            if isinstance(target, types.ModuleType):

                async def _wrapped_module(
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

                setattr(target, method_name, _wrapped_module)
                continue

            async def _wrapped_method(
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

            setattr(target, method_name, MethodType(_wrapped_method, target))

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
        print("\nCleanup Resources")
        print("-" * 90)
        print(
            f"cleanup targets: deployments={len(self.created_deployment_ids)} "
            f"snapshots={len(self.created_snapshot_ids)} "
            f"configs={len(self.created_config_ids)}"
        )

        deleted_deployments = 0
        deleted_snapshots = 0
        deleted_configs = 0

        for deployment_id in sorted(self.created_deployment_ids):
            print(f"[cleanup] deleting deployment {deployment_id}...")
            with suppress(Exception):
                await self.service.delete(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
                deleted_deployments += 1
                print(f"[cleanup] deleted deployment {deployment_id}")

        for snapshot_id in sorted(self.created_snapshot_ids):
            print(f"[cleanup] deleting snapshot {snapshot_id}...")
            try:
                await asyncio.to_thread(clients.tool.delete, snapshot_id)
                deleted_snapshots += 1
                print(f"[cleanup] deleted snapshot {snapshot_id}")
            except ClientAPIException as exc:
                if exc.response.status_code != HTTP_NOT_FOUND:
                    print(f"[cleanup-warning] snapshot {snapshot_id}: {exc}")
                else:
                    print(f"[cleanup] snapshot {snapshot_id} already deleted (404)")

        for config_id in sorted(self.created_config_ids):
            print(f"[cleanup] deleting config {config_id}...")
            try:
                await asyncio.to_thread(clients.connections.delete, config_id)
                deleted_configs += 1
                print(f"[cleanup] deleted config {config_id}")
            except ClientAPIException as exc:
                if exc.response.status_code != HTTP_NOT_FOUND:
                    print(f"[cleanup-warning] config {config_id}: {exc}")
                else:
                    print(f"[cleanup] config {config_id} already deleted (404)")

        print(
            f"cleanup completed: deployments_deleted={deleted_deployments} "
            f"snapshots_deleted={deleted_snapshots} "
            f"configs_deleted={deleted_configs}"
        )
        print("-" * 90)

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
