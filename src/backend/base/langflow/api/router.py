# Router for base api
from fastapi import APIRouter
from lfx.services.settings.feature_flags import FEATURE_FLAGS

from langflow.api.v1 import (
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
from langflow.api.v2 import workflow_router as workflow_router_v2

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
router_v2.include_router(workflow_router_v2)

router = APIRouter(
    prefix="/api",
)
router.include_router(router_v1)
router.include_router(router_v2)
