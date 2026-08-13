import shlex
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]
PUBLISHED_DOCKERFILES = (
    "build_and_push.Dockerfile",
    "build_and_push_backend.Dockerfile",
    "build_and_push_base.Dockerfile",
    "build_and_push_ep.Dockerfile",
    "build_and_push_with_extras.Dockerfile",
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


def _final_stage_instructions(dockerfile: Path) -> list[str]:
    """Return the logical instructions from the final image stage."""
    instructions = _logical_instructions(dockerfile)
    final_stage_start = max(
        index for index, instruction in enumerate(instructions) if instruction.split(maxsplit=1)[0].upper() == "FROM"
    )
    return instructions[final_stage_start + 1 :]


def _final_stage_env(dockerfile: Path) -> dict[str, str]:
    """Return active ENV assignments from the final image stage."""
    env: dict[str, str] = {}
    for instruction in _final_stage_instructions(dockerfile):
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
def test_published_images_use_writable_runtime_home(dockerfile: str) -> None:
    dockerfile_path = REPO_ROOT / "docker" / dockerfile
    runtime_env = _final_stage_env(dockerfile_path)
    runtime_instructions = _final_stage_instructions(dockerfile_path)

    assert runtime_env.get("HOME") == "/app/data"
    assert any(
        instruction.startswith("RUN ")
        and "mkdir -p /app/data /app/langflow" in instruction
        and "chown -R 1000:0 /app/data /app/langflow" in instruction
        and "chmod -R g+rwX /app/data /app/langflow" in instruction
        for instruction in runtime_instructions
    )


def test_lfx_image_uses_writable_runtime_home() -> None:
    dockerfile_path = REPO_ROOT / "src" / "lfx" / "docker" / "Dockerfile"
    runtime_env = _final_stage_env(dockerfile_path)
    runtime_instructions = _final_stage_instructions(dockerfile_path)

    assert runtime_env.get("HOME") == "/app/data"
    assert any(
        instruction.startswith("RUN ")
        and "mkdir -p /app/data" in instruction
        and "chown -R 1000:0 /app/data" in instruction
        and "chmod -R g+rwX /app/data" in instruction
        for instruction in runtime_instructions
    )


@pytest.mark.parametrize("dockerfile", PUBLISHED_DOCKERFILES)
def test_published_images_do_not_force_restrictive_runtime_defaults(dockerfile: str) -> None:
    runtime_env = _final_stage_env(REPO_ROOT / "docker" / dockerfile)

    assert runtime_env["LANGFLOW_AUTO_LOGIN"] == "false"
    assert RESTRICTIVE_RUNTIME_ENV_VARS.isdisjoint(runtime_env)


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


def test_published_images_pin_hardened_package_managers() -> None:
    install_script = (REPO_ROOT / "docker" / "install_hardened_npm.sh").read_text(encoding="utf-8")

    assert 'NPM_VERSION="12.0.2"' in install_script
    assert 'npm install --global "npm@${NPM_VERSION}"' in install_script
    assert 'actual_npm_version="$(npm --version)"' in install_script
    assert 'if [ "$actual_npm_version" != "$NPM_VERSION" ]; then' in install_script

    for variable, version, package, validation_entry in (
        ("IP_ADDRESS_VERSION", "10.3.1", "ip-address", '"ip-address": "10.3.1"'),
        ("BRACE_EXPANSION_VERSION", "5.0.9", "brace-expansion", '"brace-expansion": "5.0.9"'),
        ("TAR_VERSION", "7.5.22", "tar", 'tar: "7.5.22"'),
        ("UNDICI_VERSION", "6.28.0", "undici", 'undici: "6.28.0"'),
    ):
        assert f'{variable}="{version}"' in install_script
        assert f'"{package}@${{{variable}}}"' in install_script
        assert validation_entry in install_script

    assert "for package in ip-address brace-expansion tar undici; do" in install_script
    for validation_entry in (
        'sigstore: "5.0.0"',
        '"@sigstore/core": "4.0.1"',
        '"tinyglobby/node_modules/picomatch": "4.0.5"',
    ):
        assert validation_entry in install_script
    assert "npm ls --global --all --omit=dev" in install_script
    assert 'rm -rf "$npm_cache" /tmp/node-compile-cache' in install_script

    for dockerfile in PUBLISHED_DOCKERFILES:
        source = (REPO_ROOT / "docker" / dockerfile).read_text(encoding="utf-8")
        assert 'python3.14 -m pip install --no-cache-dir --upgrade "pip==26.2.1"' in source
        assert "sh /tmp/install_hardened_npm.sh" in source

    backend_project = tomllib.loads(
        (REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert "pip>=26.2.1,<27.0.0" in backend_project["project"]["dependencies"]

    lockfile = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_pip_versions = {package["version"] for package in lockfile["package"] if package["name"] == "pip"}
    assert locked_pip_versions == {"26.2.1"}
