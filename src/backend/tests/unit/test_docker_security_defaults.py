import shlex
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PUBLISHED_IMAGES = (
    pytest.param("build_and_push.Dockerfile", "core", id="core"),
    pytest.param("build_and_push.Dockerfile", "full", id="full"),
    pytest.param("build_and_push_backend.Dockerfile", None, id="backend"),
    pytest.param("build_and_push_base.Dockerfile", None, id="base"),
    pytest.param("build_and_push_ep.Dockerfile", None, id="ep"),
    pytest.param("build_and_push_with_extras.Dockerfile", None, id="with-extras"),
)
RESTRICTIVE_RUNTIME_ENV_VARS = frozenset(
    {
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS",
        "LANGFLOW_BLOCK_CODE_INTERPRETER_COMPONENTS",
        "LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS",
        "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK",
        "LANGFLOW_MCP_SERVER_DOCKER_HARDENING",
        "LANGFLOW_MCP_SERVER_INTERPRETER_HARDENING",
        "LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES",
    }
)


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


def _apply_env_instruction(env: dict[str, str], payload: str) -> None:
    assignments = shlex.split(payload)
    if assignments and "=" not in assignments[0]:
        env[assignments[0]] = " ".join(assignments[1:])
        return
    for assignment in assignments:
        key, has_value, value = assignment.partition("=")
        if has_value:
            env[key] = value


def _dockerfile_stages(dockerfile: Path) -> tuple[dict[str, dict[str, str]], dict[str, str], str]:
    """Return inherited stage envs, stage bases, and the final target name."""
    stage_envs: dict[str, dict[str, str]] = {}
    stage_bases: dict[str, str] = {}
    current_stage = ""
    final_stage = ""

    for instruction in _logical_instructions(dockerfile):
        parts = instruction.split(maxsplit=1)
        if len(parts) != 2:
            continue
        keyword, payload = parts
        if keyword.upper() == "FROM":
            tokens = shlex.split(payload)
            base_index = next(index for index, token in enumerate(tokens) if not token.startswith("--"))
            base = tokens[base_index].lower()
            as_index = next((index for index, token in enumerate(tokens) if token.lower() == "as"), None)
            current_stage = tokens[as_index + 1].lower() if as_index is not None else f"__stage_{len(stage_envs)}"
            stage_envs[current_stage] = stage_envs.get(base, {}).copy()
            stage_bases[current_stage] = base
            final_stage = current_stage
            continue
        if keyword.upper() == "ENV" and current_stage:
            _apply_env_instruction(stage_envs[current_stage], payload)

    return stage_envs, stage_bases, final_stage


def _target_env(dockerfile: Path, target: str | None = None) -> dict[str, str]:
    stage_envs, _, final_stage = _dockerfile_stages(dockerfile)
    return stage_envs[(target or final_stage).lower()]


@pytest.mark.parametrize(("dockerfile", "target"), PUBLISHED_IMAGES)
def test_published_images_do_not_force_restrictive_runtime_defaults(dockerfile: str, target: str | None) -> None:
    runtime_env = _target_env(REPO_ROOT / "docker" / dockerfile, target)

    assert runtime_env["LANGFLOW_AUTO_LOGIN"] == "false"
    assert RESTRICTIVE_RUNTIME_ENV_VARS.isdisjoint(runtime_env)


def test_target_env_parses_inheritance_overrides_multiple_assignments_and_continuations(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(
        """FROM builder
ENV LANGFLOW_ALLOW_CUSTOM_COMPONENTS=builder
FROM builder AS runtime
env\tLANGFLOW_ALLOW_CUSTOM_COMPONENTS=false OTHER=first \\
    THIRD=three
FROM runtime AS core
ENV OTHER=core
FROM runtime AS full
ENV OTHER=second LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true
ENV LEGACY value with spaces
""",
        encoding="utf-8",
    )

    assert _target_env(dockerfile, "core") == {
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "false",
        "OTHER": "core",
        "THIRD": "three",
    }
    assert _target_env(dockerfile) == {
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "true",
        "OTHER": "second",
        "THIRD": "three",
        "LEGACY": "value with spaces",
    }


def test_core_and_full_targets_share_one_runtime_defaults_contract() -> None:
    dockerfile = REPO_ROOT / "docker" / "build_and_push.Dockerfile"
    stage_envs, stage_bases, final_stage = _dockerfile_stages(dockerfile)

    assert final_stage == "full"
    assert stage_bases["core"] == "runtime"
    assert stage_bases["full"] == "runtime"
    assert stage_bases["core-builder"] == "core-dependencies"
    assert stage_bases["full-builder"] == "full-dependencies"

    for target in ("core", "full"):
        assert stage_envs[target]["LANGFLOW_AUTO_LOGIN"] == "false"
        assert RESTRICTIVE_RUNTIME_ENV_VARS.isdisjoint(stage_envs[target])

    source = dockerfile.read_text(encoding="utf-8")
    assert source.count("LANGFLOW_AUTO_LOGIN=") == 1
    for key in RESTRICTIVE_RUNTIME_ENV_VARS:
        assert f"{key}=" not in source

    assert not (REPO_ROOT / "docker" / "build_and_push_core.Dockerfile").exists()


def test_public_docker_targets_apply_release_version_overrides() -> None:
    dockerfile = (REPO_ROOT / "docker" / "build_and_push.Dockerfile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "docker-build-v2.yml").read_text(encoding="utf-8")

    assert 'ARG CORE_VERSION=""' in dockerfile
    assert "/app/src/langflow-core/pyproject.toml" in dockerfile
    assert 'ARG MAIN_VERSION=""' in dockerfile
    assert "/app/pyproject.toml" in dockerfile
    assert 'm.version("langflow")' in dockerfile
    assert 'm.version("langflow-core")' in dockerfile
    for variant in ("build_and_push_ep.Dockerfile", "build_and_push_with_extras.Dockerfile"):
        source = (REPO_ROOT / "docker" / variant).read_text(encoding="utf-8")
        assert 'ARG MAIN_VERSION=""' in source
        assert 'ARG CORE_VERSION=""' in source
        assert 'm.version("langflow")' in source
        assert 'm.version("langflow-core")' in source

    assert workflow.count("MAIN_VERSION=${{ needs.determine-main-version.outputs.version }}") == 6
    assert workflow.count("CORE_VERSION=${{ needs.determine-main-version.outputs.version }}") == 6
