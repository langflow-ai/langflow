"""A fresh CLI discovers GitLab without applying another provider's context restriction."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("injected", [False, True])
@pytest.mark.parametrize("check_variables", [False, True])
def test_exported_cli_flow_allows_headless_context_but_requires_verified_credentials(
    tmp_path, *, injected, check_variables
):
    import lfx_gitlab
    from lfx.components.input_output import ChatOutput
    from lfx.graph import Graph
    from lfx_gitlab.components.gitlab import GitLabGetProjectComponent

    project = GitLabGetProjectComponent(_id="gitlab", connection="gitlab/work", project_id=80)
    output = ChatOutput(_id="output").set(input_value=project.build_result)
    exported = Graph(start=project, end=output).dump()
    for node in exported["data"]["nodes"]:
        code = node["data"]["node"]["template"]["code"]
        code["value"] = code["value"].splitlines()
    path = tmp_path / "gitlab.json"
    path.write_text(json.dumps(exported), encoding="utf-8")
    env = os.environ.copy()
    env["LANGFLOW_ALLOW_CUSTOM_COMPONENTS"] = "true"
    # Source-only CI discovers the same extension manifest as an installed wheel.
    env["LANGFLOW_SEED_DIR"] = str(Path(lfx_gitlab.__file__).parent.parent)
    env["DO_NOT_TRACK"] = "1"
    env.pop("LF_CONNECTION__GITLAB__WORK", None)
    if injected:
        # A raw token lacks the account, instance, scope, and identity verification required by GitLab.
        env["LF_CONNECTION__GITLAB__WORK"] = "synthetic-gitlab-access"
    result = subprocess.run(  # noqa: S603 - fixed CLI arguments and test-owned flow
        [
            sys.executable,
            "-m",
            "lfx",
            "run",
            str(path),
            "--input-value",
            "x",
            "--check-variables" if check_variables else "--no-check-variables",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 1
    response = json.loads(result.stdout)
    assert "not available in headless" not in response["exception_message"]
    assert "synthetic-gitlab-access" not in result.stdout + result.stderr
    if injected:
        assert "scope" in response["exception_message"].lower()
    else:
        assert "LF_CONNECTION__GITLAB__WORK" in response["exception_message"]
