import shlex
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
EXPECTED_RUNTIME_ENV = {
    "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "false",
    "LANGFLOW_BLOCK_CODE_INTERPRETER_COMPONENTS": "true",
    "LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS": "true",
    "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK": "false",
    "LANGFLOW_MCP_SERVER_DOCKER_HARDENING": "true",
    "LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING": "true",
    "LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES": "mcp-proxy,lfx",
}


def _logical_instructions(dockerfile: Path) -> list[str]:
    """Collapse Dockerfile continuations while ignoring blank and comment lines."""
    instructions: list[str] = []
    current = ""
    for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            current += f"{line[:-1].rstrip()} "
            continue
        current += line
        instructions.append(current)
        current = ""
    if current:
        instructions.append(current)
    return instructions


def _final_stage_env(dockerfile: Path) -> dict[str, str]:
    """Return active ENV assignments from the final image stage."""
    instructions = _logical_instructions(dockerfile)
    final_stage_start = max(
        index for index, instruction in enumerate(instructions) if instruction.split(maxsplit=1)[0].upper() == "FROM"
    )
    env: dict[str, str] = {}
    for instruction in instructions[final_stage_start + 1 :]:
        parts = instruction.split(maxsplit=1)
        if len(parts) != 2 or parts[0].upper() != "ENV":
            continue
        payload = parts[1]
        assignments = shlex.split(payload)
        if assignments and "=" not in assignments[0]:
            env[assignments[0]] = " ".join(assignments[1:])
            continue
        for assignment in assignments:
            key, has_value, value = assignment.partition("=")
            if has_value:
                env[key] = value
    return env


@pytest.mark.parametrize("dockerfile", PUBLISHED_DOCKERFILES)
def test_published_images_enable_multi_tenant_hardening(dockerfile: str) -> None:
    runtime_env = _final_stage_env(REPO_ROOT / "docker" / dockerfile)

    assert {key: runtime_env.get(key) for key in EXPECTED_RUNTIME_ENV} == EXPECTED_RUNTIME_ENV


def test_final_stage_env_parses_overrides_multiple_assignments_and_continuations(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        """FROM builder
ENV LANGFLOW_ALLOW_CUSTOM_COMPONENTS=builder
from\truntime
env\tLANGFLOW_ALLOW_CUSTOM_COMPONENTS=false OTHER=first \\
    THIRD=three
ENV OTHER=second LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true
ENV LEGACY value with spaces
""",
        encoding="utf-8",
    )

    assert _final_stage_env(dockerfile) == {
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "true",
        "OTHER": "second",
        "THIRD": "three",
        "LEGACY": "value with spaces",
    }
