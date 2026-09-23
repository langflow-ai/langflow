"""Exercise the coverage advisor's actual shell steps with changed PR filenames."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/test-coverage-advisor.yml"


def _run(*command: str, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True, capture_output=True, text=True)  # noqa: S603


def _outputs(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())


@pytest.mark.parametrize(
    ("changed_files", "expected"),
    [
        (["src/backend/x'; touch injected_marker; echo '.py"], (True, False)),
        (["src/frontend/src/x'; touch injected_marker; echo '.tsx"], (False, True)),
        (["src/backend/x$(touch injected_marker).py", "src/frontend/src/x`touch injected_marker`.tsx"], (True, True)),
        (["src/backend/plain.py", "src/backend/tests/test_plain.py"], (False, False)),
    ],
    ids=["backend-quote", "frontend-quote", "both-command-substitutions", "source-with-test"],
)
def test_coverage_advisor_keeps_filenames_as_data(
    tmp_path: Path, changed_files: list[str], expected: tuple[bool, bool]
):
    need_be, need_fe = expected
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["advise"]["steps"]
    detect = next(step["run"] for step in steps if step.get("id") == "detect")
    message = next(step["run"] for step in steps if step.get("id") == "msg")
    detect = detect.replace("${{ github.event.pull_request.base.ref }}", "main")
    assert "${{" not in detect
    assert "${{" not in message

    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    _run("git", "init", "--bare", "--initial-branch=main", str(remote), cwd=tmp_path)
    _run("git", "clone", str(remote), str(repo), cwd=tmp_path)
    _run("git", "config", "user.email", "advisor-test@example.invalid", cwd=repo)
    _run("git", "config", "user.name", "Advisor Test", cwd=repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run("git", "add", "README.md", cwd=repo)
    _run("git", "commit", "-m", "base", cwd=repo)
    _run("git", "push", "origin", "main", cwd=repo)
    _run("git", "checkout", "-b", "feature", cwd=repo)
    for name in changed_files:
        file = repo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("changed\n", encoding="utf-8")
    _run("git", "add", "--all", cwd=repo)
    _run("git", "commit", "-m", "changes", cwd=repo)

    output_file = tmp_path / "detect-output"
    env = {**os.environ, "GITHUB_OUTPUT": str(output_file)}
    _run("bash", "-e", "-o", "pipefail", "-c", detect, cwd=repo, env=env)
    outputs = _outputs(output_file)
    assert outputs["need_be"] == str(need_be).lower()
    assert outputs["need_fe"] == str(need_fe).lower()

    message_output = tmp_path / "message-output"
    env.update(
        {
            "GITHUB_OUTPUT": str(message_output),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
            "NEED_BE": outputs["need_be"],
            "NEED_FE": outputs["need_fe"],
            "PY_SRC_FILE": outputs["py_src_file"],
            "FE_SRC_FILE": outputs["fe_src_file"],
        }
    )
    _run("bash", "-e", "-o", "pipefail", "-c", message, cwd=repo, env=env)
    body = Path(_outputs(message_output)["body_file"]).read_text(encoding="utf-8")
    assert not (repo / "injected_marker").exists()
    assert ("#### Backend" in body) == need_be
    assert ("#### Frontend" in body) == need_fe
    if need_be or need_fe:
        for name in changed_files:
            if name.startswith("src/backend/tests/"):
                continue
            assert name in body
    else:
        assert "No source changes detected without accompanying tests" in body
