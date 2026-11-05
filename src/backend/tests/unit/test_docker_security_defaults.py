import re
import shlex
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]
PUBLISHED_IMAGES = (
    pytest.param("build_and_push.Dockerfile", "base", id="base"),
    pytest.param("build_and_push.Dockerfile", "full", id="full"),
    pytest.param("build_and_push.Dockerfile", "full-bundles", id="full-bundles"),
    pytest.param("build_and_push_backend.Dockerfile", None, id="backend"),
    pytest.param("build_and_push_ep.Dockerfile", None, id="ep"),
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


def _stage_instructions(dockerfile: Path) -> dict[str, list[str]]:
    """Group logical instructions by their named Docker build stage."""
    stages: dict[str, list[str]] = {}
    current_stage = ""
    for instruction in _logical_instructions(dockerfile):
        tokens = shlex.split(instruction)
        if tokens[0].upper() == "FROM":
            as_index = next((index for index, token in enumerate(tokens) if token.upper() == "AS"), None)
            current_stage = tokens[as_index + 1].lower() if as_index is not None else f"__stage_{len(stages)}"
            stages[current_stage] = []
        if current_stage:
            stages[current_stage].append(instruction)
    return stages


def _inherited_instructions(dockerfile: Path, target: str | None = None) -> list[str]:
    """Return a target's instructions after those inherited from its base stages."""
    stages = _stage_instructions(dockerfile)
    _, stage_bases, final_stage = _dockerfile_stages(dockerfile)
    ancestors = [target or final_stage]
    while stage_bases[ancestors[-1]] in stages:
        ancestors.append(stage_bases[ancestors[-1]])
    return [instruction for stage in reversed(ancestors) for instruction in stages[stage]]


def test_lxml_rebuild_ignores_cached_wheels_and_existing_installations() -> None:
    """Require an uncached source reinstall rather than trusting cached lxml wheels."""
    helper = REPO_ROOT / "docker" / "build_lxml.sh"
    tokens = shlex.split(" ".join(_logical_instructions(helper)))
    assert {"--no-cache", "--no-config", "--no-deps", "--force-reinstall", "--no-binary"}.issubset(tokens)
    assert tokens[tokens.index("--no-binary") + 1] == "lxml"


@pytest.mark.parametrize(
    ("dockerfile", "final_builders"),
    [
        ("build_and_push.Dockerfile", ("base-builder", "full-builder", "full-bundles-builder")),
        ("build_and_push_backend.Dockerfile", ("builder",)),
        ("build_and_push_ep.Dockerfile", ("builder",)),
    ],
)
def test_published_image_builders_rebuild_lxml_after_dependency_installs(
    dockerfile: str, final_builders: tuple[str, ...]
) -> None:
    """Keep cached or restored wheels from bypassing the final lxml rebuild."""
    path = REPO_ROOT / "docker" / dockerfile
    stages = _stage_instructions(path)

    for final_builder in final_builders:
        builder_instructions = _inherited_instructions(path, final_builder)
        assert any(
            instruction.startswith("COPY ") and "docker/build_lxml.sh /tmp/build_lxml.sh" in instruction
            for instruction in builder_instructions
        )
        builder_tokens = shlex.split(" ".join(builder_instructions))
        assert {"libxml2-devel", "libxslt-devel"}.issubset(builder_tokens)
        instructions = "\n".join(stages[final_builder])
        rebuild = instructions.rfind("sh /tmp/build_lxml.sh")
        assert rebuild >= 0, f"{dockerfile} {final_builder} must rebuild lxml"
        installs = [
            instructions.rfind(command)
            for command in ("uv sync", "uv pip install", "python3.14 /tmp/install_release_wheels.py")
        ]
        assert max(installs) >= 0, f"{dockerfile} {final_builder} must install dependencies"
        assert rebuild > max(installs), f"{dockerfile} {final_builder} rebuilds lxml before its final install"


@pytest.mark.parametrize(("dockerfile", "target"), PUBLISHED_IMAGES)
def test_published_images_verify_lxml_after_copying_the_environment(dockerfile: str, target: str | None) -> None:
    """Check shared XML libraries and exercise lxml in every assembled runtime."""
    path = REPO_ROOT / "docker" / dockerfile
    instructions = _inherited_instructions(path, target)
    runtime_tokens = shlex.split(" ".join(instructions))
    assert {"libxml2", "libxslt"}.issubset(runtime_tokens)
    assert any(
        instruction.startswith("COPY ")
        and "--chown=1000:0" in instruction
        and "scripts/ci/verify_lxml_runtime.py /tmp/verify_lxml_runtime.py" in instruction
        for instruction in instructions
    )

    source = "\n".join(instructions)
    venv_copy = max(
        source.rfind(instruction)
        for instruction in instructions
        if instruction.startswith("COPY ") and instruction.endswith("/app/.venv /app/.venv")
    )
    verification = source.rfind("/app/.venv/bin/python /tmp/verify_lxml_runtime.py")
    removal = max(source.rfind("rm /tmp/verify_lxml_runtime.py"), source.rfind("rm -f /tmp/verify_lxml_runtime.py"))
    assert verification > venv_copy
    assert removal > verification


def test_backend_image_lxml_pin_matches_the_release_lock() -> None:
    """Keep the unlocked backend resolver on the same lxml version as other images."""
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {package["version"] for package in lock["package"] if package["name"] == "lxml"}
    assert len(versions) == 1
    pinned_requirement = f"lxml=={versions.pop()}"
    instructions = _logical_instructions(REPO_ROOT / "docker" / "build_and_push_backend.Dockerfile")
    assert any(
        "uv pip install" in instruction and pinned_requirement in shlex.split(instruction)
        for instruction in instructions
    )


@pytest.mark.parametrize(
    "dockerfile",
    sorted(
        path
        for path in (REPO_ROOT / "docker").rglob("*Dockerfile")
        # The standalone frontend runs Nginx and does not consume backend auth settings.
        if path != REPO_ROOT / "docker" / "frontend" / "build_and_push_frontend.Dockerfile"
    ),
    ids=lambda path: str(path.relative_to(REPO_ROOT / "docker")),
)
def test_backend_docker_images_disable_auto_login_by_default(dockerfile: Path) -> None:
    assert _target_env(dockerfile).get("LANGFLOW_AUTO_LOGIN") == "false"


def test_lfx_docker_image_disables_auto_login_by_default() -> None:
    assert _target_env(REPO_ROOT / "src/lfx/docker/Dockerfile").get("LANGFLOW_AUTO_LOGIN") == "false"


@pytest.mark.parametrize(("dockerfile", "target"), PUBLISHED_IMAGES)
def test_published_images_use_writable_runtime_home(dockerfile: str, target: str | None) -> None:
    assert _target_env(REPO_ROOT / "docker" / dockerfile, target).get("HOME") == "/app/data"


def test_consolidated_and_lfx_images_create_writable_runtime_home() -> None:
    sources = (
        (REPO_ROOT / "docker" / "build_and_push.Dockerfile").read_text(encoding="utf-8"),
        (REPO_ROOT / "src" / "lfx" / "docker" / "Dockerfile").read_text(encoding="utf-8"),
    )
    for source in sources:
        assert "mkdir -p /app/data" in source
        assert "chown -R 1000:0 /app/data" in source
        assert "chmod -R g+rwX /app/data" in source


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
FROM runtime AS base
ENV OTHER=base
FROM runtime AS full
ENV OTHER=second LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true
ENV LEGACY value with spaces
""",
        encoding="utf-8",
    )

    assert _target_env(dockerfile, "base") == {
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "false",
        "OTHER": "base",
        "THIRD": "three",
    }
    assert _target_env(dockerfile) == {
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "true",
        "OTHER": "second",
        "THIRD": "three",
        "LEGACY": "value with spaces",
    }


def test_base_and_full_targets_share_one_runtime_defaults_contract() -> None:
    dockerfile = REPO_ROOT / "docker" / "build_and_push.Dockerfile"
    stage_envs, stage_bases, final_stage = _dockerfile_stages(dockerfile)

    assert final_stage == "full"
    assert stage_bases["base"] == "runtime"
    assert stage_bases["full"] == "runtime"
    assert stage_bases["base-builder"] == "base-dependencies"
    assert stage_bases["full-builder"] == "full-dependencies"

    for target in ("base", "full"):
        assert stage_envs[target]["LANGFLOW_AUTO_LOGIN"] == "false"
        assert RESTRICTIVE_RUNTIME_ENV_VARS.isdisjoint(stage_envs[target])

    source = dockerfile.read_text(encoding="utf-8")
    assert source.count("LANGFLOW_AUTO_LOGIN=") == 1
    for key in RESTRICTIVE_RUNTIME_ENV_VARS:
        assert f"{key}=" not in source

    assert not (REPO_ROOT / "docker" / "build_and_push_base.Dockerfile").exists()
    assert not (REPO_ROOT / "docker" / "build_and_push_with_extras.Dockerfile").exists()


def test_public_docker_targets_apply_release_version_overrides() -> None:
    dockerfile = (REPO_ROOT / "docker" / "build_and_push.Dockerfile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "docker-build-v2.yml").read_text(encoding="utf-8")

    assert 'ARG BASE_VERSION=""' in dockerfile
    assert "/app/src/backend/base/pyproject.toml" in dockerfile
    assert 'ARG MAIN_VERSION=""' in dockerfile
    assert "/app/pyproject.toml" in dockerfile
    assert 'm.version("langflow")' in dockerfile
    assert 'm.version("langflow-base")' in dockerfile
    source = (REPO_ROOT / "docker" / "build_and_push_ep.Dockerfile").read_text(encoding="utf-8")
    assert 'ARG MAIN_VERSION=""' in source
    assert 'ARG BASE_VERSION=""' in source
    assert 'm.version("langflow")' in source
    assert 'm.version("langflow-base")' in source

    assert workflow.count("MAIN_VERSION=${{ needs.determine-main-version.outputs.version }}") == 6
    assert workflow.count("BASE_VERSION=${{ needs.determine-main-version.outputs.version }}") == 6
    assert workflow.count("BASE_VERSION=${{ needs.determine-base-version.outputs.version }}") == 2


def test_full_target_checks_only_default_workspace_distributions() -> None:
    dockerfile = (REPO_ROOT / "docker" / "build_and_push.Dockerfile").read_text(encoding="utf-8")

    assert 'required = {"langflow", "langflow-base"}' in dockerfile
    assert '{"torch", "torchvision"} & names' in dockerfile


def test_published_images_pin_hardened_package_managers() -> None:
    """Keep the installed package-manager versions and dependency checks aligned."""
    install_script = (REPO_ROOT / "docker" / "install_hardened_npm.sh").read_text(encoding="utf-8")

    assert 'NPM_VERSION="12.0.2"' in install_script
    assert 'npm install --global "npm@${NPM_VERSION}"' in install_script
    assert 'actual_npm_version="$(npm --version)"' in install_script
    assert 'if [ "$actual_npm_version" != "$NPM_VERSION" ]; then' in install_script

    for variable, version, package, validation_entry in (
        ("IP_ADDRESS_VERSION", "10.7.4", "ip-address", '"ip-address": "10.7.4"'),
        ("BRACE_EXPANSION_VERSION", "5.0.12", "brace-expansion", '"brace-expansion": "5.0.12"'),
        ("TAR_VERSION", "7.5.22", "tar", 'tar: "7.5.22"'),
        ("UNDICI_VERSION", "6.29.1", "undici", 'undici: "6.29.1"'),
        ("POSTCSS_SELECTOR_PARSER_VERSION", "7.1.6", "postcss-selector-parser", '"postcss-selector-parser": "7.1.6"'),
        ("GLOB_VERSION", "14.0.2", "glob", 'glob: "14.0.2"'),
        ("MINIMATCH_VERSION", "11.0.1", "minimatch", 'minimatch: "11.0.1"'),
        ("PATH_SCURRY_VERSION", "3.0.0", "path-scurry", '"path-scurry": "3.0.0"'),
        (
            "NONRECURSIVE_GLOB_MATCH_VERSION",
            "1.0.1",
            "@isaacs/nonrecursive-glob-match",
            '"@isaacs/nonrecursive-glob-match": "1.0.1"',
        ),
    ):
        assert f'{variable}="{version}"' in install_script
        assert f'"{package}@${{{variable}}}"' in install_script
        assert validation_entry in install_script

    assert (
        "for package in ip-address brace-expansion tar undici postcss-selector-parser "
        "glob minimatch path-scurry @isaacs/nonrecursive-glob-match; do"
    ) in install_script
    for validation_entry in (
        'sigstore: "5.0.0"',
        '"@sigstore/core": "4.0.1"',
        '"tinyglobby/node_modules/picomatch": "4.0.5"',
    ):
        assert validation_entry in install_script
    assert "npm ls --global --all --omit=dev" in install_script
    assert 'rm -rf "$npm_cache" /tmp/node-compile-cache' in install_script

    for dockerfile in (
        "build_and_push.Dockerfile",
        "build_and_push_backend.Dockerfile",
        "build_and_push_ep.Dockerfile",
    ):
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


def _image_uid(dockerfile: str) -> int:
    """The numeric uid the image's named runtime user is created with."""
    source = (REPO_ROOT / "docker" / dockerfile).read_text(encoding="utf-8")
    match = re.search(r"useradd\b[^\n]*?(?:--uid|-u)[= ](\d+)", source)
    assert match is not None, f"{dockerfile} no longer creates its runtime user with an explicit uid"
    return int(match.group(1))


def test_the_listener_deployment_names_a_uid_and_not_only_non_root() -> None:
    """`runAsNonRoot` alone never starts a container whose image USER is a name.

    The kubelet cannot prove that the name `user` is not root, so the pod stops
    at `CreateContainerConfigError: image has non-numeric user`. The manifest has
    to say which uid, and that uid has to be the one the images actually create -
    which is the drift this test exists to catch.
    """
    import yaml

    manifest = yaml.safe_load(
        (REPO_ROOT / "deploy" / "listeners" / "kubernetes-deployment.yaml").read_text(encoding="utf-8")
    )
    containers = manifest["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    security_context = containers[0]["securityContext"]

    assert security_context["runAsNonRoot"] is True
    runtime_uid = security_context["runAsUser"]
    assert isinstance(runtime_uid, int)
    assert runtime_uid != 0

    for dockerfile in ("build_and_push.Dockerfile", "build_and_push_backend.Dockerfile"):
        assert _image_uid(dockerfile) == runtime_uid, f"{dockerfile} runs as a different uid than the manifest asks for"


@pytest.mark.parametrize(
    "dockerfile",
    ["build_and_push.Dockerfile", "build_and_push_backend.Dockerfile", "build_and_push_ep.Dockerfile"],
)
def test_published_node_versions_include_brotli_security_fix(dockerfile: str) -> None:
    """Reject Node runtimes that still bundle the vulnerable Brotli decoder."""
    versions = [
        instruction.split("=", 1)[1]
        for instruction in _logical_instructions(REPO_ROOT / "docker" / dockerfile)
        if instruction.startswith("ARG NODE_VERSION=")
    ]
    assert len(versions) == 1
    version = tuple(int(part) for part in versions[0].split("."))
    fixed = {22: (22, 23, 4), 24: (24, 22, 1), 26: (26, 12, 1)}
    assert version[0] in fixed, "Verify the Brotli fix before changing Node release lines"
    assert version >= fixed[version[0]], f"{dockerfile} still ships CVE-2026-111497"


def test_frontend_runtime_uses_patched_base_and_non_root_runtime() -> None:
    """Keep OS updates privileged and the frontend runtime on its patched image."""
    dockerfile = REPO_ROOT / "docker/frontend/build_and_push_frontend.Dockerfile"
    _, bases, final_stage = _dockerfile_stages(dockerfile)
    image = re.fullmatch(
        r"nginxinc/nginx-unprivileged:(\d+)\.(\d+)\.(\d+)-trixie@sha256:[0-9a-f]{64}",
        bases[final_stage],
    )
    assert image is not None, "Pin the patched non-Perl Trixie runtime by digest"
    assert tuple(int(part) for part in image.groups()) >= (1, 30, 5)

    instructions = _stage_instructions(dockerfile)[final_stage]
    upgrades = [
        index
        for index, instruction in enumerate(instructions)
        if instruction.startswith("RUN ") and "apt-get upgrade" in instruction
    ]
    assert len(upgrades) == 1
    upgrade_index = upgrades[0]
    commands = [shlex.split(command) for command in instructions[upgrade_index][4:].split("&&")]
    update = commands.index(["apt-get", "update"])
    upgrade = commands.index(["apt-get", "upgrade", "-y"])
    cleanup = commands.index(["rm", "-rf", "/var/lib/apt/lists/*"])
    assert update < upgrade < cleanup
    users_before_upgrade = [
        instruction for instruction in instructions[:upgrade_index] if instruction.startswith("USER ")
    ]
    assert users_before_upgrade[-1] == "USER root"

    copies = [index for index, instruction in enumerate(instructions) if instruction.startswith("COPY ")]
    assert copies
    for index in copies:
        users = [instruction for instruction in instructions[:index] if instruction.startswith("USER ")]
        assert users[-1] == "USER nginx"
    assert [instruction for instruction in instructions if instruction.startswith("USER ")][-1] == "USER nginx"
