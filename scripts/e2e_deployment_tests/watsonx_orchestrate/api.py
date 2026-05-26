"""Deployments API create/update matrix runner.

This script exercises `/api/v1/deployments` over HTTP and focuses on
create/update payload-heavy scenarios for the Watsonx Orchestrate provider.

Warning:
--------
This script performs live integration calls and creates real resources in langflow
and Watsonx Orchestrate (agents, snapshots/tools, and configs/connections).
By default, cleanup runs at the end of execution, but cleanup is best-effort:
if the process is interrupted or provider deletes fail, resources may remain.
Use `--keep-resources` only when you intentionally want to inspect leftovers.

Safety model:
- Destructive operations are only executed for resources created by this run.
- "Onboard existing agent" scenarios reuse an agent created by this run:
  create deployment -> delete with `include_provider=false` -> re-onboard.
- End-of-run cleanup deletes all runner-owned deployment rows and provider
  resources unless `--keep-resources` is set.
- Provider account resolution is deterministic: list deployment providers and
  reuse the one whose URL matches `WXO_INSTANCE_URL`; create a provider account
  when no matching record exists for the current user.

Scenario catalog
----------------
Live create/update happy-path scenarios:
- `create_new_agent_success`: creates a deployment using create-time `add_flows`
  payload (expects Success).
- `create_onboard_existing_agent_without_mutation`: onboards an existing agent
  created by this run (seeded and DB-deleted with `include_provider=false`)
  without mutating provider state (expects Success).
- `create_onboard_existing_agent_with_mutation`: onboards a second owned
  existing agent while applying create payload operations (expects Success).
- `update_metadata_only_success`: updates name/description only (expects Success).
- `update_provider_data_llm_only_success`: updates provider_data model only
  (expects Success).

Live payload-validation scenarios:
- `create_reject_missing_add_flows_and_upsert_tools`: rejects create
  provider_data without operations for new agent creation (expects HTTP422).
- `create_reject_duplicate_connection_app_ids`: rejects create payload with
  duplicate `connections[].app_id` values (expects HTTP422).
- `create_reject_unused_connection_app_ids`: rejects create payload where
  declared connection app ids are not referenced by operations (expects HTTP422).
- `update_reject_empty_body`: rejects update with no changed fields
  (expects HTTP422).
- `update_reject_add_remove_overlap`: rejects update when a flow item includes
  overlapping `add_app_ids` and `remove_app_ids` (expects HTTP422).

Live attachment/flow patching scenarios:
- `update_patch_upsert_flows_add_binding`: exercises update `upsert_flows`
  attachment patch path (expects Success).
- `update_patch_add_second_flow_then_remove`: when a second flow-version id is
  configured, chains add then remove operations for that flow
  (expects Success).

Live rollback/error-path scenarios:
- `create_duplicate_name_conflict`: validates duplicate name protection for the
  same provider account (expects HTTP409).
- `update_unknown_deployment_not_found`: validates unknown deployment handling
  for update calls (expects HTTP404).
- `update_remove_unknown_tool_id_noop_success`: validates remove-by-tool-id is
  accepted as a no-op when the tool id is unknown (expects Success).

Live concurrency/race scenarios:
- `cc_parallel_duplicate_create_<n>`: runs two create calls in parallel with
  the same payload; accepts deterministic outcomes of one success + one conflict
  (or dual success when provider-side timing allows), and tracks owned results.
- `cc_parallel_update_<n>`: runs two updates in parallel against the same
  owned deployment and validates acceptable race outcomes.

Live large/complex payload scenarios (executed at fixed tiers S/M/L):
- `create_large_payload_success_fanout_tier_<tier>`: validates large create
  payload fanout success.
- `create_large_payload_reject_unused_connections_tier_<tier>`: validates
  rejection of unreferenced connection app ids.
- `create_large_payload_reject_duplicate_connection_app_ids_tier_<tier>`:
  validates duplicate connection app id rejection.
- `update_large_payload_success_mixed_ops_tier_<tier>`: validates mixed update
  operations at large scale.
- `update_large_payload_success_tool_id_fanout_tier_<tier>`: validates large
  tool-id upsert/remove operation fanout.
- `update_large_payload_reject_add_remove_overlap_tier_<tier>`: validates
  overlap rejection within one upsert item.
- `update_large_payload_reject_remove_conflict_tier_<tier>`: validates
  remove-vs-upsert conflict rejection.
- `update_large_payload_reject_unbind_raw_app_ids_tier_<tier>`: validates
  rejection of remove_app_ids that target raw connection app ids.
- `update_llm_only_fast_path_control_tier_<tier>`: validates LLM-only fast
  path remains successful.

Failpoint-mode scenarios (API-deterministic failure points):
- `fp_create_missing_flow_version_in_project`: create payload references a
  non-existent flow-version id (expects HTTP404).
- `fp_update_missing_deployment`: update call targets a non-existent
  deployment id (expects HTTP404).
- `fp_create_invalid_conflicting_update_ops_shape`: create payload intentionally
  uses conflicting update-shape operation fields and is rejected by schema
  validation (expects HTTP422).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import httpx
from dotenv import load_dotenv
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from langflow.services.adapters.deployment.context import DeploymentAdapterContext, DeploymentProviderIDContext
from langflow.services.adapters.deployment.watsonx_orchestrate import WxOCredentials

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

OUTCOME_SUCCESS = "Success"
OUTCOME_HTTP_404 = "HTTP404"
OUTCOME_HTTP_409 = "HTTP409"
OUTCOME_HTTP_422 = "HTTP422"
OUTCOME_HTTP_500 = "HTTP500"
OUTCOME_FAILURE = "Failure"

DEFAULT_TIMEOUT_SECS = 90
DEFAULT_CONCURRENCY_REPEAT = 2
DEFAULT_WXO_LLM = "groq/openai/gpt-oss-120b"
LARGE_PAYLOAD_TIER_ORDER = ("S", "M", "L")
# Large success scenarios create connections three times per tier:
# - create_large_payload_success_fanout
# - update_large_payload_success_mixed_ops
# - update_large_payload_success_tool_id_fanout
LARGE_SUCCESS_CONNECTION_MULTIPLIER = 3
MAX_LARGE_SUCCESS_CONNECTION_CREATES = 300
LARGE_PAYLOAD_TIER_CONFIGS: dict[str, dict[str, int]] = {
    "S": {
        "connections": 16,
        "credentials_per_connection": 2,
        "create_flow_items": 1,
        "update_flow_items": 1,
        "update_tool_items": 4,
        "remove_tool_items": 2,
        "remove_app_ids_per_flow": 4,
    },
    "M": {
        "connections": 24,
        "credentials_per_connection": 3,
        "create_flow_items": 2,
        "update_flow_items": 3,
        "update_tool_items": 8,
        "remove_tool_items": 4,
        "remove_app_ids_per_flow": 8,
    },
    "L": {
        "connections": 48,
        "credentials_per_connection": 4,
        "create_flow_items": 6,
        "update_flow_items": 6,
        "update_tool_items": 24,
        "remove_tool_items": 8,
        "remove_app_ids_per_flow": 24,
    },
}
HTTP_STATUS_OK = 200
HTTP_STATUS_CREATED = 201
HTTP_STATUS_NO_CONTENT = 204
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_CONFLICT = 409
HTTP_STATUS_UNPROCESSABLE = 422
HTTP_STATUS_SERVER_ERROR = 500
HTTP_STATUS_MULTIPLE_CHOICES = 300


@dataclass(slots=True)
class ScenarioResult:
    name: str
    expected_outcomes: set[str]
    actual_outcome: str
    ok: bool
    detail: str


@dataclass(slots=True)
class HttpResponseEnvelope:
    status_code: int
    payload: dict[str, Any] | list[Any] | None
    detail: str


@dataclass(slots=True)
class OwnedDeployment:
    deployment_id: str
    resource_key: str
    name: str


class DeploymentsApiParallelE2E:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        instance_url: str,
        provider_api_key: str,
        provider_tenant_id: str | None,
        provider_key: str,
        mode: str,
        test_subset: str,
        keep_resources: bool,
        llm: str,
        flow_version_ids: list[str],
        starter_project_files: list[str] | None,
        starter_project_count: int,
        project_id: str | None,
        timeout_secs: int,
        concurrency_repeat: int,
        verify_tls: bool,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instance_url = instance_url
        self.provider_api_key = provider_api_key
        self.provider_tenant_id = provider_tenant_id
        self.provider_key = provider_key
        self.provider_id: str | None = None
        self.mode = mode
        self.test_subset = test_subset
        self.keep_resources = keep_resources
        self.llm = llm
        self.flow_version_ids = flow_version_ids
        self.starter_project_files = starter_project_files or []
        self.starter_project_count = max(1, starter_project_count)
        self.project_id = project_id
        self.timeout_secs = timeout_secs
        self.concurrency_repeat = concurrency_repeat
        self.verify_tls = verify_tls

        self.run_suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:8]
        self._name_counter = 0
        self.owned_deployments: dict[str, OwnedDeployment] = {}
        self.orphaned_provider_resource_keys: set[str] = set()
        self.created_snapshot_ids: set[str] = set()
        self.created_config_ids: set[str] = set()
        self.requested_raw_connection_app_ids: set[str] = set()
        self.cleanup_issues: list[str] = []
        self.created_provider_account_id: str | None = None
        self.created_flow_ids: set[str] = set()
        self.user_id = str(uuid4())
        self.db = object()
        self._client_mod: Any = None
        self._deployment_context_token: Any = None
        self._original_resolve_wxo_client_credentials: Any = None

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_secs),
            verify=self.verify_tls,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
            },
        )
        self._validate_large_payload_connection_budget()

    def _validate_large_payload_connection_budget(self) -> None:
        total_tier_connections = sum(int(config["connections"]) for config in LARGE_PAYLOAD_TIER_CONFIGS.values())
        expected_large_success_creates = total_tier_connections * LARGE_SUCCESS_CONNECTION_MULTIPLIER
        if expected_large_success_creates > MAX_LARGE_SUCCESS_CONNECTION_CREATES:
            msg = (
                "large payload configuration exceeds connection-create budget: "
                f"expected={expected_large_success_creates} max={MAX_LARGE_SUCCESS_CONNECTION_CREATES}"
            )
            raise RuntimeError(msg)

    async def run(self) -> int:
        print("Starting deployments API parallel E2E runner...")
        results: list[ScenarioResult] = []
        try:
            resolved_provider_id = await self._resolve_or_create_provider_account()
            await self._setup_provider_clients_context()
            await self._ensure_flow_versions()
            print(
                f"mode={self.mode} subset={self.test_subset} provider_id={resolved_provider_id} "
                f"keep_resources={self.keep_resources} flow_versions={','.join(self.flow_version_ids)} "
                f"project_id={self.project_id or '<starter-project>'}"
            )
            total_tier_connections = sum(int(config["connections"]) for config in LARGE_PAYLOAD_TIER_CONFIGS.values())
            expected_large_success_creates = total_tier_connections * LARGE_SUCCESS_CONNECTION_MULTIPLIER
            print(
                "large payload connection budget: "
                f"tiers_total={total_tier_connections} "
                f"expected_success_creates={expected_large_success_creates} "
                f"max={MAX_LARGE_SUCCESS_CONNECTION_CREATES}"
            )
            if self.mode in {"live", "both"}:
                results.extend(await self._run_live_scenarios())
            if self.mode in {"failpoint", "both"}:
                results.extend(await self._run_failpoint_scenarios())
        finally:
            if not self.keep_resources:
                try:
                    await self._cleanup_resources()
                except Exception as exc:  # noqa: BLE001
                    message = f"cleanup routine failed: {exc}"
                    print(f"cleanup warning: {message}")
                    self.cleanup_issues.append(message)
            try:
                await self._client.aclose()
            except Exception as exc:  # noqa: BLE001
                message = f"http client close failed: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)
            try:
                await self._teardown_provider_clients_context()
            except Exception as exc:  # noqa: BLE001
                message = f"provider context teardown failed: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)

        self._print_summary(results)
        if self.cleanup_issues:
            print("Cleanup verification failed:")
            for issue in self.cleanup_issues:
                print(f"- {issue}")
        has_scenario_failures = any(not item.ok for item in results)
        return 1 if has_scenario_failures or bool(self.cleanup_issues) else 0

    async def _run_live_scenarios(self) -> list[ScenarioResult]:
        if self.test_subset == "smoke-connections":
            return await self._run_smoke_connection_scenarios()
        if self.test_subset == "large-tier-s":
            return await self._run_large_complex_payload_scenarios(tiers=["S"])
        results: list[ScenarioResult] = []
        results.extend(await self._run_create_update_happy_paths())
        results.extend(await self._run_payload_validation_scenarios())
        results.extend(await self._run_large_complex_payload_scenarios())
        results.extend(await self._run_attachment_patch_scenarios())
        results.extend(await self._run_rollback_and_error_scenarios())
        results.extend(await self._run_parallel_race_scenarios())
        return results

    async def _run_smoke_connection_scenarios(self) -> list[ScenarioResult]:
        print("Running smoke-connections live subset ...")

        create_app_id = self._normalize_wxo_connection_app_id(f"smoke-create-{self._app_id_namespace()}-000")
        update_app_id = self._normalize_wxo_connection_app_id(f"smoke-update-{self._app_id_namespace()}-001")

        create_payload = self._create_request_payload(
            name=self._mk_name("smoke_create_conn"),
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": [create_app_id]}],
                connections=[
                    {
                        "app_id": create_app_id,
                        "credentials": [{"key": "SMOKE_KEY", "value": "smoke-value", "source": "raw"}],
                    }
                ],
            ),
        )
        results = await self._run_http_scenarios(
            [
                {
                    "name": "smoke_create_with_connection_success",
                    "expected": {OUTCOME_SUCCESS},
                    "call": self._call_create,
                    "payload": create_payload,
                    "track_owned": True,
                }
            ]
        )

        update_seed = await self._create_owned_deployment(
            name=self._mk_name("smoke_update_seed"),
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
            ),
        )
        update_payload = {
            "deployment_id": update_seed.deployment_id,
            "body": {
                "provider_data": self._provider_data_update(
                    connections=[
                        {
                            "app_id": update_app_id,
                            "credentials": [{"key": "SMOKE_UPD_KEY", "value": "smoke-update", "source": "raw"}],
                        }
                    ],
                    upsert_flows=[
                        {
                            "flow_version_id": self.flow_version_ids[0],
                            "add_app_ids": [update_app_id],
                            "remove_app_ids": [],
                        }
                    ],
                )
            },
        }
        results.extend(
            await self._run_http_scenarios(
                [
                    {
                        "name": "smoke_update_with_connection_success",
                        "expected": {OUTCOME_SUCCESS},
                        "call": self._call_update,
                        "payload": update_payload,
                        "track_owned": False,
                    }
                ]
            )
        )
        return results

    async def _run_failpoint_scenarios(self) -> list[ScenarioResult]:
        # API-level deterministic failure points (schema+validation+not-found).
        scenarios = [
            {
                "name": "fp_create_missing_flow_version_in_project",
                "expected": {OUTCOME_HTTP_404},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("fp_missing_flow"),
                    provider_data=self._provider_data_create(
                        add_flows=[{"flow_version_id": str(uuid4()), "app_ids": []}],
                    ),
                ),
                "track_owned": False,
                "detail_contains": "not checkpoints of flows in the selected project",
            },
            {
                "name": "fp_update_missing_deployment",
                "expected": {OUTCOME_HTTP_404},
                "call": self._call_update,
                "payload": {
                    "deployment_id": str(uuid4()),
                    "body": {"provider_data": self._provider_data_update(llm=self.llm)},
                },
                "track_owned": False,
                "detail_contains": "not found",
            },
            {
                "name": "fp_create_invalid_conflicting_update_ops_shape",
                "expected": {OUTCOME_HTTP_422},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("fp_invalid_shape"),
                    provider_data={
                        "llm": self.llm,
                        "upsert_flows": [
                            {
                                "flow_version_id": self.flow_version_ids[0],
                                "add_app_ids": ["cfg-a"],
                                "remove_app_ids": ["cfg-a"],
                            }
                        ],
                    },
                ),
                "track_owned": False,
            },
        ]
        return await self._run_http_scenarios(scenarios)

    async def _run_create_update_happy_paths(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        onboard_seed_without_mutation = await self._create_owned_deployment(
            name=self._mk_name("seed_existing_agent"),
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
            ),
        )
        await self._delete_owned_deployment(onboard_seed_without_mutation.deployment_id, include_provider=False)
        self.orphaned_provider_resource_keys.add(onboard_seed_without_mutation.resource_key)
        onboard_seed_with_mutation = await self._create_owned_deployment(
            name=self._mk_name("seed_existing_agent_mutate"),
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
            ),
        )
        await self._delete_owned_deployment(onboard_seed_with_mutation.deployment_id, include_provider=False)
        self.orphaned_provider_resource_keys.add(onboard_seed_with_mutation.resource_key)

        scenarios = [
            {
                "name": "create_new_agent_success",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("create_new"),
                    provider_data=self._provider_data_create(
                        add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
                    ),
                ),
                "track_owned": True,
            },
            {
                "name": "create_onboard_existing_agent_without_mutation",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("onboard_existing_nomutate"),
                    provider_data=self._provider_data_create(
                        existing_agent_id=onboard_seed_without_mutation.resource_key
                    ),
                ),
                "track_owned": True,
            },
            {
                "name": "create_onboard_existing_agent_with_mutation",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("onboard_existing_mutate"),
                    provider_data=self._provider_data_create(
                        existing_agent_id=onboard_seed_with_mutation.resource_key,
                        add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
                    ),
                ),
                "track_owned": True,
            },
            {
                "name": "update_metadata_only_success",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_update,
                "payload": {
                    "deployment_id": await self._ensure_seed_for_update("meta_only"),
                    "body": {"name": self._mk_name("updated_name"), "description": "metadata-only update"},
                },
                "track_owned": False,
            },
            {
                "name": "update_provider_data_llm_only_success",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_update,
                "payload": {
                    "deployment_id": await self._ensure_seed_for_update("provider_only"),
                    "body": {"provider_data": self._provider_data_update(llm=self.llm)},
                },
                "track_owned": False,
            },
        ]
        results.extend(await self._run_http_scenarios(scenarios))
        return results

    async def _run_payload_validation_scenarios(self) -> list[ScenarioResult]:
        scenarios = [
            {
                "name": "create_reject_missing_add_flows_and_upsert_tools",
                "expected": {OUTCOME_HTTP_422},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("invalid_create_no_ops"),
                    provider_data={"llm": self.llm, "connections": []},
                ),
                "track_owned": False,
            },
            {
                "name": "create_reject_duplicate_connection_app_ids",
                "expected": {OUTCOME_HTTP_422},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("invalid_create_dup_conn"),
                    provider_data=self._provider_data_create(
                        add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": ["cfg-shared"]}],
                        connections=[
                            {"app_id": "cfg-shared", "credentials": [{"key": "k1", "value": "v1", "source": "raw"}]},
                            {"app_id": "cfg-shared", "credentials": [{"key": "k2", "value": "v2", "source": "raw"}]},
                        ],
                    ),
                ),
                "track_owned": False,
            },
            {
                "name": "create_reject_unused_connection_app_ids",
                "expected": {OUTCOME_HTTP_422},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=self._mk_name("invalid_create_unused_conn"),
                    provider_data=self._provider_data_create(
                        add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
                        connections=[
                            {
                                "app_id": "cfg-unused",
                                "credentials": [{"key": "k", "value": "v", "source": "raw"}],
                            }
                        ],
                    ),
                ),
                "track_owned": False,
            },
            {
                "name": "update_reject_empty_body",
                "expected": {OUTCOME_HTTP_422},
                "call": self._call_update,
                "payload": {"deployment_id": str(uuid4()), "body": {}},
                "track_owned": False,
            },
            {
                "name": "update_reject_add_remove_overlap",
                "expected": {OUTCOME_HTTP_422},
                "call": self._call_update,
                "payload": {
                    "deployment_id": await self._ensure_seed_for_update("invalid_update_overlap"),
                    "body": {
                        "provider_data": self._provider_data_update(
                            upsert_flows=[
                                {
                                    "flow_version_id": self.flow_version_ids[0],
                                    "add_app_ids": ["cfg-race"],
                                    "remove_app_ids": ["cfg-race"],
                                }
                            ],
                        )
                    },
                },
                "track_owned": False,
            },
        ]
        return await self._run_http_scenarios(scenarios)

    async def _run_large_complex_payload_scenarios(self, tiers: list[str] | None = None) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        tier_order = tiers or LARGE_PAYLOAD_TIER_ORDER
        for tier in tier_order:
            tier_config = LARGE_PAYLOAD_TIER_CONFIGS[tier]
            tier_label = tier.lower()
            print(f"Running large payload scenario tier={tier} ...")

            create_success_payload = self._create_request_payload(
                name=self._mk_name(f"large_create_success_{tier_label}"),
                provider_data=self._build_large_create_provider_data(tier=tier, tier_config=tier_config),
            )
            create_reject_unused_payload = self._create_request_payload(
                name=self._mk_name(f"large_create_unused_{tier_label}"),
                provider_data=self._build_large_create_unused_connections_provider_data(
                    tier=tier,
                    tier_config=tier_config,
                ),
            )
            create_reject_duplicate_payload = self._create_request_payload(
                name=self._mk_name(f"large_create_duplicate_{tier_label}"),
                provider_data=self._build_large_create_duplicate_connections_provider_data(
                    tier=tier,
                    tier_config=tier_config,
                ),
            )
            create_scenarios = [
                {
                    "name": f"create_large_payload_success_fanout_tier_{tier_label}",
                    "expected": {OUTCOME_SUCCESS},
                    "call": self._call_create,
                    "payload": create_success_payload,
                    "track_owned": True,
                },
                {
                    "name": f"create_large_payload_reject_unused_connections_tier_{tier_label}",
                    "expected": {OUTCOME_HTTP_422},
                    "call": self._call_create,
                    "payload": create_reject_unused_payload,
                    "track_owned": False,
                    "detail_contains": "not referenced by operations",
                },
                {
                    "name": f"create_large_payload_reject_duplicate_connection_app_ids_tier_{tier_label}",
                    "expected": {OUTCOME_HTTP_422},
                    "call": self._call_create,
                    "payload": create_reject_duplicate_payload,
                    "track_owned": False,
                    "detail_contains": "duplicate app_id",
                },
            ]
            results.extend(await self._run_http_scenarios(create_scenarios))

            seed_flow_ids = self._large_seed_flow_ids()
            primary_flow_id = seed_flow_ids[0]
            remove_flow_id = seed_flow_ids[1] if len(seed_flow_ids) > 1 else None

            seeded_tool_ids = await self._ensure_large_tool_id_pool(
                minimum_unique=max(2, int(tier_config["remove_tool_items"]) + 1),
                tier=tier,
            )
            if not seeded_tool_ids:
                msg = f"Unable to seed provider tool ids for large payload scenarios (tier={tier})."
                raise RuntimeError(msg)
            mixed_seed = await self._create_large_update_seed_deployment(tier=tier, label="mixed")
            fanout_seed = await self._create_large_update_seed_deployment(tier=tier, label="tool_fanout")
            validation_seed = await self._create_large_update_seed_deployment(tier=tier, label="validation")

            mixed_provider_data = self._build_large_update_mixed_provider_data(
                tier=tier,
                tier_config=tier_config,
                seeded_tool_ids=seeded_tool_ids,
                primary_flow_id=primary_flow_id,
                remove_flow_id=remove_flow_id,
            )
            tool_fanout_provider_data = self._build_large_update_tool_fanout_provider_data(
                tier=tier,
                tier_config=tier_config,
                seeded_tool_ids=seeded_tool_ids,
            )
            overlap_provider_data = self._build_large_update_overlap_provider_data(
                tier=tier,
                tier_config=tier_config,
                seeded_tool_ids=seeded_tool_ids,
                primary_flow_id=primary_flow_id,
                remove_flow_id=remove_flow_id,
            )
            remove_conflict_provider_data = self._build_large_update_remove_conflict_provider_data(
                tier=tier,
                tier_config=tier_config,
                seeded_tool_ids=seeded_tool_ids,
                primary_flow_id=primary_flow_id,
                remove_flow_id=remove_flow_id,
            )
            unbind_raw_provider_data = self._build_large_update_unbind_raw_provider_data(
                tier=tier,
                tier_config=tier_config,
                seeded_tool_ids=seeded_tool_ids,
                primary_flow_id=primary_flow_id,
                remove_flow_id=remove_flow_id,
            )
            update_scenarios = [
                {
                    "name": f"update_large_payload_success_mixed_ops_tier_{tier_label}",
                    "expected": {OUTCOME_SUCCESS},
                    "call": self._call_update,
                    "payload": {
                        "deployment_id": mixed_seed.deployment_id,
                        "body": {"provider_data": mixed_provider_data},
                    },
                    "track_owned": False,
                },
                {
                    "name": f"update_large_payload_success_tool_id_fanout_tier_{tier_label}",
                    "expected": {OUTCOME_SUCCESS},
                    "call": self._call_update,
                    "payload": {
                        "deployment_id": fanout_seed.deployment_id,
                        "body": {"provider_data": tool_fanout_provider_data},
                    },
                    "track_owned": False,
                },
                {
                    "name": f"update_large_payload_reject_add_remove_overlap_tier_{tier_label}",
                    "expected": {OUTCOME_HTTP_422},
                    "call": self._call_update,
                    "payload": {
                        "deployment_id": validation_seed.deployment_id,
                        "body": {"provider_data": overlap_provider_data},
                    },
                    "track_owned": False,
                    "detail_contains": "must not overlap",
                },
                {
                    "name": f"update_large_payload_reject_remove_conflict_tier_{tier_label}",
                    "expected": {OUTCOME_HTTP_422},
                    "call": self._call_update,
                    "payload": {
                        "deployment_id": validation_seed.deployment_id,
                        "body": {"provider_data": remove_conflict_provider_data},
                    },
                    "track_owned": False,
                    "detail_contains": "cannot be combined with upsert",
                },
                {
                    "name": f"update_large_payload_reject_unbind_raw_app_ids_tier_{tier_label}",
                    "expected": {OUTCOME_HTTP_422},
                    "call": self._call_update,
                    "payload": {
                        "deployment_id": validation_seed.deployment_id,
                        "body": {"provider_data": unbind_raw_provider_data},
                    },
                    "track_owned": False,
                    "detail_contains": "must not reference connections app_ids",
                },
                {
                    "name": f"update_llm_only_fast_path_control_tier_{tier_label}",
                    "expected": {OUTCOME_SUCCESS},
                    "call": self._call_update,
                    "payload": {
                        "deployment_id": validation_seed.deployment_id,
                        "body": {"provider_data": self._provider_data_update(llm=self.llm)},
                    },
                    "track_owned": False,
                },
            ]
            results.extend(await self._run_http_scenarios(update_scenarios))
        return results

    async def _run_attachment_patch_scenarios(self) -> list[ScenarioResult]:
        update_seed = await self._create_owned_deployment(
            name=self._mk_name("attachment_seed"),
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
            ),
        )
        scenarios = [
            {
                "name": "update_patch_upsert_flows_add_binding",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_update,
                "payload": {
                    "deployment_id": update_seed.deployment_id,
                    "body": {
                        "provider_data": self._provider_data_update(
                            upsert_flows=[
                                {
                                    "flow_version_id": self.flow_version_ids[0],
                                    "add_app_ids": [],
                                    "remove_app_ids": [],
                                }
                            ],
                        )
                    },
                },
                "track_owned": False,
            },
        ]
        if len(self.flow_version_ids) > 1:
            scenarios.append(
                {
                    "name": "update_patch_add_second_flow_then_remove",
                    "expected": {OUTCOME_SUCCESS},
                    "call": self._call_update_chain_add_remove,
                    "payload": {
                        "deployment_id": update_seed.deployment_id,
                        "add_flow_version_id": self.flow_version_ids[1],
                    },
                    "track_owned": False,
                }
            )
        return await self._run_http_scenarios(scenarios)

    async def _run_rollback_and_error_scenarios(self) -> list[ScenarioResult]:
        duplicate_name = self._mk_name("dup_name")
        created = await self._create_owned_deployment(
            name=duplicate_name,
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
            ),
        )
        scenarios = [
            {
                "name": "create_duplicate_name_conflict",
                "expected": {OUTCOME_HTTP_409},
                "call": self._call_create,
                "payload": self._create_request_payload(
                    name=duplicate_name,
                    provider_data=self._provider_data_create(
                        add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
                    ),
                ),
                "track_owned": False,
                "detail_contains": "already exists",
            },
            {
                "name": "update_unknown_deployment_not_found",
                "expected": {OUTCOME_HTTP_404},
                "call": self._call_update,
                "payload": {
                    "deployment_id": str(uuid4()),
                    "body": {"provider_data": self._provider_data_update(llm=self.llm)},
                },
                "track_owned": False,
            },
            {
                "name": "update_remove_unknown_tool_id_noop_success",
                "expected": {OUTCOME_SUCCESS},
                "call": self._call_update,
                "payload": {
                    "deployment_id": created.deployment_id,
                    "body": {
                        "provider_data": self._provider_data_update(
                            remove_tools=["tool-not-owned-by-runner"],
                        )
                    },
                },
                "track_owned": False,
            },
        ]
        return await self._run_http_scenarios(scenarios)

    async def _run_parallel_race_scenarios(self) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        for iteration in range(1, self.concurrency_repeat + 1):
            race_name = self._mk_name(f"cc_dup_{iteration}")
            create_body = self._create_request_payload(
                name=race_name,
                provider_data=self._provider_data_create(
                    add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
                ),
            )
            parallel_create_results = await self._run_parallel_calls(
                {
                    "c1": (lambda body=create_body: self._call_create(body)),
                    "c2": (lambda body=create_body: self._call_create(body)),
                }
            )
            statuses = sorted(item.status_code for item in parallel_create_results.values())
            ok = statuses in (
                [HTTP_STATUS_CREATED, HTTP_STATUS_CONFLICT],
                [HTTP_STATUS_CREATED, HTTP_STATUS_CREATED],
            )
            detail = f"statuses={statuses}"
            self._track_raw_connection_app_ids_from_request_payload(create_body)
            for response in parallel_create_results.values():
                self._track_provider_artifacts_from_response(response)
                if response.status_code == HTTP_STATUS_CREATED:
                    tracked = self._track_owned_from_create_response(response)
                    if tracked is None:
                        message = (
                            f"parallel create iteration {iteration} returned HTTP 201 without "
                            "deployment ownership fields; cleanup may be incomplete"
                        )
                        print(f"cleanup warning: {message}")
                        self.cleanup_issues.append(message)
            results.append(
                ScenarioResult(
                    name=f"cc_parallel_duplicate_create_{iteration}",
                    expected_outcomes={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_SUCCESS if ok else OUTCOME_FAILURE,
                    ok=ok,
                    detail=detail,
                )
            )

            update_seed = await self._create_owned_deployment(
                name=self._mk_name(f"cc_update_seed_{iteration}"),
                provider_data=self._provider_data_create(
                    add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
                ),
            )
            parallel_update_results = await self._run_parallel_calls(
                {
                    "u1": (
                        lambda deployment_id=update_seed.deployment_id, iteration_id=iteration: self._call_update(
                            {
                                "deployment_id": deployment_id,
                                "body": {"description": f"race-one-{iteration_id}"},
                            }
                        )
                    ),
                    "u2": (
                        lambda deployment_id=update_seed.deployment_id, iteration_id=iteration: self._call_update(
                            {
                                "deployment_id": deployment_id,
                                "body": {"description": f"race-two-{iteration_id}"},
                            }
                        )
                    ),
                }
            )
            for response in parallel_update_results.values():
                self._track_provider_artifacts_from_response(response)
            update_statuses = sorted(item.status_code for item in parallel_update_results.values())
            update_ok = update_statuses in (
                [HTTP_STATUS_OK, HTTP_STATUS_OK],
                [HTTP_STATUS_OK, HTTP_STATUS_CONFLICT],
            )
            results.append(
                ScenarioResult(
                    name=f"cc_parallel_update_{iteration}",
                    expected_outcomes={OUTCOME_SUCCESS},
                    actual_outcome=OUTCOME_SUCCESS if update_ok else OUTCOME_FAILURE,
                    ok=update_ok,
                    detail=f"statuses={update_statuses}",
                )
            )
        return results

    async def _run_http_scenarios(self, scenarios: list[dict[str, Any]]) -> list[ScenarioResult]:
        results: list[ScenarioResult] = []
        for index, scenario in enumerate(scenarios, start=1):
            print(f"[{index}/{len(scenarios)}] {scenario['name']}")
            try:
                self._track_raw_connection_app_ids_from_request_payload(scenario["payload"])
                envelope = await scenario["call"](scenario["payload"])
                self._track_provider_artifacts_from_response(envelope)
                if scenario.get("track_owned") or envelope.status_code == HTTP_STATUS_CREATED:
                    tracked = self._track_owned_from_create_response(envelope)
                    if envelope.status_code == HTTP_STATUS_CREATED and tracked is None:
                        message = (
                            f"scenario {scenario['name']} returned HTTP 201 without deployment ownership fields; "
                            "cleanup may be incomplete"
                        )
                        print(f"cleanup warning: {message}")
                        self.cleanup_issues.append(message)
                outcome = self._to_outcome(envelope.status_code)
                detail = envelope.detail
            except Exception as exc:  # noqa: BLE001
                outcome = OUTCOME_FAILURE
                detail = str(exc)
            detail_contains = str(scenario.get("detail_contains") or "").strip().lower()
            detail_ok = not detail_contains or detail_contains in detail.lower()
            ok = outcome in scenario["expected"] and detail_ok
            results.append(
                ScenarioResult(
                    name=scenario["name"],
                    expected_outcomes=scenario["expected"],
                    actual_outcome=outcome,
                    ok=ok,
                    detail=detail,
                )
            )
        return results

    async def _call_create(self, payload: dict[str, Any]) -> HttpResponseEnvelope:
        response = await self._client.post("/api/v1/deployments", json=payload)
        return self._normalize_response(response)

    async def _call_update(self, payload: dict[str, Any]) -> HttpResponseEnvelope:
        response = await self._client.patch(f"/api/v1/deployments/{payload['deployment_id']}", json=payload["body"])
        return self._normalize_response(response)

    async def _call_update_chain_add_remove(self, payload: dict[str, Any]) -> HttpResponseEnvelope:
        add_response = await self._client.patch(
            f"/api/v1/deployments/{payload['deployment_id']}",
            json={
                "provider_data": self._provider_data_update(
                    upsert_flows=[
                        {
                            "flow_version_id": payload["add_flow_version_id"],
                            "add_app_ids": [],
                            "remove_app_ids": [],
                        }
                    ]
                )
            },
        )
        normalized_add = self._normalize_response(add_response)
        self._track_provider_artifacts_from_response(normalized_add)
        if normalized_add.status_code >= HTTP_STATUS_MULTIPLE_CHOICES:
            return normalized_add
        remove_response = await self._client.patch(
            f"/api/v1/deployments/{payload['deployment_id']}",
            json={
                "provider_data": self._provider_data_update(
                    remove_flows=[payload["add_flow_version_id"]],
                )
            },
        )
        return self._normalize_response(remove_response)

    async def _create_owned_deployment(self, *, name: str, provider_data: dict[str, Any]) -> OwnedDeployment:
        create_payload = self._create_request_payload(name=name, provider_data=provider_data)
        self._track_raw_connection_app_ids_from_request_payload(create_payload)
        result = await self._call_create(create_payload)
        self._track_provider_artifacts_from_response(result)
        if result.status_code != HTTP_STATUS_CREATED:
            msg = f"create deployment failed: status={result.status_code} detail={result.detail}"
            raise RuntimeError(msg)
        tracked = self._track_owned_from_create_response(result)
        if tracked is None:
            msg = "create deployment succeeded but did not return deployment id/resource_key"
            raise RuntimeError(msg)
        return tracked

    async def _ensure_seed_for_update(self, suffix: str) -> str:
        seed = await self._create_owned_deployment(
            name=self._mk_name(f"upd_seed_{suffix}"),
            provider_data=self._provider_data_create(
                add_flows=[{"flow_version_id": self.flow_version_ids[0], "app_ids": []}],
            ),
        )
        return seed.deployment_id

    def _create_request_payload(self, *, name: str, provider_data: dict[str, Any]) -> dict[str, Any]:
        if self.provider_id is None:
            msg = "provider_id must be resolved before creating deployments"
            raise RuntimeError(msg)
        payload: dict[str, Any] = {
            "provider_id": self.provider_id,
            "name": name,
            "description": "wxo deployments api e2e",
            "type": "agent",
            "provider_data": provider_data,
        }
        if self.project_id:
            payload["project_id"] = self.project_id
        return payload

    def _provider_data_create(
        self,
        *,
        existing_agent_id: str | None = None,
        add_flows: list[dict[str, Any]] | None = None,
        upsert_tools: list[dict[str, Any]] | None = None,
        connections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_add_flows: list[dict[str, Any]] = []
        for item in add_flows or []:
            candidate = dict(item)
            if not str(candidate.get("tool_name") or "").strip():
                flow_version_id = str(candidate.get("flow_version_id") or uuid4()).replace("-", "")[:12]
                candidate["tool_name"] = self._mk_name(f"tool_{flow_version_id}")
            normalized_add_flows.append(candidate)
        payload: dict[str, Any] = {
            "llm": self.llm,
            "add_flows": normalized_add_flows,
            "upsert_tools": upsert_tools or [],
            "connections": connections or [],
        }
        if existing_agent_id:
            payload["existing_agent_id"] = existing_agent_id
        return payload

    def _provider_data_update(
        self,
        *,
        llm: str | None = None,
        connections: list[dict[str, Any]] | None = None,
        upsert_flows: list[dict[str, Any]] | None = None,
        upsert_tools: list[dict[str, Any]] | None = None,
        remove_flows: list[str] | None = None,
        remove_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "llm": llm,
            "connections": connections or [],
            "upsert_flows": upsert_flows or [],
            "upsert_tools": upsert_tools or [],
            "remove_flows": remove_flows or [],
            "remove_tools": remove_tools or [],
        }

    def _large_seed_flow_ids(self) -> list[str]:
        unique_flow_ids = list(dict.fromkeys(self.flow_version_ids))
        if not unique_flow_ids:
            msg = "large payload scenarios require at least one flow_version_id."
            raise RuntimeError(msg)
        return unique_flow_ids[:2] if len(unique_flow_ids) > 1 else unique_flow_ids[:1]

    async def _create_large_update_seed_deployment(self, *, tier: str, label: str) -> OwnedDeployment:
        add_flows = [
            {
                "flow_version_id": flow_version_id,
                "app_ids": [],
                "tool_name": self._large_tool_name(tier=tier, scenario=f"seed_{label}", index=index),
            }
            for index, flow_version_id in enumerate(self._large_seed_flow_ids())
        ]
        return await self._create_owned_deployment(
            name=self._mk_name(f"large_update_seed_{tier.lower()}_{label}"),
            provider_data=self._provider_data_create(add_flows=add_flows),
        )

    async def _ensure_large_tool_id_pool(self, *, minimum_unique: int, tier: str) -> list[str]:
        target_unique = max(1, minimum_unique)
        attempts = 0
        max_attempts = target_unique + 2
        while len(self.created_snapshot_ids) < target_unique and attempts < max_attempts:
            attempts += 1
            await self._create_large_update_seed_deployment(
                tier=tier,
                label=f"tool_pool_{attempts:02d}",
            )
        return sorted(self.created_snapshot_ids)

    def _app_id_namespace(self) -> str:
        # Include seconds and random suffix to avoid cross-run app-id collisions.
        return "".join(ch for ch in self.run_suffix.lower() if ch.isalnum())[:20]

    def _normalize_wxo_connection_app_id(self, app_id: str) -> str:
        translated = str(app_id).strip().replace(" ", "_").replace("-", "_")
        return "".join(ch for ch in translated if ch.isalnum() or ch == "_")

    def _build_large_app_ids(self, *, tier: str, prefix: str, count: int) -> list[str]:
        namespace = self._app_id_namespace()
        # Put the index before namespace so uniqueness survives provider-side truncation.
        return [f"{prefix}-{tier.lower()}-{index:03d}-{namespace}" for index in range(max(1, count))]

    def _partition_evenly(self, values: list[str], partition_count: int) -> list[list[str]]:
        normalized_count = max(1, partition_count)
        buckets: list[list[str]] = [[] for _ in range(normalized_count)]
        for index, value in enumerate(values):
            buckets[index % normalized_count].append(value)
        return buckets

    def _build_large_connections(
        self,
        *,
        tier: str,
        app_ids: list[str],
        credentials_per_connection: int,
        credential_prefix: str,
    ) -> list[dict[str, Any]]:
        connections: list[dict[str, Any]] = []
        normalized_cred_count = max(1, credentials_per_connection)
        for connection_index, app_id in enumerate(app_ids):
            credentials = [
                {
                    "key": f"{credential_prefix.upper()}_{credential_index:02d}",
                    "value": f"{tier.lower()}-{connection_index:03d}-{credential_index:02d}",
                    # Keep large-payload success scenarios self-contained and deterministic.
                    # Variable-sourced credentials require pre-existing variable records and
                    # can fail after connection creation, which then retries into 409 conflicts.
                    "source": "raw",
                }
                for credential_index in range(normalized_cred_count)
            ]
            connections.append({"app_id": app_id, "credentials": credentials})
        return connections

    def _large_tool_name(self, *, tier: str, scenario: str, index: int) -> str:
        return f"wxo_{scenario}_{tier.lower()}_{index:03d}_tool"

    def _build_large_create_provider_data(self, *, tier: str, tier_config: dict[str, int]) -> dict[str, Any]:
        app_ids = self._build_large_app_ids(
            tier=tier,
            prefix="cfg",
            count=int(tier_config["connections"]),
        )
        connections = self._build_large_connections(
            tier=tier,
            app_ids=app_ids,
            credentials_per_connection=int(tier_config["credentials_per_connection"]),
            credential_prefix="create",
        )
        add_flow_count = max(1, int(tier_config["create_flow_items"]))
        app_chunks = self._partition_evenly(app_ids, add_flow_count)
        seed_flow_ids = self._large_seed_flow_ids()
        add_flows = []
        for index, app_chunk in enumerate(app_chunks):
            normalized_chunk = app_chunk or [app_ids[index % len(app_ids)]]
            add_flows.append(
                {
                    "flow_version_id": seed_flow_ids[index % len(seed_flow_ids)],
                    "app_ids": normalized_chunk,
                    "tool_name": self._large_tool_name(tier=tier, scenario="create_fanout", index=index),
                }
            )
        return self._provider_data_create(
            add_flows=add_flows,
            connections=connections,
        )

    def _build_large_create_unused_connections_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
    ) -> dict[str, Any]:
        provider_data = self._build_large_create_provider_data(tier=tier, tier_config=tier_config)
        extra_app_ids = self._build_large_app_ids(
            tier=tier,
            prefix="cfg-unused",
            count=max(2, int(tier_config["credentials_per_connection"])),
        )
        provider_data["connections"].extend(
            self._build_large_connections(
                tier=tier,
                app_ids=extra_app_ids,
                credentials_per_connection=int(tier_config["credentials_per_connection"]),
                credential_prefix="unused",
            )
        )
        return provider_data

    def _build_large_create_duplicate_connections_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
    ) -> dict[str, Any]:
        provider_data = self._build_large_create_provider_data(tier=tier, tier_config=tier_config)
        connections = provider_data.get("connections") or []
        if connections:
            duplicate = dict(connections[0])
            duplicate_credentials = duplicate.get("credentials") or []
            duplicate["credentials"] = [dict(item) for item in duplicate_credentials]
            connections.append(duplicate)
        return provider_data

    def _split_tool_ids_for_upsert_remove(
        self,
        *,
        tool_ids: list[str],
        remove_target: int,
    ) -> tuple[list[str], list[str]]:
        unique_tool_ids = list(dict.fromkeys(item for item in tool_ids if str(item).strip()))
        if not unique_tool_ids:
            return [], []
        normalized_remove_target = max(0, remove_target)
        remove_count = min(normalized_remove_target, max(0, len(unique_tool_ids) - 1))
        if remove_count == 0:
            return unique_tool_ids, []
        remove_ids = unique_tool_ids[-remove_count:]
        upsert_pool = unique_tool_ids[:-remove_count] or unique_tool_ids[:1]
        return upsert_pool, remove_ids

    def _build_large_upsert_tools(
        self,
        *,
        tier: str,
        tool_ids: list[str],
        app_ids: list[str],
        item_count: int,
    ) -> list[dict[str, Any]]:
        if not tool_ids:
            msg = f"No seeded tool ids available for tier={tier} upsert_tools payload."
            raise RuntimeError(msg)
        normalized_count = max(1, item_count)
        add_app_chunks = self._partition_evenly(app_ids, normalized_count)
        upsert_tools: list[dict[str, Any]] = []
        for index in range(normalized_count):
            add_app_ids = add_app_chunks[index] if index < len(add_app_chunks) else []
            if not add_app_ids:
                add_app_ids = [app_ids[index % len(app_ids)]]
            upsert_tools.append(
                {
                    "tool_id": tool_ids[index % len(tool_ids)],
                    "add_app_ids": add_app_ids,
                    "remove_app_ids": [],
                }
            )
        return upsert_tools

    def _build_legacy_remove_app_ids(self, *, tier: str, item_index: int, count: int) -> list[str]:
        normalized_count = max(1, count)
        return [f"legacy-{tier.lower()}-{item_index:03d}-{idx:03d}" for idx in range(normalized_count)]

    def _build_large_update_mixed_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
        seeded_tool_ids: list[str],
        primary_flow_id: str,
        remove_flow_id: str | None,
    ) -> dict[str, Any]:
        app_ids = self._build_large_app_ids(
            tier=tier,
            prefix="upd-mixed",
            count=int(tier_config["connections"]),
        )
        connections = self._build_large_connections(
            tier=tier,
            app_ids=app_ids,
            credentials_per_connection=int(tier_config["credentials_per_connection"]),
            credential_prefix="update",
        )
        flow_item_count = max(1, int(tier_config["update_flow_items"]))
        tool_item_count = max(1, int(tier_config["update_tool_items"]) // 2)
        reference_chunks = self._partition_evenly(app_ids, flow_item_count + tool_item_count)
        flow_add_chunks = reference_chunks[:flow_item_count]
        tool_add_chunks = reference_chunks[flow_item_count:]
        upsert_flows: list[dict[str, Any]] = []
        for index in range(flow_item_count):
            add_app_ids = flow_add_chunks[index] if index < len(flow_add_chunks) else []
            if not add_app_ids:
                add_app_ids = [app_ids[index % len(app_ids)]]
            upsert_item: dict[str, Any] = {
                "flow_version_id": primary_flow_id,
                "add_app_ids": add_app_ids,
                "remove_app_ids": [],
            }
            if index == 0:
                upsert_item["tool_name"] = self._large_tool_name(tier=tier, scenario="update_mixed", index=index)
            upsert_flows.append(upsert_item)
        upsert_tool_pool, remove_tools = self._split_tool_ids_for_upsert_remove(
            tool_ids=seeded_tool_ids,
            remove_target=int(tier_config["remove_tool_items"]),
        )
        tool_add_app_ids = [app_id for chunk in tool_add_chunks for app_id in chunk] or list(app_ids)
        upsert_tools = self._build_large_upsert_tools(
            tier=tier,
            tool_ids=upsert_tool_pool or seeded_tool_ids,
            app_ids=tool_add_app_ids,
            item_count=tool_item_count,
        )
        remove_flows = [remove_flow_id] if remove_flow_id else []
        return self._provider_data_update(
            llm=self.llm,
            connections=connections,
            upsert_flows=upsert_flows,
            upsert_tools=upsert_tools,
            remove_flows=remove_flows,
            remove_tools=remove_tools,
        )

    def _build_large_update_tool_fanout_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
        seeded_tool_ids: list[str],
    ) -> dict[str, Any]:
        app_ids = self._build_large_app_ids(
            tier=tier,
            prefix="upd-tools",
            count=int(tier_config["connections"]),
        )
        connections = self._build_large_connections(
            tier=tier,
            app_ids=app_ids,
            credentials_per_connection=int(tier_config["credentials_per_connection"]),
            credential_prefix="fanout",
        )
        upsert_tool_pool, remove_tools = self._split_tool_ids_for_upsert_remove(
            tool_ids=seeded_tool_ids,
            remove_target=int(tier_config["remove_tool_items"]),
        )
        upsert_tools = self._build_large_upsert_tools(
            tier=tier,
            tool_ids=upsert_tool_pool or seeded_tool_ids,
            app_ids=app_ids,
            item_count=int(tier_config["update_tool_items"]),
        )
        return self._provider_data_update(
            llm=self.llm,
            connections=connections,
            upsert_tools=upsert_tools,
            remove_tools=remove_tools,
        )

    def _build_large_update_overlap_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
        seeded_tool_ids: list[str],
        primary_flow_id: str,
        remove_flow_id: str | None,
    ) -> dict[str, Any]:
        provider_data = self._build_large_update_mixed_provider_data(
            tier=tier,
            tier_config=tier_config,
            seeded_tool_ids=seeded_tool_ids,
            primary_flow_id=primary_flow_id,
            remove_flow_id=remove_flow_id,
        )
        connections = provider_data.get("connections") or []
        upsert_flows = provider_data.get("upsert_flows") or []
        if not connections or not upsert_flows:
            return provider_data
        overlap_app_id = f"overlap-{tier.lower()}-{self._app_id_namespace()}-000"
        existing_add_app_ids = [
            str(item).strip() for item in upsert_flows[0].get("add_app_ids", []) if str(item).strip()
        ]
        if overlap_app_id not in existing_add_app_ids:
            existing_add_app_ids.append(overlap_app_id)
        upsert_flows[0]["add_app_ids"] = existing_add_app_ids
        upsert_flows[0]["remove_app_ids"] = [overlap_app_id]
        return provider_data

    def _build_large_update_remove_conflict_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
        seeded_tool_ids: list[str],
        primary_flow_id: str,
        remove_flow_id: str | None,
    ) -> dict[str, Any]:
        provider_data = self._build_large_update_mixed_provider_data(
            tier=tier,
            tier_config=tier_config,
            seeded_tool_ids=seeded_tool_ids,
            primary_flow_id=primary_flow_id,
            remove_flow_id=remove_flow_id,
        )
        upsert_flows = provider_data.get("upsert_flows") or []
        if upsert_flows:
            provider_data["remove_flows"] = [upsert_flows[0]["flow_version_id"]]
        return provider_data

    def _build_large_update_unbind_raw_provider_data(
        self,
        *,
        tier: str,
        tier_config: dict[str, int],
        seeded_tool_ids: list[str],
        primary_flow_id: str,
        remove_flow_id: str | None,
    ) -> dict[str, Any]:
        provider_data = self._build_large_update_mixed_provider_data(
            tier=tier,
            tier_config=tier_config,
            seeded_tool_ids=seeded_tool_ids,
            primary_flow_id=primary_flow_id,
            remove_flow_id=remove_flow_id,
        )
        connections = provider_data.get("connections") or []
        upsert_flows = provider_data.get("upsert_flows") or []
        if not connections or not upsert_flows:
            return provider_data
        raw_app_id = str(connections[0].get("app_id", "")).strip()
        if not raw_app_id:
            return provider_data
        first_upsert_flow = upsert_flows[0]
        first_upsert_flow["remove_app_ids"] = [raw_app_id]
        first_upsert_flow["add_app_ids"] = [
            item for item in first_upsert_flow.get("add_app_ids", []) if item != raw_app_id
        ]

        is_referenced_on_add_side = any(raw_app_id in item.get("add_app_ids", []) for item in upsert_flows) or any(
            raw_app_id in item.get("add_app_ids", []) for item in provider_data.get("upsert_tools", [])
        )
        if not is_referenced_on_add_side:
            upsert_tools = provider_data.get("upsert_tools") or []
            if upsert_tools:
                first_tool_add_app_ids = list(upsert_tools[0].get("add_app_ids", []))
                if raw_app_id not in first_tool_add_app_ids:
                    first_tool_add_app_ids.append(raw_app_id)
                upsert_tools[0]["add_app_ids"] = first_tool_add_app_ids
        return provider_data

    def _normalize_response(self, response: httpx.Response) -> HttpResponseEnvelope:
        payload: dict[str, Any] | list[Any] | None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        detail = self._detail_from_payload(payload) or (response.text[:500] if response.text else "")
        return HttpResponseEnvelope(status_code=response.status_code, payload=payload, detail=detail)

    def _detail_from_payload(self, payload: dict[str, Any] | list[Any] | None) -> str:
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list):
                flattened = [str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail]
                return "; ".join(flattened)
            return str(payload)[:500]
        if isinstance(payload, list):
            return str(payload)[:500]
        return ""

    def _track_owned_from_create_response(self, envelope: HttpResponseEnvelope) -> OwnedDeployment | None:
        if not isinstance(envelope.payload, dict):
            return None
        deployment_id = envelope.payload.get("id")
        resource_key = envelope.payload.get("resource_key")
        name = envelope.payload.get("name")
        if not deployment_id or not resource_key or not name:
            return None
        owned = OwnedDeployment(deployment_id=str(deployment_id), resource_key=str(resource_key), name=str(name))
        self.owned_deployments[owned.deployment_id] = owned
        return owned

    def _track_provider_artifacts_from_response(self, envelope: HttpResponseEnvelope) -> None:
        if envelope.status_code >= HTTP_STATUS_MULTIPLE_CHOICES:
            return
        if not isinstance(envelope.payload, dict):
            return
        provider_data = envelope.payload.get("provider_data")
        if not isinstance(provider_data, dict):
            return
        created_app_ids = provider_data.get("created_app_ids")
        if isinstance(created_app_ids, list):
            for app_id in created_app_ids:
                normalized = str(app_id).strip()
                if normalized:
                    self.created_config_ids.add(normalized)
        created_tools = provider_data.get("created_tools")
        if isinstance(created_tools, list):
            for item in created_tools:
                if not isinstance(item, dict):
                    continue
                tool_id = str(item.get("tool_id") or item.get("id") or "").strip()
                if tool_id:
                    self.created_snapshot_ids.add(tool_id)

    def _track_raw_connection_app_ids_from_request_payload(self, payload: dict[str, Any]) -> None:
        provider_data: Any = payload.get("provider_data")
        if not isinstance(provider_data, dict):
            body = payload.get("body")
            if isinstance(body, dict):
                provider_data = body.get("provider_data")
        if not isinstance(provider_data, dict):
            return

        connections = provider_data.get("connections")
        if not isinstance(connections, list):
            return
        for connection in connections:
            if not isinstance(connection, dict):
                continue
            app_id = str(connection.get("app_id") or "").strip()
            if app_id:
                self.requested_raw_connection_app_ids.add(app_id)
                normalized = self._normalize_wxo_connection_app_id(app_id)
                if normalized:
                    self.requested_raw_connection_app_ids.add(normalized)

    async def _delete_owned_deployment(self, deployment_id: str, *, include_provider: bool) -> int:
        if deployment_id not in self.owned_deployments:
            msg = f"refusing to delete unmanaged deployment id: {deployment_id}"
            raise RuntimeError(msg)
        response = await self._client.delete(
            f"/api/v1/deployments/{deployment_id}",
            params={"include_provider": str(include_provider).lower()},
        )
        if response.status_code not in {HTTP_STATUS_NO_CONTENT, HTTP_STATUS_NOT_FOUND}:
            normalized = self._normalize_response(response)
            msg = (
                f"delete deployment failed id={deployment_id} include_provider={include_provider} "
                f"status={normalized.status_code} detail={normalized.detail}"
            )
            raise RuntimeError(msg)
        # Treat NOT_FOUND as already deleted and clear ownership tracking.
        self.owned_deployments.pop(deployment_id, None)
        return response.status_code

    async def _cleanup_resources(self) -> None:
        print("Running cleanup...")
        active_ids = list(self.owned_deployments.keys())
        orphaned_keys = list(self.orphaned_provider_resource_keys)
        print(
            "cleanup targets: "
            f"deployments={len(active_ids)} "
            f"orphaned_agents={len(orphaned_keys)} "
            f"snapshots={len(self.created_snapshot_ids)} "
            f"configs={len(self.created_config_ids | self.requested_raw_connection_app_ids)} "
            f"flows={len(self.created_flow_ids)} "
            f"provider_account={'1' if self.created_provider_account_id else '0'}"
        )
        for index, deployment_id in enumerate(active_ids, start=1):
            with_provider = True
            try:
                print(f"cleanup: deleting deployment {index}/{len(active_ids)} {deployment_id} ...")
                status_code = await self._delete_owned_deployment(deployment_id, include_provider=with_provider)
                if status_code == HTTP_STATUS_NO_CONTENT:
                    print(f"cleanup: deleted deployment {deployment_id}")
                else:
                    print(f"cleanup: deployment already missing {deployment_id}")
            except Exception as exc:  # noqa: BLE001
                message = f"could not delete deployment {deployment_id}: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)

        for index, resource_key in enumerate(orphaned_keys, start=1):
            try:
                print(f"cleanup: deleting orphaned provider resource {index}/{len(orphaned_keys)} {resource_key} ...")
                # Re-onboard owned orphan in DB, then delete with provider delete enabled.
                tmp = await self._create_owned_deployment(
                    name=self._mk_name("cleanup_orphan"),
                    provider_data=self._provider_data_create(existing_agent_id=resource_key),
                )
                await self._delete_owned_deployment(tmp.deployment_id, include_provider=True)
                self.orphaned_provider_resource_keys.discard(resource_key)
                print(f"cleanup: deleted orphaned provider resource {resource_key}")
            except Exception as exc:  # noqa: BLE001
                deleted_directly = await self._delete_provider_agent_direct(resource_key)
                if deleted_directly:
                    self.orphaned_provider_resource_keys.discard(resource_key)
                    print(f"cleanup: deleted orphaned provider resource directly {resource_key}")
                    continue
                message = f"could not cleanup orphaned provider resource {resource_key}: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)

        await self._cleanup_created_provider_artifacts()

        if self.owned_deployments:
            message = f"owned deployment leftovers remain: {sorted(self.owned_deployments.keys())}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)
        if self.orphaned_provider_resource_keys:
            message = f"orphaned provider leftovers remain: {sorted(self.orphaned_provider_resource_keys)}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)
        await self._cleanup_created_flows()
        if self.created_provider_account_id:
            await self._cleanup_created_provider_account()

    async def _cleanup_created_flows(self) -> None:
        created_flow_ids = list(self.created_flow_ids)
        for index, flow_id in enumerate(created_flow_ids, start=1):
            print(f"cleanup: deleting flow {index}/{len(created_flow_ids)} {flow_id} ...")
            response = await self._client.delete(f"/api/v1/flows/{flow_id}")
            if response.status_code in {HTTP_STATUS_OK, HTTP_STATUS_NO_CONTENT, HTTP_STATUS_NOT_FOUND}:
                self.created_flow_ids.discard(flow_id)
                if response.status_code == HTTP_STATUS_NOT_FOUND:
                    print(f"cleanup: flow already missing {flow_id}")
                else:
                    print(f"cleanup: deleted flow {flow_id}")
                continue
            normalized = self._normalize_response(response)
            message = (
                f"could not delete runner-created flow {flow_id}: "
                f"status={normalized.status_code} detail={normalized.detail}"
            )
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)

    async def _cleanup_created_provider_artifacts(self) -> None:
        if self._client_mod is None or self.provider_id is None:
            return
        try:
            clients = await self._client_mod.get_provider_clients(user_id=self.user_id, db=self.db)
        except Exception as exc:  # noqa: BLE001
            message = f"could not resolve provider clients for artifact cleanup: {exc}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)
            return

        snapshot_ids = sorted(self.created_snapshot_ids)
        for index, snapshot_id in enumerate(snapshot_ids, start=1):
            try:
                print(f"cleanup: deleting snapshot {index}/{len(snapshot_ids)} {snapshot_id} ...")
                await asyncio.to_thread(clients.tool.delete, snapshot_id)
                self.created_snapshot_ids.discard(snapshot_id)
                print(f"cleanup: deleted snapshot {snapshot_id}")
            except ClientAPIException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code == HTTP_STATUS_NOT_FOUND:
                    self.created_snapshot_ids.discard(snapshot_id)
                    print(f"cleanup: snapshot already missing {snapshot_id}")
                    continue
                message = f"could not delete snapshot {snapshot_id}: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)
            except Exception as exc:  # noqa: BLE001
                message = f"could not delete snapshot {snapshot_id}: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)

        config_cleanup_candidates = sorted(self.created_config_ids | self.requested_raw_connection_app_ids)
        for index, config_id in enumerate(config_cleanup_candidates, start=1):
            try:
                print(f"cleanup: deleting config {index}/{len(config_cleanup_candidates)} {config_id} ...")
                await asyncio.to_thread(clients.connections.delete, config_id)
                self.created_config_ids.discard(config_id)
                self.requested_raw_connection_app_ids.discard(config_id)
                print(f"cleanup: deleted config {config_id}")
            except ClientAPIException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code == HTTP_STATUS_NOT_FOUND:
                    self.created_config_ids.discard(config_id)
                    self.requested_raw_connection_app_ids.discard(config_id)
                    print(f"cleanup: config already missing {config_id}")
                    continue
                message = f"could not delete config {config_id}: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)
            except Exception as exc:  # noqa: BLE001
                message = f"could not delete config {config_id}: {exc}"
                print(f"cleanup warning: {message}")
                self.cleanup_issues.append(message)

        if self.created_snapshot_ids:
            message = f"snapshot leftovers remain: {sorted(self.created_snapshot_ids)}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)
        if self.created_config_ids:
            message = f"config leftovers remain: {sorted(self.created_config_ids)}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)
        if self.requested_raw_connection_app_ids:
            message = f"raw connection app-id leftovers remain: {sorted(self.requested_raw_connection_app_ids)}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)

    async def _delete_provider_agent_direct(self, resource_key: str) -> bool:
        if self._client_mod is None:
            return False
        try:
            clients = await self._client_mod.get_provider_clients(user_id=self.user_id, db=self.db)
            await asyncio.to_thread(clients.agent.delete, resource_key)
        except ClientAPIException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            return status_code == HTTP_STATUS_NOT_FOUND
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    async def _setup_provider_clients_context(self) -> None:
        if self.provider_id is None:
            msg = "provider_id must be resolved before setting adapter client context"
            raise RuntimeError(msg)
        if self._client_mod is not None:
            return

        import langflow.services.adapters.deployment.watsonx_orchestrate.client as client_mod

        self._client_mod = client_mod
        self._original_resolve_wxo_client_credentials = client_mod.resolve_wxo_client_credentials
        deployment_context = DeploymentAdapterContext(provider_id=UUID(self.provider_id))
        self._deployment_context_token = DeploymentProviderIDContext.set_current(deployment_context)

        async def _resolve_credentials(*, user_id, db, provider_id):  # noqa: ARG001
            authenticator = client_mod.get_authenticator(
                instance_url=self.instance_url,
                api_key=self.provider_api_key,
            )
            return WxOCredentials(instance_url=self.instance_url, authenticator=authenticator)

        client_mod.resolve_wxo_client_credentials = _resolve_credentials  # type: ignore[assignment]

    async def _teardown_provider_clients_context(self) -> None:
        if self._client_mod is not None and self._original_resolve_wxo_client_credentials is not None:
            self._client_mod.resolve_wxo_client_credentials = self._original_resolve_wxo_client_credentials
            self._client_mod.clear_provider_clients_request_context()
        if self._deployment_context_token is not None:
            DeploymentProviderIDContext.reset_current(self._deployment_context_token)
        self._client_mod = None
        self._original_resolve_wxo_client_credentials = None
        self._deployment_context_token = None
        if self.created_flow_ids:
            message = f"flow leftovers remain: {sorted(self.created_flow_ids)}"
            print(f"cleanup warning: {message}")
            self.cleanup_issues.append(message)

    async def _cleanup_created_provider_account(self) -> None:
        provider_id = self.created_provider_account_id
        if provider_id is None:
            return
        response = await self._client.delete(f"/api/v1/deployments/providers/{provider_id}")
        if response.status_code in {HTTP_STATUS_NO_CONTENT, HTTP_STATUS_NOT_FOUND}:
            self.created_provider_account_id = None
            return
        normalized = self._normalize_response(response)
        message = (
            f"could not delete runner-created provider account {provider_id}: "
            f"status={normalized.status_code} detail={normalized.detail}"
        )
        print(f"cleanup warning: {message}")
        self.cleanup_issues.append(message)

    async def _resolve_or_create_provider_account(self) -> str:
        existing_id = await self._find_provider_account_id_by_url()
        if existing_id:
            self.provider_id = existing_id
            return existing_id
        created_id = await self._create_provider_account_for_instance_url()
        self.provider_id = created_id
        self.created_provider_account_id = created_id
        return created_id

    async def _find_provider_account_id_by_url(self) -> str | None:
        wanted_url = self._normalize_url(self.instance_url)
        page = 1
        size = 50
        while True:
            response = await self._client.get(
                "/api/v1/deployments/providers",
                params={"page": page, "size": size},
            )
            normalized = self._normalize_response(response)
            if normalized.status_code != HTTP_STATUS_OK:
                msg = f"listing provider accounts failed: status={normalized.status_code} detail={normalized.detail}"
                raise RuntimeError(msg)
            payload = normalized.payload if isinstance(normalized.payload, dict) else {}
            provider_accounts = payload.get("provider_accounts") if isinstance(payload, dict) else []
            if not isinstance(provider_accounts, list):
                provider_accounts = []
            for account in provider_accounts:
                if not isinstance(account, dict):
                    continue
                if str(account.get("provider_key", "")).strip() != self.provider_key:
                    continue
                provider_data = account.get("provider_data")
                if not isinstance(provider_data, dict):
                    continue
                account_url = self._normalize_url(str(provider_data.get("url", "")))
                if account_url != wanted_url:
                    continue
                provider_id = str(account.get("id", "")).strip()
                if provider_id:
                    return provider_id
            total = payload.get("total") if isinstance(payload, dict) else None
            if not isinstance(total, int):
                if len(provider_accounts) < size:
                    return None
            elif page * size >= total:
                return None
            page += 1

    async def _create_provider_account_for_instance_url(self) -> str:
        create_payload: dict[str, Any] = {
            "name": self._mk_name("provider-account"),
            "provider_key": self.provider_key,
            "provider_data": {
                "url": self.instance_url,
                "api_key": self.provider_api_key,
            },
        }
        if self.provider_tenant_id:
            create_payload["provider_data"]["tenant_id"] = self.provider_tenant_id
        response = await self._client.post("/api/v1/deployments/providers", json=create_payload)
        normalized = self._normalize_response(response)
        if normalized.status_code != HTTP_STATUS_CREATED:
            msg = f"creating provider account failed: status={normalized.status_code} detail={normalized.detail}"
            raise RuntimeError(msg)
        payload = normalized.payload if isinstance(normalized.payload, dict) else {}
        provider_id = str(payload.get("id", "")).strip()
        if not provider_id:
            msg = "provider account create succeeded but response did not include id"
            raise RuntimeError(msg)
        return provider_id

    def _normalize_url(self, value: str) -> str:
        return value.strip().rstrip("/").lower()

    async def _ensure_flow_versions(self) -> None:
        if self.flow_version_ids:
            return
        provisioned_ids = await self._provision_flow_versions_from_starter_projects(self.starter_project_count)
        if not provisioned_ids:
            msg = "no flow versions were provisioned from starter projects"
            raise RuntimeError(msg)
        self.flow_version_ids = provisioned_ids

    async def _provision_flow_versions_from_starter_projects(self, count: int) -> list[str]:
        starter_paths = self._resolve_starter_project_paths(count=count)
        version_ids: list[str] = []
        for starter_path in starter_paths:
            starter_payload = self._load_starter_project_payload(starter_path)
            flow_payload = self._build_flow_create_payload(starter_payload=starter_payload, starter_path=starter_path)
            flow_response = await self._client.post("/api/v1/flows/", json=flow_payload)
            flow_envelope = self._normalize_response(flow_response)
            if flow_envelope.status_code != HTTP_STATUS_CREATED:
                msg = (
                    f"creating flow from starter project failed ({starter_path.name}): "
                    f"status={flow_envelope.status_code} detail={flow_envelope.detail}"
                )
                raise RuntimeError(msg)
            flow_payload_body = flow_envelope.payload if isinstance(flow_envelope.payload, dict) else {}
            flow_id = str(flow_payload_body.get("id", "")).strip()
            if not flow_id:
                msg = f"flow create response missing id for starter project {starter_path.name}"
                raise RuntimeError(msg)
            self.created_flow_ids.add(flow_id)

            snapshot_response = await self._client.post(
                f"/api/v1/flows/{flow_id}/versions/",
                json={"description": f"e2e version from {starter_path.stem}"},
            )
            snapshot_envelope = self._normalize_response(snapshot_response)
            if snapshot_envelope.status_code != HTTP_STATUS_CREATED:
                msg = (
                    f"creating flow version failed for flow {flow_id} ({starter_path.name}): "
                    f"status={snapshot_envelope.status_code} detail={snapshot_envelope.detail}"
                )
                raise RuntimeError(msg)
            snapshot_payload = snapshot_envelope.payload if isinstance(snapshot_envelope.payload, dict) else {}
            version_id = str(snapshot_payload.get("id", "")).strip()
            if not version_id:
                msg = f"flow version create response missing id for flow {flow_id}"
                raise RuntimeError(msg)
            version_ids.append(version_id)
        return version_ids

    def _resolve_starter_project_paths(self, *, count: int) -> list[Path]:
        starter_root = Path(__file__).resolve().parents[3] / "src/backend/base/langflow/initial_setup/starter_projects"
        if not starter_root.is_dir():
            msg = f"starter projects directory not found: {starter_root}"
            raise RuntimeError(msg)
        if self.starter_project_files:
            paths = [starter_root / item for item in self.starter_project_files]
        else:
            paths = sorted(starter_root.glob("*.json"))[:count]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            msg = f"starter project file(s) not found: {missing}"
            raise RuntimeError(msg)
        if len(paths) < count:
            msg = f"not enough starter project files to provision {count} flow versions"
            raise RuntimeError(msg)
        return paths

    def _load_starter_project_payload(self, starter_path: Path) -> dict[str, Any]:
        try:
            raw = starter_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except Exception as exc:
            msg = f"failed to load starter project JSON at {starter_path}: {exc}"
            raise RuntimeError(msg) from exc
        if not isinstance(payload, dict):
            msg = f"starter project payload must be a JSON object: {starter_path}"
            raise TypeError(msg)
        return payload

    def _build_flow_create_payload(self, *, starter_payload: dict[str, Any], starter_path: Path) -> dict[str, Any]:
        data = starter_payload.get("data")
        if not isinstance(data, dict):
            msg = f"starter project is missing object `data`: {starter_path}"
            raise TypeError(msg)
        payload: dict[str, Any] = {
            "name": self._mk_name(starter_path.stem.lower().replace(" ", "_")),
            "description": str(starter_payload.get("description") or f"e2e flow from {starter_path.stem}"),
            "data": data,
            "is_component": bool(starter_payload.get("is_component", False)),
            "endpoint_name": None,
            "tags": starter_payload.get("tags") if isinstance(starter_payload.get("tags"), list) else [],
        }
        for optional_key in ("icon", "icon_bg_color", "gradient", "webhook"):
            if optional_key in starter_payload:
                payload[optional_key] = starter_payload[optional_key]
        return payload

    async def _run_parallel_calls(
        self,
        calls: dict[str, Callable[[], Awaitable[HttpResponseEnvelope]]],
    ) -> dict[str, HttpResponseEnvelope]:
        tasks = {name: asyncio.create_task(call()) for name, call in calls.items()}
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results: dict[str, HttpResponseEnvelope] = {}
        for name, outcome in zip(tasks, gathered, strict=False):
            if isinstance(outcome, Exception):
                results[name] = HttpResponseEnvelope(
                    status_code=HTTP_STATUS_SERVER_ERROR,
                    payload=None,
                    detail=str(outcome),
                )
            else:
                results[name] = outcome
        return results

    def _to_outcome(self, status_code: int) -> str:
        if HTTP_STATUS_OK <= status_code < HTTP_STATUS_MULTIPLE_CHOICES:
            return OUTCOME_SUCCESS
        if status_code == HTTP_STATUS_NOT_FOUND:
            return OUTCOME_HTTP_404
        if status_code == HTTP_STATUS_CONFLICT:
            return OUTCOME_HTTP_409
        if status_code == HTTP_STATUS_UNPROCESSABLE:
            return OUTCOME_HTTP_422
        if status_code >= HTTP_STATUS_SERVER_ERROR:
            return OUTCOME_HTTP_500
        return OUTCOME_FAILURE

    def _mk_name(self, label: str) -> str:
        sanitized = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "-" for ch in label).strip("-")
        self._name_counter += 1
        return f"wxo-api-{sanitized}-{self.run_suffix}-{self._name_counter:04d}"

    def _print_summary(self, results: list[ScenarioResult]) -> None:
        print("\n=== Deployments API E2E Summary ===")
        for result in results:
            status = "PASS" if result.ok else "FAIL"
            expected = ",".join(sorted(result.expected_outcomes))
            print(f"[{status}] {result.name}: expected={expected} got={result.actual_outcome} detail={result.detail}")
        passed = sum(1 for item in results if item.ok)
        failed = len(results) - passed
        print(f"Totals: passed={passed} failed={failed} total={len(results)}")


def _parse_uuid_list(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        return []
    return [str(UUID(value)) for value in values]


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deployments API create/update matrix against /api/v1/deployments."
    )
    parser.add_argument("--base-url", default=os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860"))
    parser.add_argument("--api-key", default=os.getenv("LANGFLOW_API_KEY", ""))
    parser.add_argument("--instance-url", default=os.getenv("WXO_INSTANCE_URL", ""))
    parser.add_argument("--provider-api-key", default=os.getenv("WXO_API_KEY", ""))
    parser.add_argument("--provider-tenant-id", default=os.getenv("WXO_TENANT_ID"))
    parser.add_argument("--provider-key", default=os.getenv("WXO_PROVIDER_KEY", "watsonx-orchestrate"))
    parser.add_argument(
        "--flow-version-ids",
        default=os.getenv("WXO_E2E_FLOW_VERSION_IDS", ""),
        help="Comma-separated flow version UUIDs. First is required; second enables add/remove patch scenario.",
    )
    parser.add_argument("--project-id", default=os.getenv("LANGFLOW_PROJECT_ID"))
    parser.add_argument(
        "--starter-project-files",
        default=os.getenv("WXO_E2E_STARTER_PROJECT_FILES", ""),
        help=(
            "Optional comma-separated starter project filenames from "
            "src/backend/base/langflow/initial_setup/starter_projects."
        ),
    )
    parser.add_argument(
        "--starter-project-count",
        type=int,
        default=int(os.getenv("WXO_E2E_STARTER_PROJECT_COUNT", "2")),
        help="Number of starter projects to provision when --flow-version-ids is not provided.",
    )
    parser.add_argument("--mode", choices=["live", "failpoint", "both"], default=os.getenv("WXO_E2E_MODE", "both"))
    parser.add_argument("--llm", default=os.getenv("WXO_DEFAULT_LLM", DEFAULT_WXO_LLM))
    parser.add_argument(
        "--timeout-secs",
        type=int,
        default=int(os.getenv("WXO_E2E_TIMEOUT_SECS", str(DEFAULT_TIMEOUT_SECS))),
    )
    parser.add_argument(
        "--concurrency-repeat",
        type=int,
        default=int(os.getenv("WXO_CONCURRENCY_REPEAT", str(DEFAULT_CONCURRENCY_REPEAT))),
    )
    parser.add_argument(
        "--test-subset",
        choices=["full", "smoke-connections", "large-tier-s"],
        default=os.getenv("WXO_E2E_TEST_SUBSET", "full"),
        help="Run full matrix, a connection smoke subset, or only large tier-S scenarios.",
    )
    parser.add_argument("--keep-resources", action="store_true")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification.")
    return parser.parse_args()


def _require(value: str, env_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        msg = f"Missing required value for {env_name}"
        raise ValueError(msg)
    return normalized


async def _main() -> int:
    load_dotenv()
    args = _parse_args()
    api_key = _require(args.api_key, "LANGFLOW_API_KEY/--api-key")
    instance_url = _require(args.instance_url, "WXO_INSTANCE_URL/--instance-url")
    provider_api_key = _require(args.provider_api_key, "WXO_API_KEY/--provider-api-key")
    flow_version_ids = _parse_uuid_list(args.flow_version_ids)
    starter_project_files = _parse_csv(args.starter_project_files)
    runner = DeploymentsApiParallelE2E(
        base_url=args.base_url,
        api_key=api_key,
        instance_url=instance_url,
        provider_api_key=provider_api_key,
        provider_tenant_id=args.provider_tenant_id,
        provider_key=args.provider_key,
        mode=args.mode,
        test_subset=args.test_subset,
        keep_resources=args.keep_resources,
        llm=args.llm,
        flow_version_ids=flow_version_ids,
        starter_project_files=starter_project_files,
        starter_project_count=max(1, args.starter_project_count),
        project_id=str(UUID(args.project_id)) if args.project_id else None,
        timeout_secs=args.timeout_secs,
        concurrency_repeat=max(1, args.concurrency_repeat),
        verify_tls=not args.insecure,
    )
    return await runner.run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
