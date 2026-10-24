"""The quickstart database must require its password and stay on the private Compose network."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = [
    REPO_ROOT / "docker_example" / "docker-compose.yml",
    REPO_ROOT / "docker_example" / "pre.docker-compose.yml",
]
TEST_PASSWORD = "test-only-password"  # noqa: S105  # pragma: allowlist secret
RESERVED_PASSWORD = "test-only-/password#with?reserved"  # noqa: S105  # pragma: allowlist secret
DOCKER = shutil.which("docker")
IMAGE_STARTUP = {
    "docker-compose.yml": {"entrypoint": [], "command": ["langflow", "run"]},
    "pre.docker-compose.yml": {
        "entrypoint": ["python", "-m", "langflow", "run"],
        "command": ["--host", "0.0.0.0", "--port", "7860"],  # noqa: S104 - image default
    },
}

pytestmark = pytest.mark.skipif(DOCKER is None, reason="Docker Compose is required")


def _compose_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["LANGFLOW_SUPERUSER_PASSWORD"] = TEST_PASSWORD
    return environment


def _compose_config(compose_file: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env_file = tmp_path / "empty.env"
    env_file.touch()
    return subprocess.run(  # noqa: S603 - arguments are repository-controlled
        [DOCKER, "compose", "--env-file", str(env_file), "-f", str(compose_file), "config", "--format", "json"],
        cwd=REPO_ROOT,
        env=_compose_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def _effective_command(compose_file: Path, langflow: dict) -> list[str]:
    image = IMAGE_STARTUP[compose_file.name]
    entrypoint = langflow["entrypoint"] if langflow.get("entrypoint") is not None else image["entrypoint"]
    command = langflow.get("command", image["command"])
    return [*entrypoint, *command]


@pytest.mark.parametrize("compose_file", COMPOSE_FILES, ids=lambda path: path.name)
def test_postgres_password_is_required(compose_file: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    result = _compose_config(compose_file, tmp_path)

    assert result.returncode != 0
    assert "POSTGRES_PASSWORD" in result.stderr


@pytest.mark.parametrize("compose_file", COMPOSE_FILES, ids=lambda path: path.name)
def test_postgres_stays_internal_and_shares_the_required_password(
    compose_file: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", TEST_PASSWORD)
    result = _compose_config(compose_file, tmp_path)

    assert result.returncode == 0, result.stderr
    config = yaml.safe_load(result.stdout)
    postgres = config["services"]["postgres"]
    assert "ports" not in postgres
    assert postgres["environment"]["POSTGRES_PASSWORD"] == TEST_PASSWORD


@pytest.mark.parametrize("compose_file", COMPOSE_FILES, ids=lambda path: path.name)
def test_startup_percent_encodes_reserved_password_characters(compose_file: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", RESERVED_PASSWORD)
    result = _compose_config(compose_file, tmp_path)

    assert result.returncode == 0, result.stderr
    config = yaml.safe_load(result.stdout)
    langflow = config["services"]["langflow"]
    assert langflow["environment"]["POSTGRES_PASSWORD"] == RESERVED_PASSWORD
    assert config["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"] == RESERVED_PASSWORD
    command = _effective_command(compose_file, langflow)
    assert command[:2] == ["/bin/sh", "-c"]
    command[-1] = command[-1].replace("$$", "$")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    langflow_stub = bin_dir / "langflow"
    langflow_stub.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$LANGFLOW_DATABASE_URL\"\nprintf '%s\\n' \"$@\"\n", encoding="utf-8"
    )
    langflow_stub.chmod(0o755)
    python_stub = bin_dir / "python"
    python_stub.write_text(
        f'#!/bin/sh\nif [ "$1" = "-c" ]; then exec "{sys.executable}" "$@"; fi\n'
        "printf '%s\\n' \"$LANGFLOW_DATABASE_URL\"\nprintf '%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    python_stub.chmod(0o755)
    environment = _compose_environment()
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment['PATH']}"
    startup = subprocess.run(  # noqa: S603 - the command comes from the repository Compose file
        command,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert startup.returncode == 0, startup.stderr
    output = startup.stdout.splitlines()
    expected_arguments = (
        ["-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]  # noqa: S104 - required binding
        if compose_file.name == "pre.docker-compose.yml"
        else ["run"]
    )
    assert output[1:] == expected_arguments
    database_url = output[0]
    expected_url = "postgresql://langflow:test-only-" + "%2Fpassword%23with%3Freserved@postgres:5432/langflow"
    assert database_url == expected_url
    parsed_url = urlsplit(database_url)
    assert (parsed_url.hostname, parsed_url.port) == ("postgres", 5432)
    assert unquote(parsed_url.password) == RESERVED_PASSWORD
