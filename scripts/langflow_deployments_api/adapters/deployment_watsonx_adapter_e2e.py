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
- `live_create_success`: creates config + snapshot + agent successfully (expects Success).
- `live_invalid_config_reference`: rejects config reference binding at create time
  (expects InvalidDeploymentOperationError).
- `live_duplicate_snapshot_names_conflict`: duplicate snapshot names collide in wxO (expects DeploymentConflictError).

Live lifecycle scenarios:
- `live_lifecycle_create_seed`: creates a seed deployment for lifecycle checks (expects Success).
- `live_list_contains_seed`: verifies list-by-id includes the seed deployment (expects Success).
- `live_get_seed`: fetches deployment details by id (expects Success).
- `live_update_seed_name_description`: updates deployment name/description (expects Success).
- `live_get_after_update_reflects_name`: confirms updated name is persisted (expects Success).
- `live_get_status_connected`: confirms status endpoint reports connected deployment (expects Success).
- `live_create_execution_success`: starts an execution run with valid message payload (expects Success).
- `live_get_execution_success`: fetches execution by returned execution id (expects Success).
- `live_delete_seed`: deletes seed deployment agent (expects Success).
- `live_get_after_delete_not_found`: confirms deleted deployment is no longer fetchable
  (expects DeploymentNotFoundError).
- `live_status_after_delete_not_found_state`: confirms status on deleted deployment returns not found
  (expects DeploymentNotFoundError).

Live negative scenarios:
- `live_negative_create_seed`: creates a second seed deployment for negative-path checks (expects Success).
- `live_create_execution_rejects_empty_input`: rejects empty execution input payload (expects InvalidContentError).
- `live_delete_missing_not_found`: delete on unknown deployment id returns not found (expects DeploymentNotFoundError).
- `live_negative_delete_seed`: cleans up negative-path seed deployment (expects Success).

Live update-matrix scenarios:
- Contract note: in provider_data operations, `app_ids` are unprefixed operation ids.
  `resource_name_prefix` is applied only when raw resources are created in the provider.
- `upd_spec_only_name_desc`: updates deployment metadata only (expects Success).
- `upd_snapshot_remove_only_no_config`: removes an attached snapshot via provider_data operation
  (expects Success).
- `upd_config_only_existing_tools_with_config_id`: rebinds existing attached snapshots
  to an explicit existing app id via provider_data (expects Success).
- `upd_snapshot_add_ids_with_config_id`: binds existing snapshot ids using provider_data
  operations (expects Success).
- `upd_snapshot_add_raw_with_config_id`: creates and binds raw snapshot payloads using
  provider_data tools/connections/operations (expects Success).
- `upd_mixed_add_remove_raw_with_config`: mixed add/remove/raw snapshot update with provider_data
  operations (expects Success).
- `upd_reject_bind_with_undeclared_app_id`: rejects bind operation with undeclared app id
  in provider_data (expects InvalidContentError).
- `upd_reject_raw_bind_with_undeclared_app_id`: rejects raw-tool bind operation with undeclared app id
  in provider_data (expects InvalidContentError).
- `upd_reject_unbind_with_undeclared_app_id`: rejects unbind operation with undeclared app id
  in provider_data (expects InvalidContentError).
- `upd_reject_unbind_unknown_tool_id`: rejects unbind on unknown tool id
  in provider_data (expects InvalidContentError).
- `upd_missing_add_id_fails`: rejects unknown bind.tool.reference_id in provider_data (expects InvalidContentError).
- `upd_config_raw_payload_conflict`: detects conflict when creating duplicate provider_data
  raw connection app id (expects DeploymentConflictError).
- `upd_not_found_deployment`: update unknown deployment id returns not found (expects DeploymentNotFoundError).

Failpoint scenarios:
- `fp_retry_create_config_then_success`: injects transient config-create failures; retries
  then succeeds (expects Success).
- `fp_non_retryable_create_agent_conflict`: injects non-retryable agent conflict (expects DeploymentConflictError).
- `fp_create_agent_failure_triggers_rollback`: injects repeated agent-create failure and
  checks rollback (expects DeploymentError).
- `fp_update_bindings_failure_triggers_rollback`: injects update-stage binding failure
  and validates rollback path (expects DeploymentError).
- `fp_update_bindings_failure_with_rollback_failure`: injects update failure + rollback
  failure and expects terminal error (expects DeploymentError).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import textwrap
import types
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MethodType, SimpleNamespace
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import langflow.services.adapters.deployment.watsonx_orchestrate.core.retry as retry_module
import langflow.services.adapters.deployment.watsonx_orchestrate.service as service_module
import langflow.services.adapters.deployment.watsonx_orchestrate.update_helpers as update_helpers_module
from dotenv import load_dotenv
from fastapi import HTTPException
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from langflow.services.adapters.deployment.context import (
    DeploymentAdapterContext,
    DeploymentProviderIDContext,
)
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
    ConfigItem,
    ConfigListParams,
    DeploymentConfig,
    DeploymentCreate,
    DeploymentListParams,
    DeploymentType,
    DeploymentUpdate,
    ExecutionCreate,
    SnapshotItems,
    SnapshotListParams,
)

OUTCOME_SUCCESS = "Success"
OUTCOME_INVALID_OPERATION = "InvalidDeploymentOperationError"
OUTCOME_CONFLICT = "DeploymentConflictError"
OUTCOME_INVALID_CONTENT = "InvalidContentError"
OUTCOME_FAILURE = "DeploymentError"
OUTCOME_NOT_FOUND = "DeploymentNotFoundError"
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_CONFLICT = 409
MIN_MIXED_SNAPSHOT_IDS = 2
DEFAULT_CONCURRENCY_ITERATIONS = 1

_INVALID_WXO_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]")

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class DummySettingsService:
    def __init__(self) -> None:
        self.settings = SimpleNamespace()


