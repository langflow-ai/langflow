from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PUBLISHED_DOCKERFILES = (
    "build_and_push.Dockerfile",
    "build_and_push_backend.Dockerfile",
    "build_and_push_base.Dockerfile",
    "build_and_push_ep.Dockerfile",
    "build_and_push_with_extras.Dockerfile",
)


@pytest.mark.parametrize("dockerfile", PUBLISHED_DOCKERFILES)
def test_published_images_enable_mcp_hardening(dockerfile: str) -> None:
    content = (REPO_ROOT / "docker" / dockerfile).read_text(encoding="utf-8")

    assert "ENV LANGFLOW_MCP_SERVER_DOCKER_HARDENING=true" in content
    assert "ENV LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING=true" in content
