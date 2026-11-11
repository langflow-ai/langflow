"""Exercise stable Docker alias ordering and complete registry tag reads."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import docker_latest_tags

SCRIPT_DIR = Path(__file__).resolve().parent
WORKFLOW_PATH = SCRIPT_DIR.parents[1] / ".github" / "workflows" / "docker-build-v2.yml"
TAG_URL = "https://hub.docker.com/v2/namespaces/langflowai/repositories/langflow/tags?page_size=100"
NEXT_URL = f"{TAG_URL}&page=2"
AUTH_URL = "https://hub.docker.com/v2/auth/token"
AUTH_ENV = {"DOCKERHUB_USERNAME": "fixture-user", "DOCKERHUB_TOKEN": "fixture-password-secret"}


@pytest.mark.parametrize(
    ("candidate", "published", "expected"),
    [
        ("1.12.10", ["1.12.9", "1.13.1"], False),
        ("1.13.2", ["1.12.10", "1.13.1"], True),
        ("1.13.1", ["1.13.1"], True),
        ("1.12.10", ["1.12.9"], True),
        ("1.9.10", ["1.10.0"], False),
        ("2.0.0", ["1.99.99"], True),
        ("1.0.0", [], True),
    ],
)
def test_latest_never_moves_to_an_older_stable_version(candidate, published, expected):
    assert docker_latest_tags.should_update_latest(candidate, published) is expected


@pytest.mark.parametrize("candidate", ["1.14.0rc1", "1.14.0.dev1", "1.14.0.post1", "1.14.0+local", "", "latest"])
def test_non_stable_candidates_cannot_be_latest(candidate):
    assert docker_latest_tags.should_update_latest(candidate, ["1.13.1"]) is False


def test_only_plain_stable_image_tags_affect_latest():
    tags = [
        "1.13.1",
        "1.14.0rc1",
        "2.0.0.dev1",
        "2.0.0.post1",
        "2.0.0+local",
        "2.0.0-amd64",
        "2.0.0-arm64",
        "base-2.0.0",
        "latest",
        "base-latest",
        "unrecognized",
        "",
    ]
    assert docker_latest_tags.should_update_latest("1.13.2", tags) is True


def test_base_and_full_images_have_separate_stable_versions():
    tags = ["1.14.0", "base-1.13.1", "base-1.15.0rc1", "base-1.15.0-amd64", "base-latest"]
    assert docker_latest_tags.should_update_latest("1.13.2", tags, prefix="base-") is True
    assert docker_latest_tags.should_update_latest("1.12.10", tags, prefix="base-") is False
    assert docker_latest_tags.should_update_latest("1.13.2", tags) is False


@pytest.mark.parametrize(
    ("prefix", "tags", "expected"), [("", "1.13.1\n1.12.9\n", "false"), ("base-", "base-1.12.9\n1.13.1\n", "true")]
)
def test_cli_reads_registry_tags_from_stdin(prefix, tags, expected, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["docker_latest_tags.py", "1.12.10", "--prefix", prefix])
    monkeypatch.setattr(sys, "stdin", io.StringIO(tags))
    docker_latest_tags.main()
    assert capsys.readouterr().out.strip() == expected


def _registry_env(tmp_path: Path, pages: dict[str, tuple[int, object]]) -> dict[str, str]:
    if shutil.which("bash") is None or shutil.which("jq") is None:
        pytest.skip("registry tag reads require bash and jq")
    fixtures = tmp_path / "pages.json"
    fixtures.write_text(json.dumps(pages), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "url = next(value for value in args if value.startswith('https://'))\n"
        "calls_path = Path(os.environ['DOCKER_TAG_CALLS'])\n"
        "calls = json.loads(calls_path.read_text()) if calls_path.exists() else []\n"
        "calls.append({'url': url, 'args': args})\n"
        "calls_path.write_text(json.dumps(calls))\n"
        "if '--data-binary' in args:\n"
        "    sys.stdin.read()\n"
        "pages = json.loads(Path(os.environ['DOCKER_TAG_FIXTURES']).read_text())\n"
        "status, body = pages.get(url, [404, {}])\n"
        "Path(args[args.index('--output') + 1]).write_text(json.dumps(body))\n"
        "print(status, end='')\n",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    uv = bin_dir / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "index = sys.argv.index('python')\n"
        "os.execv(sys.executable, [sys.executable, *sys.argv[index + 1:]])\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_TAG_FIXTURES": str(fixtures),
        "DOCKER_TAG_CALLS": str(tmp_path / "calls.json"),
        "DOCKERHUB_USERNAME": "",
        "DOCKERHUB_TOKEN": "",
    }


def _fetch_tags(
    tmp_path: Path,
    pages: dict[str, tuple[int, object]],
    *,
    all_pages: bool = True,
    credentials: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**_registry_env(tmp_path, pages), **(credentials or {})}
    args = [shutil.which("bash"), str(SCRIPT_DIR / "fetch_docker_hub_tags.sh"), "langflowai/langflow"]
    if all_pages:
        args.append("--all-pages")
    return subprocess.run(  # noqa: S603
        args,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_registry_lookup_follows_pagination_before_deciding_latest(tmp_path):
    first_page = [f"1.12.10rc{number}" for number in range(100)]
    pages = {
        TAG_URL: (200, {"results": [{"name": tag} for tag in first_page], "next": NEXT_URL}),
        NEXT_URL: (200, {"results": [{"name": "1.13.1"}], "next": None}),
    }
    result = _fetch_tags(tmp_path, pages)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [*first_page, "1.13.1"]
    assert docker_latest_tags.should_update_latest("1.12.10", result.stdout.splitlines()) is False


def test_default_registry_lookup_preserves_single_page_behavior(tmp_path):
    pages = {TAG_URL: (200, {"results": [{"name": "1.12.9"}], "next": NEXT_URL})}
    result = _fetch_tags(tmp_path, pages, all_pages=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["1.12.9"]


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (503, {"message": "registry unavailable"}),
        (200, {"results": [{"name": 123}], "next": None}),
        (200, {"results": "not a tag list", "next": None}),
        (200, {"results": [], "next": 123}),
        (200, {"results": []}),
        (200, {"results": [], "next": ""}),
        (200, {"results": [], "next": "https://example.com/untrusted"}),
    ],
)
def test_registry_errors_on_later_pages_fail_closed(tmp_path, status, body):
    pages = {
        TAG_URL: (200, {"results": [{"name": "1.12.9"}], "next": NEXT_URL}),
        NEXT_URL: (status, body),
    }
    result = _fetch_tags(tmp_path, pages)
    assert result.returncode != 0
    assert result.stderr


def test_authenticated_lookup_sends_bearer_token_on_every_page(tmp_path):
    pages = {
        AUTH_URL: (200, {"access_token": "fixture-bearer-token"}),
        "https://registry.hub.docker.com/v2/repositories/langflowai/langflow/tags?page_size=100": (
            403,
            {"message": "organization access tokens cannot use legacy endpoints"},
        ),
        TAG_URL: (200, {"results": [{"name": "1.12.9"}], "next": NEXT_URL}),
        NEXT_URL: (200, {"results": [{"name": "1.13.1"}], "next": None}),
    }
    result = _fetch_tags(tmp_path, pages, credentials=AUTH_ENV)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["1.12.9", "1.13.1"]
    calls = json.loads((tmp_path / "calls.json").read_text(encoding="utf-8"))
    assert [call["url"] for call in calls] == [AUTH_URL, TAG_URL, NEXT_URL]
    for call in calls[1:]:
        assert "Authorization: Bearer fixture-bearer-token" in call["args"]


@pytest.mark.parametrize(
    "next_url",
    [
        "https://registry.hub.docker.com/v2/repositories/langflowai/langflow/tags?page_size=100&page=2",
        "https://hub.docker.com/v2/namespaces/other/repositories/langflow/tags?page_size=100&page=2",
    ],
)
def test_authenticated_lookup_rejects_pagination_outside_the_repository(tmp_path, next_url):
    pages = {
        AUTH_URL: (200, {"access_token": "fixture-bearer-token"}),
        TAG_URL: (200, {"results": [{"name": "1.12.9"}], "next": next_url}),
    }
    result = _fetch_tags(tmp_path, pages, credentials=AUTH_ENV)
    assert result.returncode != 0
    assert "unexpected next page" in result.stderr
    calls = json.loads((tmp_path / "calls.json").read_text(encoding="utf-8"))
    assert [call["url"] for call in calls] == [AUTH_URL, TAG_URL]


def test_authenticated_tag_permission_errors_fail_closed(tmp_path):
    pages = {
        AUTH_URL: (200, {"access_token": "fixture-bearer-token"}),
        TAG_URL: (403, {"message": "tag read permission required"}),
    }
    result = _fetch_tags(tmp_path, pages, credentials=AUTH_ENV)
    assert result.returncode != 0
    assert "HTTP 403" in result.stderr
    assert not result.stdout
    assert "fixture-bearer-token" not in result.stderr


@pytest.mark.parametrize(
    ("status", "body"),
    [(401, {"message": "invalid credentials"}), (200, {}), (200, {"access_token": ""}), (200, {"access_token": 123})],
)
def test_authentication_errors_fail_closed_without_leaking_credentials(tmp_path, status, body):
    result = _fetch_tags(tmp_path, {AUTH_URL: (status, body)}, credentials=AUTH_ENV)
    assert result.returncode != 0
    for credential in AUTH_ENV.values():
        assert credential not in result.stdout + result.stderr


@pytest.mark.parametrize("missing", ["DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN"])
def test_incomplete_credentials_are_rejected(tmp_path, missing):
    result = _fetch_tags(tmp_path, {}, credentials={**AUTH_ENV, missing: ""})
    assert result.returncode != 0
    assert "fixture-password-secret" not in result.stdout + result.stderr


def _run_manifest_steps(tmp_path, pages, *, release_type, version, pre_release=False):
    env = {
        **_registry_env(tmp_path, pages),
        "BASE_VERSION": version,
        "MAIN_VERSION": version,
        "PRE_RELEASE": str(pre_release).lower(),
        "RELEASE_TYPE": release_type,
        "GITHUB_OUTPUT": str(tmp_path / "github_output"),
    }
    steps = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))["jobs"]["create-manifest"]["steps"]
    output = Path(env["GITHUB_OUTPUT"])
    output.touch()
    outputs = {}
    for step_name in ["Determine latest promotion", "Set tags"]:
        step = next(step for step in steps if step.get("name") == step_name)
        result = subprocess.run(  # noqa: S603
            [shutil.which("bash"), "-e", "-c", step["run"]],
            cwd=SCRIPT_DIR.parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        outputs.update(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
        if result.returncode:
            return result, outputs
        env["PROMOTE_LATEST"] = outputs["promote_latest"]
    return result, outputs


@pytest.mark.parametrize("release_type", ["main", "base", "main-backend", "main-frontend", "main-ep", "main-all"])
@pytest.mark.parametrize(
    ("version", "pre_release", "promote"),
    [("1.12.10", False, False), ("1.13.1", False, True), ("1.13.2", False, True), ("1.14.0rc1", True, False)],
)
def test_workflow_keeps_numbered_images_and_guards_both_registry_aliases(
    tmp_path, release_type, version, pre_release, promote
):
    suffix = release_type.removeprefix("main-") if release_type.startswith("main-") else ""
    repository = f"langflow{('-' + suffix) if suffix else ''}"
    prefix = "base-" if release_type == "base" else ""
    url = TAG_URL.replace("/langflow/tags", f"/{repository}/tags")
    pages = {url: (200, {"results": [{"name": f"{prefix}1.13.1"}], "next": None})}
    # A prerelease must not need a successful registry lookup.
    result, outputs = _run_manifest_steps(
        tmp_path, {} if pre_release else pages, release_type=release_type, version=version, pre_release=pre_release
    )
    assert result.returncode == 0, result.stderr
    expected = {f"langflowai/{repository}:{prefix}{version}", f"ghcr.io/langflow-ai/{repository}:{prefix}{version}"}
    if promote:
        expected.update({f"langflowai/{repository}:{prefix}latest", f"ghcr.io/langflow-ai/{repository}:{prefix}latest"})
    assert set(outputs["final_tags"].split(",")) == expected
    assert outputs["arch_base"] == f"langflowai/{repository}:{prefix}{version}"
    assert outputs["ghcr_arch_base"] == f"ghcr.io/langflow-ai/{repository}:{prefix}{version}"


def test_workflow_does_not_promote_from_partial_registry_history(tmp_path):
    pages = {
        TAG_URL: (200, {"results": [{"name": "1.12.9"}], "next": NEXT_URL}),
        NEXT_URL: (503, {"message": "unavailable"}),
    }
    result, outputs = _run_manifest_steps(tmp_path, pages, release_type="main", version="1.12.10")
    assert result.returncode != 0
    assert "final_tags" not in outputs
    assert outputs.get("promote_latest") != "true"


def test_manifest_publications_share_a_queue_across_release_versions():
    job = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))["jobs"]["create-manifest"]
    assert job["concurrency"] == {
        "group": "docker-release-manifest-${{ inputs.release_type }}",
        "cancel-in-progress": False,
        "queue": "max",
    }
    guard = next(step for step in job["steps"] if step.get("name") == "Determine latest promotion")
    assert guard["env"]["DOCKERHUB_USERNAME"] == "${{ secrets.DOCKERHUB_USERNAME }}"
    # This is a workflow secret reference, not a credential value.
    assert guard["env"]["DOCKERHUB_TOKEN"] == "${{ secrets.DOCKERHUB_TOKEN }}"  # noqa: S105