@dataclass(slots=True)
class ScenarioResult:
    name: str
    expected_outcomes: set[str]
    actual_outcome: str
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

        self._client_mod = _client_mod

        deployment_context = DeploymentAdapterContext(provider_id=self.provider_id)
        self._deployment_context_token = DeploymentProviderIDContext.set_current(deployment_context)

        self._original_resolve_wxo_client_credentials = _client_mod.resolve_wxo_client_credentials

        async def _resolve_credentials(*, user_id, db, provider_id):  # noqa: ARG001
            authenticator = _client_mod.get_authenticator(
                instance_url=self.provider_backend_url,
                api_key=self.provider_api_key,
            )
            return WxOCredentials(instance_url=self.provider_backend_url, authenticator=authenticator)

        _client_mod.resolve_wxo_client_credentials = _resolve_credentials  # type: ignore[assignment]

        self.created_deployment_ids: set[str] = set()
        self.created_snapshot_ids: set[str] = set()
        self.created_config_ids: set[str] = set()

    async def run(self) -> int:
        print("Starting watsonx direct adapter runner...")
        print(f"mode={self.mode} project_id={self.project_id} keep_resources={self.keep_resources}")
        try:
            results: list[ScenarioResult] = []
            if self.mode in {"live", "both"}:
                results.extend(await self._run_live_scenarios())
            if self.mode in {"failpoint", "both"}:
                results.extend(await self._run_failpoint_scenarios())

            self._print_summary(results)
            if not self.keep_resources:
                await self._cleanup_resources()
            return 1 if any(not result.ok for result in results) else 0
        finally:
            self._client_mod.resolve_wxo_client_credentials = self._original_resolve_wxo_client_credentials
            self._client_mod.clear_provider_clients_request_context()
            DeploymentProviderIDContext.reset_current(self._deployment_context_token)

    async def _run_live_scenarios(self) -> list[ScenarioResult]:
        duplicate_name = self._mk_name("dup_snapshot")
        scenarios = [
            {
                "name": "live_create_success",
                "expected": {OUTCOME_SUCCESS},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_live_success")],
                    config=self._build_config_payload(label="cfg_live_success"),
                ),
            },
            {
                "name": "live_invalid_config_reference",
                "expected": {OUTCOME_INVALID_OPERATION},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_live_invalid_ref")],
                    config_reference_id="cfg_ref_not_supported",
                ),
            },
            {
                "name": "live_duplicate_snapshot_names_conflict",
                "expected": {OUTCOME_CONFLICT},
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
        results.extend(await self._run_live_update_matrix_scenarios())
        results.extend(await self._run_live_concurrency_scenarios())
        results.extend(await self._run_live_negative_scenarios())
        return results

    async def _run_failpoint_scenarios(self) -> list[ScenarioResult]:
        scenarios = [
            {
                "name": "fp_retry_create_config_then_success",
                "expected": {OUTCOME_SUCCESS},
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
                "expected": {OUTCOME_CONFLICT},
                "payload": self._build_create_payload(
                    snapshots=[self._build_flow_payload(label="snap_fp_conflict")],
                    config=self._build_config_payload(label="cfg_fp_conflict"),
                ),
                "inject": {
                    "create_agent": {
                        "fail_first_n": 1,
                        "error_type": "domain_conflict",
                        "message": "fp_create_agent_conflict",
                    }
                },
            },
            {
                "name": "fp_create_agent_failure_triggers_rollback",
                "expected": {OUTCOME_FAILURE},
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
        results = await self._run_scenarios(scenarios)
        results.extend(await self._run_update_failpoint_scenarios())
        return results

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
                    expected_outcomes=set(scenario["expected"]),
                    actual_outcome=status_code,
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
    ) -> tuple[str, str, dict[str, Any] | None]:
        originals: list[tuple[Any, str, Any]] = []
        try:
            if inject:
                self._apply_injections(inject, originals)

            result = await self.service.create(user_id=self.user_id, payload=payload, db=self.db)
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            created = {
                "deployment_id": str(result.id),
                "config_id": str(result.config_id) if result.config_id else None,
                "snapshot_ids": {str(item) for item in (result.snapshot_ids or [])},
            }
            return OUTCOME_SUCCESS, "created", created
        finally:
            for target, attr_name, original in originals:
                setattr(target, attr_name, original)

    async def _run_list(self, *, params: DeploymentListParams | None = None) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.list(user_id=self.user_id, db=self.db, params=params)
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "listed", result

    async def _run_get(self, deployment_id: str) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.get(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "fetched", result

    async def _run_update(
        self,
        deployment_id: str,
        payload: DeploymentUpdate,
        *,
        inject: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[str, str, Any | None]:
        originals: list[tuple[Any, str, Any]] = []
        try:
            if inject:
                self._apply_injections(inject, originals)
            result = await self.service.update(
                user_id=self.user_id,
                deployment_id=deployment_id,
                payload=payload,
                db=self.db,
            )
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "updated", result
        finally:
            for target, attr_name, original in originals:
                setattr(target, attr_name, original)

    async def _run_list_snapshots(self, deployment_id: str) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.list_snapshots(
                user_id=self.user_id,
                params=SnapshotListParams(deployment_ids=[deployment_id]),
                db=self.db,
            )
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "snapshots_listed", result

    async def _run_list_configs(self, deployment_id: str) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.list_configs(
                user_id=self.user_id,
                params=ConfigListParams(deployment_ids=[deployment_id]),
                db=self.db,
            )
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "configs_listed", result

    async def _run_status(self, deployment_id: str) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.get_status(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "status", result

    async def _run_create_execution(
        self,
        deployment_id: str,
        *,
        provider_data: dict[str, Any],
    ) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.create_execution(
                user_id=self.user_id,
                payload=ExecutionCreate(deployment_id=deployment_id, provider_data=provider_data),
                db=self.db,
            )
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "execution_created", result

    async def _run_get_execution(self, execution_id: str) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.get_execution(user_id=self.user_id, execution_id=execution_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "execution_fetched", result

    async def _run_delete(self, deployment_id: str) -> tuple[str, str, Any | None]:
        try:
            result = await self.service.delete(user_id=self.user_id, deployment_id=deployment_id, db=self.db)
        except DeploymentNotFoundError as exc:
            return OUTCOME_NOT_FOUND, str(exc), None
        except DeploymentConflictError as exc:
            return OUTCOME_CONFLICT, exc.message, None
        except InvalidContentError as exc:
            return OUTCOME_INVALID_CONTENT, exc.message, None
        except (InvalidDeploymentOperationError, InvalidDeploymentTypeError) as exc:
            return OUTCOME_INVALID_OPERATION, exc.message, None
        except DeploymentError as exc:
            return OUTCOME_FAILURE, exc.message, None
        except HTTPException as exc:
            return self._outcome_from_http_exception(exc), str(exc.detail), None
        except Exception as exc:  # noqa: BLE001
            return OUTCOME_FAILURE, str(exc), None
        else:
            return OUTCOME_SUCCESS, "deleted", result

    def _build_result(
        self,
        *,
        name: str,
        expected: set[str],
        actual_outcome: str,
        detail: str,
        ok: bool,
    ) -> ScenarioResult:
        return ScenarioResult(
            name=name,
            expected_outcomes=expected,
            actual_outcome=actual_outcome,
            ok=ok,
            detail=detail[:600],
        )

    def _outcome_from_http_exception(self, exc: HTTPException) -> str:
        status_code = int(exc.status_code)
        if status_code == HTTP_STATUS_NOT_FOUND:
            return OUTCOME_NOT_FOUND
        if status_code == HTTP_STATUS_CONFLICT:
            return OUTCOME_CONFLICT
        if status_code in {400, 405}:
            return OUTCOME_INVALID_OPERATION
        if status_code in {413, 415, 422}:
            return OUTCOME_INVALID_CONTENT
        return OUTCOME_FAILURE

    async def _run_live_lifecycle_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        print("\n[life/1] live_lifecycle_create_seed")
        status_code, detail, created = await self._run_create(
            self._build_create_payload(
                snapshots=[self._build_flow_payload(label="snap_live_lifecycle_seed")],
                config=self._build_config_payload(label="cfg_live_lifecycle_seed"),
            )
        )
        create_ok = status_code == OUTCOME_SUCCESS and created is not None
        results.append(
            self._build_result(
                name="live_lifecycle_create_seed",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
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
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_SUCCESS and list_contains_seed,
            )
        )

        print("[life/3] live_get_seed")
        status_code, detail, get_result = await self._run_get(deployment_id)
        got_seed = bool(get_result and str(get_result.id) == deployment_id)
        results.append(
            self._build_result(
                name="live_get_seed",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_SUCCESS and got_seed,
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
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_SUCCESS,
            )
        )

        print("[life/5] live_get_after_update_reflects_name")
        status_code, detail, get_after_update = await self._run_get(deployment_id)
        updated_name_ok = bool(get_after_update and getattr(get_after_update, "name", None) == updated_name)
        results.append(
            self._build_result(
                name="live_get_after_update_reflects_name",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_SUCCESS and updated_name_ok,
            )
        )

        print("[life/6] live_get_status_connected")
        status_code, detail, status_result = await self._run_status(deployment_id)
        connected_ok = bool(status_result and getattr(status_result, "provider_data", {}).get("status") == "connected")
        results.append(
            self._build_result(
                name="live_get_status_connected",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_SUCCESS and connected_ok,
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
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_SUCCESS and has_execution_id,
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
                    expected={OUTCOME_SUCCESS},
                    actual_outcome=status_code,
                    detail=detail,
                    ok=status_code == OUTCOME_SUCCESS and execution_ok,
                )
            )

        print("[life/9] live_delete_seed")
        status_code, detail, _ = await self._run_delete(deployment_id)
        delete_ok = status_code == OUTCOME_SUCCESS
        if delete_ok:
            self.created_deployment_ids.discard(deployment_id)
        results.append(
            self._build_result(
                name="live_delete_seed",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=delete_ok,
            )
        )

        print("[life/10] live_get_after_delete_not_found")
        status_code, detail, _ = await self._run_get(deployment_id)
        results.append(
            self._build_result(
                name="live_get_after_delete_not_found",
                expected={OUTCOME_NOT_FOUND},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_NOT_FOUND,
            )
        )

        print("[life/11] live_status_after_delete_not_found_state")
        status_code, detail, _ = await self._run_status(deployment_id)
        results.append(
            self._build_result(
                name="live_status_after_delete_not_found_state",
                expected={OUTCOME_NOT_FOUND},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_NOT_FOUND,
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
        create_ok = status_code == OUTCOME_SUCCESS and created is not None
        results.append(
            self._build_result(
                name="live_negative_create_seed",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
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

        print("[neg/2] live_create_execution_rejects_empty_input")
        status_code, detail, _ = await self._run_create_execution(
            deployment_id,
            provider_data={"input": "   "},
        )
        results.append(
            self._build_result(
                name="live_create_execution_rejects_empty_input",
                expected={OUTCOME_INVALID_CONTENT},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_INVALID_CONTENT,
            )
        )

        print("[neg/3] live_delete_missing_not_found")
        status_code, detail, _ = await self._run_delete(str(uuid4()))
        results.append(
            self._build_result(
                name="live_delete_missing_not_found",
                expected={OUTCOME_NOT_FOUND},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_NOT_FOUND,
            )
        )

        print("[neg/4] live_negative_delete_seed")
        status_code, detail, _ = await self._run_delete(deployment_id)
        delete_ok = status_code == OUTCOME_SUCCESS
        if delete_ok:
            self.created_deployment_ids.discard(deployment_id)
        results.append(
            self._build_result(
                name="live_negative_delete_seed",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=delete_ok,
            )
        )

        return results

    def _extract_snapshot_ids(self, snapshot_result: Any) -> set[str]:
        snapshots = getattr(snapshot_result, "snapshots", []) if snapshot_result else []
        return {str(snapshot.id) for snapshot in snapshots if snapshot and snapshot.id}

    async def _create_update_seed(
        self,
        *,
        label: str,
        snapshot_count: int = 2,
    ) -> tuple[str, str | None, set[str], str]:
        snapshots = [self._build_flow_payload(label=f"{label}_snap_{idx}") for idx in range(snapshot_count)]
        status_code, detail, created = await self._run_create(
            self._build_create_payload(
                snapshots=snapshots,
                config=self._build_config_payload(label=f"{label}_cfg"),
            )
        )
        if status_code != OUTCOME_SUCCESS or not created:
            msg = f"Failed to create seed deployment '{label}': status={status_code}, detail={detail}"
            raise RuntimeError(msg)
        deployment_id = str(created["deployment_id"])
        self.created_deployment_ids.add(deployment_id)
        self.created_snapshot_ids.update(created["snapshot_ids"])
        if created["config_id"]:
            self.created_config_ids.add(str(created["config_id"]))
        return deployment_id, created["config_id"], set(created["snapshot_ids"]), detail

    async def _run_live_update_matrix_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        print("\n[upd] building update matrix seed resources")
        (
            primary_deployment_id,
            _primary_config_id,
            primary_snapshot_ids,
            _,
        ) = await self._create_update_seed(label="upd_primary", snapshot_count=2)
        donor_deployment_id, donor_config_id, donor_snapshot_ids, _ = await self._create_update_seed(
            label="upd_donor",
            snapshot_count=1,
        )
        mixed_donor_deployment_id, _mixed_donor_cfg, mixed_donor_snapshot_ids, _ = await self._create_update_seed(
            label="upd_mixed_donor",
            snapshot_count=1,
        )

        donor_snapshot_id = next(iter(donor_snapshot_ids), "")
        mixed_donor_snapshot_id = next(iter(mixed_donor_snapshot_ids), "")
        removable_snapshot_id = next(iter(primary_snapshot_ids), "")
        retained_snapshot_ids = set(primary_snapshot_ids)
        retained_snapshot_ids.discard(removable_snapshot_id)
        if not donor_config_id:
            results.append(
                self._build_result(
                    name="upd_seed_missing_donor_config",
                    expected={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="donor deployment config id is missing",
                    ok=False,
                )
            )
            return results

        print("[upd/1] upd_spec_only_name_desc")
        updated_name = self._mk_name("dep_upd_spec_only")
        status_code, detail, update_result = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                spec=BaseDeploymentDataUpdate(
                    name=updated_name,
                    description="updated by update matrix spec-only",
                )
            ),
        )
        get_status, _get_detail, get_after_update = await self._run_get(primary_deployment_id)
        spec_ok = bool(get_after_update and getattr(get_after_update, "name", None) == updated_name)
        spec_snapshot_ids_ok = bool(update_result and not getattr(update_result, "snapshot_ids", []))
        results.append(
            self._build_result(
                name="upd_spec_only_name_desc",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=(
                    status_code == OUTCOME_SUCCESS
                    and get_status == OUTCOME_SUCCESS
                    and spec_ok
                    and spec_snapshot_ids_ok
                ),
            )
        )

        print("[upd/2] upd_snapshot_remove_only_no_config")
        status_code, detail, remove_result = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"existing_ids": [removable_snapshot_id]},
                    "operations": [{"op": "remove_tool", "tool_id": removable_snapshot_id}],
                }
            ),
        )
        list_status, _list_detail, list_after_remove = await self._run_list_snapshots(primary_deployment_id)
        attached_after_remove = self._extract_snapshot_ids(list_after_remove)
        remove_snapshot_ids_ok = bool(remove_result and not getattr(remove_result, "snapshot_ids", []))
        results.append(
            self._build_result(
                name="upd_snapshot_remove_only_no_config",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=(
                    status_code == OUTCOME_SUCCESS
                    and list_status == OUTCOME_SUCCESS
                    and removable_snapshot_id not in attached_after_remove
                    and retained_snapshot_ids.issubset(attached_after_remove)
                    and remove_snapshot_ids_ok
                ),
            )
        )

        print("[upd/3] upd_config_only_existing_tools_with_config_id")
        retained_snapshot_ids_sorted = sorted(retained_snapshot_ids)
        status_code, detail, config_only_result = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"existing_ids": retained_snapshot_ids_sorted},
                    "connections": {"existing_app_ids": [str(donor_config_id)]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"reference_id": tool_id},
                            "app_ids": [str(donor_config_id)],
                        }
                        for tool_id in retained_snapshot_ids_sorted
                    ],
                }
            ),
        )
        list_status, _list_detail, list_after_config_only = await self._run_list_snapshots(primary_deployment_id)
        attached_after_config_only = self._extract_snapshot_ids(list_after_config_only)
        config_only_snapshot_ids = (
            {str(item) for item in getattr(config_only_result, "snapshot_ids", [])} if config_only_result else set()
        )
        config_only_snapshot_ids_ok = retained_snapshot_ids.issubset(config_only_snapshot_ids)
        results.append(
            self._build_result(
                name="upd_config_only_existing_tools_with_config_id",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=(
                    status_code == OUTCOME_SUCCESS
                    and list_status == OUTCOME_SUCCESS
                    and retained_snapshot_ids.issubset(attached_after_config_only)
                    and config_only_snapshot_ids_ok
                ),
            )
        )

        print("[upd/4] upd_snapshot_add_ids_with_config_id")
        status_code, detail, add_id_result = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"existing_ids": [donor_snapshot_id]},
                    "connections": {"existing_app_ids": [str(donor_config_id)]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"reference_id": donor_snapshot_id},
                            "app_ids": [str(donor_config_id)],
                        }
                    ],
                }
            ),
        )
        list_status, _list_detail, list_after_add_id = await self._run_list_snapshots(primary_deployment_id)
        attached_after_add_id = self._extract_snapshot_ids(list_after_add_id)
        add_id_snapshot_ids = (
            {str(item) for item in getattr(add_id_result, "snapshot_ids", [])} if add_id_result else set()
        )
        results.append(
            self._build_result(
                name="upd_snapshot_add_ids_with_config_id",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=(
                    status_code == OUTCOME_SUCCESS
                    and list_status == OUTCOME_SUCCESS
                    and donor_snapshot_id in attached_after_add_id
                    and donor_snapshot_id in add_id_snapshot_ids
                ),
            )
        )

        print("[upd/5] upd_snapshot_add_raw_with_config_id")
        raw_payload = self._build_flow_payload(label="upd_add_raw")
        status_code, detail, add_raw_result = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "resource_name_prefix": f"e2e_upd_{uuid4().hex[:6]}_",
                    "tools": {"raw_payloads": [raw_payload.model_dump(mode="json")]},
                    "connections": {"existing_app_ids": [str(donor_config_id)]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": raw_payload.name},
                            "app_ids": [str(donor_config_id)],
                        }
                    ],
                }
            ),
        )
        add_raw_snapshot_ids = (
            {str(item) for item in getattr(add_raw_result, "snapshot_ids", [])} if add_raw_result else set()
        )
        self.created_snapshot_ids.update(add_raw_snapshot_ids)
        list_status, _list_detail, list_after_add_raw = await self._run_list_snapshots(primary_deployment_id)
        attached_after_add_raw = self._extract_snapshot_ids(list_after_add_raw)
        add_raw_created_ids = add_raw_snapshot_ids
        results.append(
            self._build_result(
                name="upd_snapshot_add_raw_with_config_id",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=(
                    status_code == OUTCOME_SUCCESS
                    and list_status == OUTCOME_SUCCESS
                    and bool(add_raw_created_ids)
                    and add_raw_created_ids.issubset(attached_after_add_raw)
                ),
            )
        )

        print("[upd/6] upd_mixed_add_remove_raw_with_config")
        mixed_raw_payload = self._build_flow_payload(label="upd_mixed_raw")
        mixed_remove_id = next(iter(retained_snapshot_ids), "")
        status_code, detail, mixed_result = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "resource_name_prefix": f"e2e_upd_mix_{uuid4().hex[:6]}_",
                    "tools": {
                        "existing_ids": [mixed_donor_snapshot_id, mixed_remove_id],
                        "raw_payloads": [mixed_raw_payload.model_dump(mode="json")],
                    },
                    "connections": {"existing_app_ids": [str(donor_config_id)]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"reference_id": mixed_donor_snapshot_id},
                            "app_ids": [str(donor_config_id)],
                        },
                        {"op": "remove_tool", "tool_id": mixed_remove_id},
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": mixed_raw_payload.name},
                            "app_ids": [str(donor_config_id)],
                        },
                    ],
                }
            ),
        )
        mixed_snapshot_ids = (
            {str(item) for item in getattr(mixed_result, "snapshot_ids", [])} if mixed_result else set()
        )
        self.created_snapshot_ids.update(mixed_snapshot_ids)
        list_status, _list_detail, list_after_mixed = await self._run_list_snapshots(primary_deployment_id)
        attached_after_mixed = self._extract_snapshot_ids(list_after_mixed)
        results.append(
            self._build_result(
                name="upd_mixed_add_remove_raw_with_config",
                expected={OUTCOME_SUCCESS},
                actual_outcome=status_code,
                detail=detail,
                ok=(
                    status_code == OUTCOME_SUCCESS
                    and list_status == OUTCOME_SUCCESS
                    and mixed_remove_id not in attached_after_mixed
                    and mixed_donor_snapshot_id in attached_after_mixed
                    and mixed_donor_snapshot_id in mixed_snapshot_ids
                    and len(mixed_snapshot_ids) >= MIN_MIXED_SNAPSHOT_IDS
                ),
            )
        )

        print("[upd/7] upd_reject_bind_with_undeclared_app_id")
        status_code, detail, _ = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"existing_ids": [donor_snapshot_id]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"reference_id": donor_snapshot_id},
                            "app_ids": ["undeclared_app_for_bind"],
                        }
                    ],
                }
            ),
        )
        results.append(
            self._build_result(
                name="upd_reject_bind_with_undeclared_app_id",
                expected={OUTCOME_INVALID_CONTENT},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_INVALID_CONTENT,
            )
        )

        print("[upd/8] upd_reject_raw_bind_with_undeclared_app_id")
        missing_cfg_raw_payload = self._build_flow_payload(label="upd_no_cfg_raw")
        status_code, detail, _ = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"raw_payloads": [missing_cfg_raw_payload.model_dump(mode="json")]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"name_of_raw": missing_cfg_raw_payload.name},
                            "app_ids": ["undeclared_app_for_raw_bind"],
                        }
                    ],
                }
            ),
        )
        results.append(
            self._build_result(
                name="upd_reject_raw_bind_with_undeclared_app_id",
                expected={OUTCOME_INVALID_CONTENT},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_INVALID_CONTENT,
            )
        )

        print("[upd/9] upd_reject_unbind_with_undeclared_app_id")
        status_code, detail, _ = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"existing_ids": [donor_snapshot_id]},
                    "operations": [
                        {
                            "op": "unbind",
                            "tool_id": donor_snapshot_id,
                            "app_ids": ["undeclared_app_for_unbind"],
                        }
                    ],
                }
            ),
        )
        results.append(
            self._build_result(
                name="upd_reject_unbind_with_undeclared_app_id",
                expected={OUTCOME_INVALID_CONTENT},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_INVALID_CONTENT,
            )
        )

        print("[upd/10] upd_reject_unbind_unknown_tool_id")
        status_code, detail, _ = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "connections": {"existing_app_ids": [str(donor_config_id)]},
                    "operations": [
                        {
                            "op": "unbind",
                            "tool_id": str(uuid4()),
                            "app_ids": [str(donor_config_id)],
                        }
                    ],
                }
            ),
        )
        results.append(
            self._build_result(
                name="upd_reject_unbind_unknown_tool_id",
                expected={OUTCOME_INVALID_CONTENT},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_INVALID_CONTENT,
            )
        )

        print("[upd/11] upd_missing_add_id_fails")
        status_code, detail, _ = await self._run_update(
            primary_deployment_id,
            DeploymentUpdate(
                provider_data={
                    "tools": {"existing_ids": [donor_snapshot_id]},
                    "connections": {"existing_app_ids": [str(donor_config_id)]},
                    "operations": [
                        {
                            "op": "bind",
                            "tool": {"reference_id": str(uuid4())},
                            "app_ids": [str(donor_config_id)],
                        }
                    ],
                }
            ),
        )
        results.append(
            self._build_result(
                name="upd_missing_add_id_fails",
                expected={OUTCOME_INVALID_CONTENT},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_INVALID_CONTENT,
            )
        )

        print("[upd/12] upd_config_raw_payload_conflict")
        conflict_seed_deployment_id, _conflict_cfg_id, _conflict_snapshot_ids, _ = await self._create_update_seed(
            label="upd_conflict_seed",
            snapshot_count=1,
        )
        conflict_suffix = uuid4().hex[:8]
        conflict_prefix = f"e2e_upd_conflict_{conflict_suffix}_"
        conflict_name = f"dup_cfg_{conflict_suffix}"
        conflict_tool_id = next(iter(_conflict_snapshot_ids), "")
        if not conflict_tool_id:
            results.append(
                self._build_result(
                    name="upd_config_raw_payload_conflict",
                    expected={OUTCOME_CONFLICT},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="conflict seed snapshot id is missing",
                    ok=False,
                )
            )
            return results
        conflict_payload = DeploymentUpdate(
            provider_data={
                "resource_name_prefix": conflict_prefix,
                "tools": {"existing_ids": [conflict_tool_id]},
                "connections": {"raw_payloads": [{"app_id": conflict_name, "environment_variables": {}}]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": conflict_tool_id},
                        "app_ids": [conflict_name],
                    }
                ],
            }
        )
        setup_status, _setup_detail, _ = await self._run_update(conflict_seed_deployment_id, conflict_payload)
        if setup_status == OUTCOME_SUCCESS:
            self.created_config_ids.add(f"{conflict_prefix}{conflict_name}")
        status_code, detail, _ = await self._run_update(conflict_seed_deployment_id, conflict_payload)
        results.append(
            self._build_result(
                name="upd_config_raw_payload_conflict",
                expected={OUTCOME_CONFLICT},
                actual_outcome=status_code,
                detail=(f"setup={setup_status}:{_setup_detail} conflict={status_code}:{detail}"),
                ok=setup_status == OUTCOME_SUCCESS and status_code == OUTCOME_CONFLICT,
            )
        )

        print("[upd/13] upd_not_found_deployment")
        status_code, detail, _ = await self._run_update(
            str(uuid4()),
            DeploymentUpdate(spec=BaseDeploymentDataUpdate(description="not found update")),
        )
        results.append(
            self._build_result(
                name="upd_not_found_deployment",
                expected={OUTCOME_NOT_FOUND},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_NOT_FOUND,
            )
        )

        # keep seed deployments tracked for shared final cleanup
        self.created_deployment_ids.add(primary_deployment_id)
        self.created_deployment_ids.add(donor_deployment_id)
        self.created_deployment_ids.add(mixed_donor_deployment_id)
        return results

    async def _run_live_concurrency_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        iterations_raw = os.getenv("WXO_CONCURRENCY_REPEAT", str(DEFAULT_CONCURRENCY_ITERATIONS)).strip()
        try:
            iterations = max(1, int(iterations_raw))
        except ValueError:
            iterations = DEFAULT_CONCURRENCY_ITERATIONS

        print(f"\n[concurrency] running iterations={iterations}")
        for iteration in range(1, iterations + 1):
            print(f"\n[concurrency] iteration {iteration}/{iterations}")
            results.extend(await self._run_live_concurrency_iteration(iteration=iteration))
        return results

    async def _run_live_concurrency_iteration(self, *, iteration: int) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []

        print(f"[cc/{iteration}.1] cc_create_same_prefix_race")
        shared_prefix = f"e2e_cc_shared_{uuid4().hex[:6]}_"
        shared_dep_name = self._mk_name("dep_cc_shared")
        shared_cfg_name = self._mk_name("cfg_cc_shared")
        shared_snap_name = self._mk_name("snap_cc_shared")
        shared_payload = self._build_create_payload(
            snapshots=[self._build_flow_payload(label="cc_shared_snap", name_override=shared_snap_name)],
            config=DeploymentConfig(
                name=shared_cfg_name,
                description="concurrency create collision",
                environment_variables={},
            ),
            resource_name_prefix=shared_prefix,
        )
        shared_payload.spec = shared_payload.spec.model_copy(update={"name": shared_dep_name}, deep=True)
        create_race = await self._run_parallel_calls(
            {
                "left": lambda: self._run_create(shared_payload.model_copy(deep=True)),
                "right": lambda: self._run_create(shared_payload.model_copy(deep=True)),
            }
        )
        left_status, left_detail, left_created = create_race["left"]
        right_status, right_detail, right_created = create_race["right"]
        self._track_created_result(left_created)
        self._track_created_result(right_created)
        create_pair = (left_status, right_status)
        create_pair_ok = create_pair in {
            (OUTCOME_SUCCESS, OUTCOME_CONFLICT),
            (OUTCOME_CONFLICT, OUTCOME_SUCCESS),
            (OUTCOME_SUCCESS, OUTCOME_SUCCESS),
        }
        create_no_internal = OUTCOME_FAILURE not in {left_status, right_status}
        results.append(
            self._build_result(
                name="cc_create_same_prefix_race",
                expected={OUTCOME_SUCCESS, OUTCOME_CONFLICT},
                actual_outcome=max(left_status, right_status),
                detail=f"left={left_status}:{left_detail} right={right_status}:{right_detail}",
                ok=create_pair_ok and create_no_internal,
            )
        )

        print(f"[cc/{iteration}.2] cc_update_spec_vs_snapshot_race")
        primary_id, _primary_cfg_id, _primary_snaps, _ = await self._create_update_seed(
            label=f"cc_upd_primary_{iteration}",
            snapshot_count=2,
        )
        _donor_id, donor_cfg_id, donor_snapshot_ids, _ = await self._create_update_seed(
            label=f"cc_upd_donor_{iteration}",
            snapshot_count=1,
        )
        donor_snapshot_id = next(iter(donor_snapshot_ids), "")
        update_race = await self._run_parallel_calls(
            {
                "spec": lambda: self._run_update(
                    primary_id,
                    DeploymentUpdate(spec=BaseDeploymentDataUpdate(description="cc concurrent spec update")),
                ),
                "snapshot": lambda: self._run_update(
                    primary_id,
                    DeploymentUpdate(
                        provider_data={
                            "tools": {"existing_ids": [donor_snapshot_id]},
                            "connections": {"existing_app_ids": [str(donor_cfg_id)]},
                            "operations": [
                                {
                                    "op": "bind",
                                    "tool": {"reference_id": donor_snapshot_id},
                                    "app_ids": [str(donor_cfg_id)],
                                }
                            ],
                        }
                    ),
                ),
            }
        )
        spec_status, spec_detail, _ = update_race["spec"]
        snapshot_status, snapshot_detail, _ = update_race["snapshot"]
        list_status, _list_detail, list_after = await self._run_list_snapshots(primary_id)
        attached_after = self._extract_snapshot_ids(list_after)
        no_internal_race = OUTCOME_FAILURE not in {spec_status, snapshot_status}
        results.append(
            self._build_result(
                name="cc_update_spec_vs_snapshot_race",
                expected={
                    OUTCOME_SUCCESS,
                    OUTCOME_INVALID_OPERATION,
                    OUTCOME_CONFLICT,
                    OUTCOME_INVALID_CONTENT,
                    OUTCOME_NOT_FOUND,
                },
                actual_outcome=max(spec_status, snapshot_status),
                detail=f"spec={spec_status}:{spec_detail} snapshot={snapshot_status}:{snapshot_detail}",
                ok=(
                    no_internal_race
                    and list_status == OUTCOME_SUCCESS
                    and self._has_unique_snapshot_ids(attached_after)
                ),
            )
        )

        print(f"[cc/{iteration}.3] cc_update_vs_delete_deployment_race")
        race_delete_id, _race_delete_cfg, _race_delete_snaps, _ = await self._create_update_seed(
            label=f"cc_upd_del_{iteration}",
            snapshot_count=1,
        )
        update_delete_race = await self._run_parallel_calls(
            {
                "update": lambda: self._run_update(
                    race_delete_id,
                    DeploymentUpdate(spec=BaseDeploymentDataUpdate(description="cc update while delete")),
                ),
                "delete": lambda: self._run_delete(race_delete_id),
            }
        )
        upd_status, upd_detail, _ = update_delete_race["update"]
        del_status, del_detail, _ = update_delete_race["delete"]
        status_after_delete_race, _status_detail, _status_payload = await self._run_status(race_delete_id)
        allowed_pairs = {
            (OUTCOME_SUCCESS, OUTCOME_SUCCESS),
            (OUTCOME_NOT_FOUND, OUTCOME_SUCCESS),
            (OUTCOME_SUCCESS, OUTCOME_NOT_FOUND),
            (OUTCOME_NOT_FOUND, OUTCOME_NOT_FOUND),
        }
        results.append(
            self._build_result(
                name="cc_update_vs_delete_deployment_race",
                expected={OUTCOME_SUCCESS, OUTCOME_NOT_FOUND, OUTCOME_FAILURE},
                actual_outcome=max(upd_status, del_status),
                detail=(
                    f"update={upd_status}:{upd_detail} "
                    f"delete={del_status}:{del_detail} status={status_after_delete_race}"
                ),
                ok=(upd_status, del_status) in allowed_pairs
                or (
                    OUTCOME_FAILURE in {upd_status, del_status} and "not found" in f"{upd_detail} {del_detail}".lower()
                ),
            )
        )
        self.created_deployment_ids.discard(race_delete_id)

        print(f"[cc/{iteration}.4] cc_execution_vs_delete_deployment_race")
        exec_delete_id, _exec_delete_cfg, _exec_delete_snapshots, _ = await self._create_update_seed(
            label=f"cc_exec_del_{iteration}",
            snapshot_count=1,
        )
        exec_delete_race = await self._run_parallel_calls(
            {
                "execution": lambda: self._run_create_execution(
                    exec_delete_id,
                    provider_data={"message": {"role": "user", "content": "cc execution while delete"}},
                ),
                "delete": lambda: self._run_delete(exec_delete_id),
            }
        )
        exec_status, exec_detail, _ = exec_delete_race["execution"]
        del_exec_status, del_exec_detail, _ = exec_delete_race["delete"]
        results.append(
            self._build_result(
                name="cc_execution_vs_delete_deployment_race",
                expected={OUTCOME_SUCCESS, OUTCOME_NOT_FOUND, OUTCOME_SUCCESS, OUTCOME_FAILURE},
                actual_outcome=max(exec_status, del_exec_status),
                detail=f"execution={exec_status}:{exec_detail} delete={del_exec_status}:{del_exec_detail}",
                ok=OUTCOME_FAILURE not in {exec_status, del_exec_status}
                or "not found" in f"{exec_detail} {del_exec_detail}".lower(),
            )
        )
        self.created_deployment_ids.discard(exec_delete_id)

        print(f"[cc/{iteration}.5] cc_delete_snapshot_during_update_bindings")
        delete_bind_id, bind_cfg_id, bind_snapshot_ids, _ = await self._create_update_seed(
            label=f"cc_del_bind_{iteration}",
            snapshot_count=2,
        )
        delete_target_snapshot_id = next(iter(bind_snapshot_ids), "")

        async def _delete_target_before_bind(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            clients = kwargs.get("clients")
            existing_tool_deltas = kwargs.get("existing_tool_deltas") or {}
            target_ids = list(existing_tool_deltas.keys())
            tool_id = str(target_ids[0]) if target_ids else delete_target_snapshot_id
            if clients and tool_id:
                await self._safe_delete_snapshot(clients=clients, snapshot_id=tool_id)

        del_bind_status, del_bind_detail, _ = await self._run_with_stage_hook(
            stage="update_bindings",
            operation=lambda: self._run_update(
                delete_bind_id,
                DeploymentUpdate(
                    provider_data={
                        "tools": {"existing_ids": sorted(bind_snapshot_ids)},
                        "connections": {"existing_app_ids": [str(bind_cfg_id)]},
                        "operations": [
                            {
                                "op": "unbind",
                                "tool_id": tool_id,
                                "app_ids": [str(bind_cfg_id)],
                            }
                            for tool_id in sorted(bind_snapshot_ids)
                        ],
                    }
                ),
            ),
            hook_before=_delete_target_before_bind,
        )
        results.append(
            self._build_result(
                name="cc_delete_snapshot_during_update_bindings",
                expected={OUTCOME_INVALID_CONTENT, OUTCOME_INVALID_OPERATION, OUTCOME_SUCCESS},
                actual_outcome=del_bind_status,
                detail=del_bind_detail,
                ok=del_bind_status in {OUTCOME_SUCCESS, OUTCOME_INVALID_OPERATION, OUTCOME_INVALID_CONTENT},
            )
        )

        print(f"[cc/{iteration}.6] cc_delete_config_after_update_raw_create")
        delete_cfg_id, _delete_cfg_base_id, delete_cfg_snapshots, _ = await self._create_update_seed(
            label=f"cc_del_cfg_{iteration}",
            snapshot_count=1,
        )
        target_tool_id = next(iter(delete_cfg_snapshots), "")
        if not target_tool_id:
            results.append(
                self._build_result(
                    name="cc_delete_config_after_update_raw_create",
                    expected={OUTCOME_INVALID_OPERATION, OUTCOME_INVALID_CONTENT, OUTCOME_CONFLICT, OUTCOME_FAILURE},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed snapshot id missing for update raw config stage",
                    ok=False,
                )
            )
            return results
        cfg_prefix = f"e2e_cc_del_cfg_{uuid4().hex[:6]}_"
        raw_cfg_name = self._mk_name("cc_raw_cfg")

        async def _delete_created_app_after_config_create(created_app_id: Any, **kwargs: Any) -> None:
            if not created_app_id:
                created_app_id = kwargs.get("app_id")
            app_id = str(created_app_id or "").strip()
            clients = await self.service._get_provider_clients(user_id=self.user_id, db=self.db)  # noqa: SLF001
            if app_id:
                await self._safe_delete_config(clients=clients, config_id=app_id)

        del_cfg_status, del_cfg_detail, _ = await self._run_with_stage_hook(
            stage="update_create_config",
            operation=lambda: self._run_update(
                delete_cfg_id,
                DeploymentUpdate(
                    provider_data={
                        "resource_name_prefix": cfg_prefix,
                        "tools": {"existing_ids": [target_tool_id]},
                        "connections": {"raw_payloads": [{"app_id": raw_cfg_name, "environment_variables": {}}]},
                        "operations": [
                            {
                                "op": "bind",
                                "tool": {"reference_id": target_tool_id},
                                "app_ids": [raw_cfg_name],
                            }
                        ],
                    }
                ),
            ),
            hook_after=_delete_created_app_after_config_create,
        )
        results.append(
            self._build_result(
                name="cc_delete_config_after_update_raw_create",
                expected={OUTCOME_INVALID_OPERATION, OUTCOME_INVALID_CONTENT, OUTCOME_CONFLICT, OUTCOME_FAILURE},
                actual_outcome=del_cfg_status,
                detail=del_cfg_detail,
                ok=del_cfg_status
                in {
                    OUTCOME_INVALID_OPERATION,
                    OUTCOME_INVALID_CONTENT,
                    OUTCOME_CONFLICT,
                    OUTCOME_FAILURE,
                },
            )
        )

        print(f"[cc/{iteration}.7] cc_create_during_create_snapshots_stage")
        create_race_prefix = f"e2e_cc_create_stage_{uuid4().hex[:6]}_"
        create_race_dep = self._mk_name("cc_stage_dep")
        create_race_cfg = self._mk_name("cc_stage_cfg")
        create_race_snap = self._mk_name("cc_stage_snap")
        race_payload = self._build_create_payload(
            snapshots=[self._build_flow_payload(label="cc_stage_snap", name_override=create_race_snap)],
            config=DeploymentConfig(
                name=create_race_cfg,
                description="cc competing create",
                environment_variables={},
            ),
            resource_name_prefix=create_race_prefix,
        )
        race_payload.spec = race_payload.spec.model_copy(update={"name": create_race_dep}, deep=True)
        competing_create_task: asyncio.Task[tuple[str, str, dict[str, Any] | None]] | None = None

        async def _launch_competing_create(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            nonlocal competing_create_task
            if competing_create_task is None:
                competing_create_task = asyncio.create_task(self._run_create(race_payload.model_copy(deep=True)))
                await asyncio.sleep(0)

        staged_create_status, staged_create_detail, staged_create_created = await self._run_with_stage_hook(
            stage="create_snapshots",
            operation=lambda: self._run_create(race_payload.model_copy(deep=True)),
            hook_before=_launch_competing_create,
        )
        competing_create_result = (OUTCOME_FAILURE, "competing create did not start", None)
        if competing_create_task is not None:
            competing_create_result = await competing_create_task
        comp_status, comp_detail, comp_created = competing_create_result
        self._track_created_result(staged_create_created)
        self._track_created_result(comp_created)
        staged_pair = (staged_create_status, comp_status)
        results.append(
            self._build_result(
                name="cc_create_during_create_snapshots_stage",
                expected={OUTCOME_SUCCESS, OUTCOME_CONFLICT},
                actual_outcome=max(staged_create_status, comp_status),
                detail=f"main={staged_create_status}:{staged_create_detail} competing={comp_status}:{comp_detail}",
                ok=(
                    staged_pair
                    in {
                        (OUTCOME_SUCCESS, OUTCOME_CONFLICT),
                        (OUTCOME_CONFLICT, OUTCOME_SUCCESS),
                        (OUTCOME_SUCCESS, OUTCOME_SUCCESS),
                    }
                    and OUTCOME_FAILURE not in staged_pair
                ),
            )
        )

        print(f"[cc/{iteration}.8] cc_create_during_update_raw_config_stage")
        update_create_id, _update_create_cfg, update_create_snaps, _ = await self._create_update_seed(
            label=f"cc_create_update_cfg_{iteration}",
            snapshot_count=1,
        )
        update_target_tool_id = next(iter(update_create_snaps), "")
        if not update_target_tool_id:
            results.append(
                self._build_result(
                    name="cc_create_during_update_raw_config_stage",
                    expected={OUTCOME_SUCCESS, OUTCOME_CONFLICT},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed snapshot id missing for competing update",
                    ok=False,
                )
            )
            return results
        update_cfg_prefix = f"e2e_cc_upd_cfg_create_{uuid4().hex[:6]}_"
        update_cfg_name = self._mk_name("cc_upd_cfg_create")
        competing_update_task: asyncio.Task[tuple[str, str, Any | None]] | None = None

        competing_update_payload = DeploymentUpdate(
            provider_data={
                "resource_name_prefix": update_cfg_prefix,
                "tools": {"existing_ids": [update_target_tool_id]},
                "connections": {"raw_payloads": [{"app_id": update_cfg_name, "environment_variables": {}}]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": update_target_tool_id},
                        "app_ids": [update_cfg_name],
                    }
                ],
            },
        )

        async def _launch_competing_update_create(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            nonlocal competing_update_task
            if competing_update_task is None:
                competing_update_task = asyncio.create_task(
                    self._run_update(update_create_id, competing_update_payload.model_copy(deep=True))
                )
                await asyncio.sleep(0)

        update_cfg_status, update_cfg_detail, _ = await self._run_with_stage_hook(
            stage="update_create_config",
            operation=lambda: self._run_update(update_create_id, competing_update_payload.model_copy(deep=True)),
            hook_before=_launch_competing_update_create,
        )
        competing_update_result = (OUTCOME_FAILURE, "competing update did not start", None)
        if competing_update_task is not None:
            competing_update_result = await competing_update_task
        competing_upd_status, competing_upd_detail, _ = competing_update_result
        results.append(
            self._build_result(
                name="cc_create_during_update_raw_config_stage",
                expected={OUTCOME_SUCCESS, OUTCOME_CONFLICT},
                actual_outcome=max(update_cfg_status, competing_upd_status),
                detail=(
                    f"main={update_cfg_status}:{update_cfg_detail} "
                    f"competing={competing_upd_status}:{competing_upd_detail}"
                ),
                ok=OUTCOME_FAILURE not in {update_cfg_status, competing_upd_status},
            )
        )

        print(f"[cc/{iteration}.9] cc_delete_resources_during_update_rollback")
        rollback_id, rollback_cfg_id, rollback_seed_snapshots, _ = await self._create_update_seed(
            label=f"cc_rollback_delete_{iteration}",
            snapshot_count=1,
        )
        if not rollback_cfg_id:
            results.append(
                self._build_result(
                    name="cc_delete_resources_during_update_rollback",
                    expected={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed rollback config id missing",
                    ok=False,
                )
            )
            return results
        rollback_seed_tool_id = next(iter(rollback_seed_snapshots), "")
        if not rollback_seed_tool_id:
            results.append(
                self._build_result(
                    name="cc_delete_resources_during_update_rollback",
                    expected={OUTCOME_FAILURE},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed snapshot id missing for rollback race",
                    ok=False,
                )
            )
            return results
        rollback_prefix = f"e2e_cc_rollback_{uuid4().hex[:6]}_"
        rollback_raw_flow = self._build_flow_payload(label=f"cc_rb_raw_{iteration}")
        rollback_raw_cfg_name = self._mk_name("cc_rb_cfg")
        rollback_status, rollback_detail, _ = await self._run_with_stage_hook(
            stage="update_rollback_resources",
            operation=lambda: self._run_update(
                rollback_id,
                DeploymentUpdate(
                    spec=BaseDeploymentDataUpdate(description="cc rollback delete race"),
                    provider_data={
                        "resource_name_prefix": rollback_prefix,
                        "tools": {
                            "existing_ids": [rollback_seed_tool_id],
                            "raw_payloads": [rollback_raw_flow.model_dump(mode="json")],
                        },
                        "connections": {
                            "existing_app_ids": [str(rollback_cfg_id)],
                            "raw_payloads": [{"app_id": rollback_raw_cfg_name, "environment_variables": {}}],
                        },
                        "operations": [
                            {
                                "op": "unbind",
                                "tool_id": rollback_seed_tool_id,
                                "app_ids": [str(rollback_cfg_id)],
                            },
                            {
                                "op": "bind",
                                "tool": {"name_of_raw": rollback_raw_flow.name},
                                "app_ids": [rollback_raw_cfg_name],
                            },
                        ],
                    },
                ),
                inject={
                    "update_bindings": {
                        "fail_first_n": 1,
                        "error_type": "runtime",
                        "message": "cc_rollback_trigger",
                    }
                },
            ),
            hook_before=self._delete_resources_before_rollback_hook,
        )
        results.append(
            self._build_result(
                name="cc_delete_resources_during_update_rollback",
                expected={OUTCOME_FAILURE},
                actual_outcome=rollback_status,
                detail=rollback_detail,
                ok=rollback_status == OUTCOME_FAILURE,
            )
        )

        print(f"[cc/{iteration}.10] cc_create_during_update_rollback")
        rollback_create_id, rollback_create_cfg_id, rollback_create_snaps, _ = await self._create_update_seed(
            label=f"cc_rollback_create_{iteration}",
            snapshot_count=1,
        )
        if not rollback_create_cfg_id:
            results.append(
                self._build_result(
                    name="cc_create_during_update_rollback",
                    expected={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed rollback-create config id missing",
                    ok=False,
                )
            )
            return results
        rollback_create_seed_tool_id = next(iter(rollback_create_snaps), "")
        if not rollback_create_seed_tool_id:
            results.append(
                self._build_result(
                    name="cc_create_during_update_rollback",
                    expected={OUTCOME_FAILURE, OUTCOME_SUCCESS, OUTCOME_CONFLICT},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed snapshot id missing for rollback create race",
                    ok=False,
                )
            )
            return results
        rollback_create_prefix = f"e2e_cc_rb_create_{uuid4().hex[:6]}_"
        rollback_create_cfg_name = self._mk_name("cc_rb_create_cfg")
        competing_rollback_create_task: asyncio.Task[tuple[str, str, Any | None]] | None = None

        async def _launch_competing_create_before_rollback(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            nonlocal competing_rollback_create_task
            if competing_rollback_create_task is not None:
                return
            competing_rollback_create_task = asyncio.create_task(
                self._run_update(
                    rollback_create_id,
                    DeploymentUpdate(
                        provider_data={
                            "resource_name_prefix": rollback_create_prefix,
                            "tools": {"existing_ids": [rollback_create_seed_tool_id]},
                            "connections": {
                                "raw_payloads": [{"app_id": rollback_create_cfg_name, "environment_variables": {}}]
                            },
                            "operations": [
                                {
                                    "op": "bind",
                                    "tool": {"reference_id": rollback_create_seed_tool_id},
                                    "app_ids": [rollback_create_cfg_name],
                                }
                            ],
                        },
                    ),
                )
            )
            await asyncio.sleep(0)

        rollback_create_raw_flow = self._build_flow_payload(label=f"cc_rb_create_raw_{iteration}")
        rollback_create_status, rollback_create_detail, _ = await self._run_with_stage_hook(
            stage="update_rollback_resources",
            operation=lambda: self._run_update(
                rollback_create_id,
                DeploymentUpdate(
                    spec=BaseDeploymentDataUpdate(description="cc rollback create race"),
                    provider_data={
                        "resource_name_prefix": rollback_create_prefix,
                        "tools": {
                            "existing_ids": [rollback_create_seed_tool_id],
                            "raw_payloads": [rollback_create_raw_flow.model_dump(mode="json")],
                        },
                        "connections": {
                            "existing_app_ids": [str(rollback_create_cfg_id)],
                            "raw_payloads": [{"app_id": rollback_create_cfg_name, "environment_variables": {}}],
                        },
                        "operations": [
                            {
                                "op": "unbind",
                                "tool_id": rollback_create_seed_tool_id,
                                "app_ids": [str(rollback_create_cfg_id)],
                            },
                            {
                                "op": "bind",
                                "tool": {"name_of_raw": rollback_create_raw_flow.name},
                                "app_ids": [rollback_create_cfg_name],
                            },
                        ],
                    },
                ),
                inject={
                    "update_bindings": {
                        "fail_first_n": 1,
                        "error_type": "runtime",
                        "message": "cc_rollback_create_trigger",
                    }
                },
            ),
            hook_before=_launch_competing_create_before_rollback,
        )
        competing_rollback_create_result = (OUTCOME_FAILURE, "competing rollback create missing", None)
        if competing_rollback_create_task is not None:
            competing_rollback_create_result = await competing_rollback_create_task
        comp_rb_status, comp_rb_detail, _ = competing_rollback_create_result
        results.append(
            self._build_result(
                name="cc_create_during_update_rollback",
                expected={OUTCOME_FAILURE, OUTCOME_SUCCESS, OUTCOME_CONFLICT},
                actual_outcome=max(rollback_create_status, comp_rb_status),
                detail=(
                    f"main={rollback_create_status}:{rollback_create_detail} "
                    f"competing={comp_rb_status}:{comp_rb_detail}"
                ),
                ok=rollback_create_status == OUTCOME_FAILURE
                and comp_rb_status in {OUTCOME_SUCCESS, OUTCOME_CONFLICT, OUTCOME_FAILURE},
            )
        )

        print(f"[cc/{iteration}.11] cc_parallel_updates_isolation")
        dep_a, cfg_a, _snap_a, _ = await self._create_update_seed(label=f"cc_iso_a_{iteration}", snapshot_count=1)
        dep_b, cfg_b, _snap_b, _ = await self._create_update_seed(label=f"cc_iso_b_{iteration}", snapshot_count=1)
        isolation_race = await self._run_parallel_calls(
            {
                "a": lambda: self._run_update(
                    dep_a,
                    DeploymentUpdate(spec=BaseDeploymentDataUpdate(description="isolation-a")),
                ),
                "b": lambda: self._run_update(
                    dep_b,
                    DeploymentUpdate(spec=BaseDeploymentDataUpdate(description="isolation-b")),
                ),
            }
        )
        iso_a_status, iso_a_detail, _ = isolation_race["a"]
        iso_b_status, iso_b_detail, _ = isolation_race["b"]
        cfg_list_a_status, _cfg_a_detail, cfg_list_a = await self._run_list_configs(dep_a)
        cfg_list_b_status, _cfg_b_detail, cfg_list_b = await self._run_list_configs(dep_b)
        cfg_ids_a = self._extract_config_ids(cfg_list_a)
        cfg_ids_b = self._extract_config_ids(cfg_list_b)
        isolation_ok = (
            cfg_list_a_status == OUTCOME_SUCCESS and cfg_list_b_status == OUTCOME_SUCCESS and cfg_ids_a and cfg_ids_b
        )
        if cfg_a:
            isolation_ok = isolation_ok and str(cfg_a) in cfg_ids_a
        if cfg_b:
            isolation_ok = isolation_ok and str(cfg_b) in cfg_ids_b
        results.append(
            self._build_result(
                name="cc_parallel_updates_isolation",
                expected={OUTCOME_SUCCESS},
                actual_outcome=max(iso_a_status, iso_b_status),
                detail=f"a={iso_a_status}:{iso_a_detail} b={iso_b_status}:{iso_b_detail}",
                ok=isolation_ok and iso_a_status == OUTCOME_SUCCESS and iso_b_status == OUTCOME_SUCCESS,
            )
        )
        return results

    async def _run_parallel_calls(
        self,
        calls: dict[str, Callable[[], Awaitable[tuple[str, str, Any | None]]]],
    ) -> dict[str, tuple[str, str, Any | None]]:
        tasks = {name: asyncio.create_task(call()) for name, call in calls.items()}
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results: dict[str, tuple[str, str, Any | None]] = {}
        for name, outcome in zip(tasks, gathered, strict=False):
            if isinstance(outcome, Exception):
                results[name] = (OUTCOME_FAILURE, str(outcome), None)
            else:
                results[name] = outcome
        return results

    def _track_created_result(self, created: dict[str, Any] | None) -> None:
        if not created:
            return
        deployment_id = created.get("deployment_id")
        config_id = created.get("config_id")
        snapshot_ids = created.get("snapshot_ids") or set()
        if deployment_id:
            self.created_deployment_ids.add(str(deployment_id))
        if config_id:
            self.created_config_ids.add(str(config_id))
        self.created_snapshot_ids.update({str(item) for item in snapshot_ids if item})

    def _has_unique_snapshot_ids(self, snapshot_ids: set[str]) -> bool:
        snapshot_list = [str(item) for item in snapshot_ids]
        return len(snapshot_list) == len(set(snapshot_list))

    def _extract_config_ids(self, config_result: Any) -> set[str]:
        configs = getattr(config_result, "configs", []) if config_result else []
        return {str(config.id) for config in configs if config and getattr(config, "id", None)}

    def _stage_hook_mapping(self) -> dict[str, tuple[Any, str]]:
        return {
            "create_config": (service_module, "process_config"),
            "create_snapshots": (service_module, "process_raw_flows_with_app_id"),
            "create_agent": (self.service, "_create_agent_deployment"),
            "update_create_config": (update_helpers_module, "_create_update_connection_with_conflict_mapping"),
            "update_create_tools": (update_helpers_module, "create_and_upload_wxo_flow_tools_with_bindings"),
            "update_bindings": (update_helpers_module, "_update_existing_tool_connection_deltas"),
            "update_rollback_resources": (update_helpers_module, "rollback_update_resources"),
        }

    async def _run_with_stage_hook(
        self,
        *,
        stage: str,
        operation: Callable[[], Awaitable[tuple[str, str, Any | None]]],
        hook_before: Callable[..., Awaitable[None]] | None = None,
        hook_after: Callable[..., Awaitable[None]] | None = None,
    ) -> tuple[str, str, Any | None]:
        originals: list[tuple[Any, str, Any]] = []
        self._apply_stage_hook(
            stage=stage,
            originals=originals,
            hook_before=hook_before,
            hook_after=hook_after,
        )
        try:
            return await operation()
        finally:
            for target, attr_name, original in originals:
                setattr(target, attr_name, original)

    def _apply_stage_hook(
        self,
        *,
        stage: str,
        originals: list[tuple[Any, str, Any]],
        hook_before: Callable[..., Awaitable[None]] | None = None,
        hook_after: Callable[..., Awaitable[None]] | None = None,
    ) -> None:
        mapping = self._stage_hook_mapping()
        target_and_method = mapping.get(stage)
        if target_and_method is None:
            return
        target, method_name = target_and_method
        original = getattr(target, method_name)
        originals.append((target, method_name, original))
        before_called = {"value": False}
        after_called = {"value": False}

        if isinstance(target, types.ModuleType):

            async def _wrapped_module(
                *args,
                __orig=original,
                __before=hook_before,
                __after=hook_after,
                __before_called=before_called,
                __after_called=after_called,
                **kwargs,
            ):
                if __before is not None and not __before_called["value"]:
                    __before_called["value"] = True
                    await __before(*args, **kwargs)
                result = await __orig(*args, **kwargs)
                if __after is not None and not __after_called["value"]:
                    __after_called["value"] = True
                    await __after(result, *args, **kwargs)
                return result

            setattr(target, method_name, _wrapped_module)
            return

        async def _wrapped_method(
            _self,
            *args,
            __orig=original,
            __before=hook_before,
            __after=hook_after,
            __before_called=before_called,
            __after_called=after_called,
            **kwargs,
        ):
            if __before is not None and not __before_called["value"]:
                __before_called["value"] = True
                await __before(*args, **kwargs)
            result = await __orig(*args, **kwargs)
            if __after is not None and not __after_called["value"]:
                __after_called["value"] = True
                await __after(result, *args, **kwargs)
            return result

        setattr(target, method_name, MethodType(_wrapped_method, target))

    async def _safe_delete_snapshot(self, *, clients: Any, snapshot_id: str) -> None:
        with suppress(ClientAPIException):
            await asyncio.to_thread(clients.tool.delete, snapshot_id)

    async def _safe_delete_config(self, *, clients: Any, config_id: str) -> None:
        with suppress(ClientAPIException):
            await asyncio.to_thread(clients.connections.delete, config_id)

    async def _delete_resources_before_rollback_hook(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        clients = kwargs.get("clients")
        if clients is None:
            return
        for tool_id in kwargs.get("created_tool_ids") or []:
            await self._safe_delete_snapshot(clients=clients, snapshot_id=str(tool_id))
        app_id = kwargs.get("created_app_id")
        if app_id:
            await self._safe_delete_config(clients=clients, config_id=str(app_id))
        for created_app_id in kwargs.get("created_app_ids") or []:
            await self._safe_delete_config(clients=clients, config_id=str(created_app_id))

    async def _run_update_failpoint_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        print("\n[fp-upd] creating seed deployment")
        deployment_id, config_id, snapshot_ids, _ = await self._create_update_seed(
            label="fp_upd_seed",
            snapshot_count=1,
        )
        if not config_id:
            results.append(
                self._build_result(
                    name="fp_update_seed_missing_config",
                    expected={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed deployment config id is missing",
                    ok=False,
                )
            )
            return results
        seed_tool_id = next(iter(snapshot_ids), "")
        if not seed_tool_id:
            results.append(
                self._build_result(
                    name="fp_update_seed_missing_snapshot",
                    expected={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_FAILURE,
                    detail="seed deployment snapshot id is missing",
                    ok=False,
                )
            )
            return results
        failpoint_prefix = f"e2e_fp_upd_{uuid4().hex[:6]}_"
        failpoint_raw_app_id = self._mk_name("fp_upd_cfg")

        update_payload = DeploymentUpdate(
            spec=BaseDeploymentDataUpdate(description="trigger update failpoint"),
            provider_data={
                "resource_name_prefix": failpoint_prefix,
                "tools": {"existing_ids": [seed_tool_id]},
                "connections": {"raw_payloads": [{"app_id": failpoint_raw_app_id, "environment_variables": {}}]},
                "operations": [
                    {
                        "op": "bind",
                        "tool": {"reference_id": seed_tool_id},
                        "app_ids": [failpoint_raw_app_id],
                    }
                ],
            },
        )

        print("[fp-upd/1] fp_update_bindings_failure_triggers_rollback")
        status_code, detail, _ = await self._run_update(
            deployment_id,
            update_payload,
            inject={
                "update_bindings": {
                    "fail_first_n": 1,
                    "error_type": "runtime",
                    "message": "fp_update_bindings_failure",
                }
            },
        )
        results.append(
            self._build_result(
                name="fp_update_bindings_failure_triggers_rollback",
                expected={OUTCOME_FAILURE},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_FAILURE,
            )
        )

        print("[fp-upd/2] fp_update_bindings_failure_with_rollback_failure")
        status_code, detail, _ = await self._run_update(
            deployment_id,
            update_payload,
            inject={
                "update_bindings": {
                    "fail_first_n": 1,
                    "error_type": "runtime",
                    "message": "fp_update_bindings_failure_again",
                },
                "update_rollback_resources": {
                    "fail_first_n": 1,
                    "error_type": "runtime",
                    "message": "fp_update_rollback_failure",
                },
            },
        )
        results.append(
            self._build_result(
                name="fp_update_bindings_failure_with_rollback_failure",
                expected={OUTCOME_FAILURE},
                actual_outcome=status_code,
                detail=detail,
                ok=status_code == OUTCOME_FAILURE,
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
            "update_bindings": (update_helpers_module, "_update_existing_tool_connection_deltas"),
            "update_rollback_resources": (update_helpers_module, "rollback_update_resources"),
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
            if isinstance(target, types.ModuleType):

                async def _wrapped_module(
                    *args,
                    __orig=original,
                    __ctr=counter,
                    __n=fail_first_n,
                    __type=error_type,
                    __msg=message,
                    **kwargs,
                ):
                    __ctr["value"] += 1
                    if __ctr["value"] <= __n:
                        if __type == "domain_conflict":
                            raise DeploymentConflictError(message=__msg)
                        if __type == "domain_not_found":
                            raise DeploymentNotFoundError(message=__msg)
                        if __type == "domain_invalid_content":
                            raise InvalidContentError(message=__msg)
                        if __type == "domain_invalid_operation":
                            raise InvalidDeploymentOperationError(message=__msg)
                        if __type == "domain_failure":
                            raise DeploymentError(message=__msg, error_code="deployment_error")
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
                **kwargs,
            ):
                __ctr["value"] += 1
                if __ctr["value"] <= __n:
                    if __type == "domain_conflict":
                        raise DeploymentConflictError(message=__msg)
                    if __type == "domain_not_found":
                        raise DeploymentNotFoundError(message=__msg)
                    if __type == "domain_invalid_content":
                        raise InvalidContentError(message=__msg)
                    if __type == "domain_invalid_operation":
                        raise InvalidDeploymentOperationError(message=__msg)
                    if __type == "domain_failure":
                        raise DeploymentError(message=__msg, error_code="deployment_error")
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
        prefix = resource_name_prefix or f"e2e_{uuid4().hex[:8]}_"
        provider_spec = {"resource_name_prefix": prefix}
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
                if exc.response.status_code != HTTP_STATUS_NOT_FOUND:
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
                if exc.response.status_code != HTTP_STATUS_NOT_FOUND:
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

    def _scenario_group(self, name: str) -> str:
        prefix = name.split("_", 1)[0]
        if prefix in {"live", "upd", "cc", "fp"}:
            return prefix
        return "other"

    def _scenario_label(self, name: str) -> str:
        if "_" not in name:
            return name
        return name.split("_", 1)[1]

    def _format_expected_outcomes(self, outcomes: set[str]) -> str:
        ordered = sorted(outcomes, key=lambda item: (item != OUTCOME_SUCCESS, item))
        return ", ".join(ordered)

    def _print_result_row(self, result: ScenarioResult) -> None:
        verdict = "PASS" if result.ok else "FAIL"
        scenario_label = self._scenario_label(result.name)
        expected = self._format_expected_outcomes(result.expected_outcomes)
        print(f"{verdict:<5} | {scenario_label:<44} | got: {result.actual_outcome}")
        print(f"{'':5} | {'':44} | expected: {expected}")
        if not result.ok:
            wrapped_detail = textwrap.wrap(result.detail, width=108) or [result.detail]
            for index, line in enumerate(wrapped_detail):
                prefix = "detail: " if index == 0 else "        "
                print(f"{'':5} | {'':44} | {prefix}{line}")

    def _print_summary(self, results: list[ScenarioResult]) -> None:
        print("\nScenario Summary")
        print("-" * 90)
        total = len(results)
        passed = sum(1 for result in results if result.ok)
        failed = total - passed
        print(f"Total={total} Passed={passed} Failed={failed}")
        print("-" * 90)

        grouped_results: dict[str, list[ScenarioResult]] = {"live": [], "upd": [], "cc": [], "fp": [], "other": []}
        for result in results:
            grouped_results[self._scenario_group(result.name)].append(result)

        for group in ("live", "upd", "cc", "fp", "other"):
            group_items = grouped_results[group]
            if not group_items:
                continue
            print(f"\n[{group}] ({len(group_items)})")
            for result in group_items:
                self._print_result_row(result)
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
