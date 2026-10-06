"""Root SaaS API router.

All SaaS endpoints are mounted under /api/saas/v1/.
This prefix keeps them completely separate from Langflow's /api/v1/ and
/api/v2/ routes so there is zero risk of collision.
"""

from fastapi import APIRouter

from langflow_saas.api import billing, flows, members, orgs, teams

router = APIRouter(prefix="/api/saas/v1")

router.include_router(orgs.router)
router.include_router(members.router)
router.include_router(teams.router)
router.include_router(billing.router)
router.include_router(flows.router)
