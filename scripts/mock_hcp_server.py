# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.111",
#   "uvicorn[standard]>=0.29",
# ]
# ///

"""Mock HCP (Hynix Cloud Platform) roles API server.

Simulates http://hcp-api.com/v1/projects/{project}/roles for local testing.

Usage:
    uv run scripts/mock_hcp_server.py
"""

import uvicorn
from fastapi import FastAPI

PORT = 9001

# Project → allowed employees (mirrors real HCP API response format)
HCP_PROJECT_ROLES: dict[str, dict] = {
    "project-a": {
        "managers": ["EMP001"],
        "deployApprovers": ["EMP002"],
        "developers": ["EMP003", "EMP004", "EMP005"],
    },
    "project-b": {
        "managers": ["EMP001"],
        "deployApprovers": ["EMP002"],
        "developers": ["EMP006", "EMP007", "EMP008"],
    },
}

app = FastAPI(title="Mock HCP Roles API")


@app.get("/v1/projects/{project_name}/roles")
async def hcp_roles(project_name: str):
    """Return project roles in HCP API format."""
    roles = HCP_PROJECT_ROLES.get(
        project_name,
        {"managers": [], "deployApprovers": [], "developers": []},
    )
    return {"response": roles}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print(f"\n  Mock HCP Roles API running on http://localhost:{PORT}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
