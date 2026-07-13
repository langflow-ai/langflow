# Router for base api
from fastapi import APIRouter
from lfx.schema.workflow import WORKFLOW_EXECUTION_RESPONSES
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from lfx.workflow.host import WorkflowHost
from lfx.workflow.router import create_workflow_router

from langflow.api.v1 import (
    a2a_router,
    api_key_router,
    authz_audit_router,
    authz_me_router,
    authz_role_assignments_router,
    authz_roles_router,
    authz_shares_router,
    authz_teams_router,
    chat_router,
    endpoints_router,
    extensions_router,
    files_router,
    flow_events_router,
    flow_version_router,
    flows_router,
    folders_router,
    knowledge_bases_router,
    login_router,
    mcp_projects_router,
    mcp_router,
    memories_router,
    model_options_router,
    models_router,
    monitor_router,
    openai_responses_router,
    projects_router,
    starter_projects_router,
    store_router,
    traces_router,
    users_router,
    validate_router,
    variables_router,
)
from langflow.api.v1.voice_mode import router as voice_mode_router
from langflow.api.v2 import files_router as files_router_v2
from langflow.api.v2 import mcp_router as mcp_router_v2
from langflow.api.v2 import registration_router as registration_router_v2
from langflow.api.v2 import workflow_background_router as workflow_background_router_v2
from langflow.api.v2 import workflow_public_router as workflow_public_router_v2
from langflow.api.v2.workflow_host import LangflowWorkflowHost

router_v1 = APIRouter(
    prefix="/v1",
)

router_v2 = APIRouter(
    prefix="/v2",
)


def include_deployment_router(target_router: APIRouter) -> None:
    """Mount deployment routes only when the deployments feature is enabled."""
    if FEATURE_FLAGS.wxo_deployments:
        from langflow.api.v1.deployments import router as deployment_router

        target_router.include_router(deployment_router)


router_v1.include_router(chat_router)
router_v1.include_router(endpoints_router)
router_v1.include_router(validate_router)
router_v1.include_router(store_router)
router_v1.include_router(flows_router)
router_v1.include_router(flow_events_router)
router_v1.include_router(flow_version_router)
router_v1.include_router(users_router)
router_v1.include_router(api_key_router)
router_v1.include_router(login_router)
router_v1.include_router(variables_router)
router_v1.include_router(files_router)
router_v1.include_router(monitor_router)
router_v1.include_router(traces_router)
router_v1.include_router(folders_router)
router_v1.include_router(projects_router)
router_v1.include_router(starter_projects_router)
router_v1.include_router(knowledge_bases_router)
router_v1.include_router(memories_router)
router_v1.include_router(mcp_router)
router_v1.include_router(voice_mode_router)
router_v1.include_router(mcp_projects_router)
# Always mounted; the per-request guard in langflow.api.v1.a2a returns 404 when
# LANGFLOW_A2A_ENABLED is off, so the route is indistinguishable from "not
# mounted" until the flag is set (mirrors the extensions router below).
router_v1.include_router(a2a_router)
router_v1.include_router(openai_responses_router)
router_v1.include_router(models_router)
router_v1.include_router(model_options_router)
router_v1.include_router(authz_shares_router)
router_v1.include_router(authz_audit_router)
router_v1.include_router(authz_roles_router)
router_v1.include_router(authz_role_assignments_router)
router_v1.include_router(authz_teams_router)
router_v1.include_router(authz_me_router)


# Extension reload is Mode A (local-dev / pip-installed) only.  The route is
# always mounted; a per-request guard in ``langflow.api.v1.extensions`` reads
# the live ``settings.enable_extension_reload`` and returns 404 when the flag
# is off, which means the route is indistinguishable from "not mounted" on
# production deployments that leave it unset.
#
# Mounting unconditionally avoids the import-time / env-file ordering
# coupling: ``langflow.__main__`` imports ``setup_app`` (and hence this
# router module) before ``load_dotenv(env_file)`` runs, so any module-level
# read of ``LANGFLOW_ENABLE_EXTENSION_RELOAD`` would miss the value supplied
# via ``--env-file``.  The runtime guard sees the post-env-file value
# because it executes per-request, after settings have been built.
router_v1.include_router(extensions_router)
include_deployment_router(router_v1)


# Agentic flow execution - lazy import to avoid circular dependency
def _include_agentic_router():
    from langflow.agentic.api.files_router import router as agentic_files_router
    from langflow.agentic.api.router import router as agentic_router
    from langflow.agentic.api.sessions_router import router as agentic_sessions_router

    router_v1.include_router(agentic_router)
    router_v1.include_router(agentic_files_router)
    router_v1.include_router(agentic_sessions_router)


_include_agentic_router()

router_v2.include_router(files_router_v2)
router_v2.include_router(mcp_router_v2)
router_v2.include_router(registration_router_v2)

# POST /api/v2/workflows runs through the shared lfx router bound to the
# langflow host. ``supports_background=True`` lets the background-submit branch
# dispatch to the host; ``auto_register_job_routes=False`` suppresses the lfx
# generic GET-status/POST-stop routes so the langflow durable router below owns
# them (one handler per method+path). ``developer_api_guard=False`` because the
# authenticated langflow v2 router has never carried a developer-api gate; the
# default-off setting would otherwise 403 every authenticated request.
_workflow_host = LangflowWorkflowHost()
assert isinstance(_workflow_host, WorkflowHost)  # noqa: S101
router_v2.include_router(
    create_workflow_router(
        _workflow_host,
        developer_api_guard=False,
        auto_register_job_routes=False,
        responses=WORKFLOW_EXECUTION_RESPONSES,
    )
)
# The langflow-owned durable routes: GET status, POST /stop, GET /{job_id}/events.
router_v2.include_router(workflow_background_router_v2)
router_v2.include_router(workflow_public_router_v2)

router = APIRouter(
    prefix="/api",
)
router.include_router(router_v1)
router.include_router(router_v2)
