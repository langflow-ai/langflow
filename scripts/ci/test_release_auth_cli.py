"""Behavioral tests for the release authentication command-line interface."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

from scripts.ci.release_auth.cli import main
from scripts.ci.release_auth.constants import AUTH_SOURCE
from scripts.ci.release_auth_fixtures import run_git

pytest_plugins = ("scripts.ci.release_auth_fixtures",)


@pytest.mark.parametrize("use_default_path", [False, True])
def test_should_prepare_source_when_cli_is_invoked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *, use_default_path: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    source = AUTH_SOURCE if use_default_path else tmp_path / "auth.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("class AuthSettings:\n    AUTO_LOGIN: bool = Field(default=True)\n")

    main(["prepare", *([] if use_default_path else [str(source)])])

    assert "default=False" in source.read_text()
    assert "AUTO_LOGIN=False" in capsys.readouterr().out


@pytest.mark.parametrize("is_release", [False, True])
def test_should_enforce_source_default_when_verifying_from_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *, is_release: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    AUTH_SOURCE.parent.mkdir(parents=True)
    AUTH_SOURCE.write_text(f"class AuthSettings:\n    AUTO_LOGIN: bool = Field(default={not is_release})\n")

    if is_release:
        main(["verify-source"])
        assert "AUTO_LOGIN=False" in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit) as error:
            main(["verify-source", str(AUTH_SOURCE)])
        assert error.value.code == 2
        assert "Prepare Release Tag workflow" in capsys.readouterr().err


@pytest.mark.parametrize("include_development_wheel", [False, True])
def test_should_check_each_wheel_when_verifying_from_cli(
    wheel_files: dict[bool, Path], capsys: pytest.CaptureFixture[str], *, include_development_wheel: bool
) -> None:
    wheels = [str(wheel_files[True]), str(wheel_files[not include_development_wheel])]

    if include_development_wheel:
        with pytest.raises(SystemExit) as error:
            main(["verify", *wheels])
        assert error.value.code == 2
        output = capsys.readouterr()
        assert "must default AuthSettings.AUTO_LOGIN to False" in output.err
        assert f"Verified {wheel_files[False].name}" not in output.out
    else:
        main(["verify", *wheels])
        assert capsys.readouterr().out.count("AUTO_LOGIN=False") == 2


@pytest.mark.parametrize("command", ["prepare", "verify-source", "verify"])
def test_should_report_missing_file_when_cli_input_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(SystemExit) as error:
        main([command, str(missing)])

    assert error.value.code == 2
    assert "No such file or directory" in capsys.readouterr().err
    assert not missing.exists()


@pytest.mark.parametrize("arguments", [[], ["unknown"], ["tag"], ["verify"]])
def test_should_reject_arguments_when_cli_usage_is_invalid(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        main(arguments)

    assert error.value.code == 2
    assert "usage:" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("command", "contents", "message"),
    [("prepare", "not valid python !", "invalid syntax"), ("verify", "not a zip file", "File is not a zip file")],
)
def test_should_preserve_artifact_when_cli_input_is_malformed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, contents: str, message: str
) -> None:
    path = tmp_path / "artifact"
    path.write_text(contents)

    with pytest.raises(SystemExit) as error:
        main([command, str(path)])

    assert error.value.code == 2
    assert message in capsys.readouterr().err
    assert path.read_text() == contents


def test_should_print_only_release_sha_when_cli_creates_tag(
    source_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(source_repo)
    base = run_git(source_repo, "rev-parse", "HEAD")

    main(["tag", "v1.13.0", "--ref", base.decode().strip()])

    sha = capsys.readouterr().out
    assert sha.encode() == run_git(source_repo, "rev-parse", "refs/tags/v1.13.0^{commit}")
    assert sha.encode() != base
    assert run_git(source_repo, "rev-parse", "HEAD") == base
    assert b"default=False" in run_git(source_repo, "show", f"v1.13.0:{AUTH_SOURCE.as_posix()}")

    main(["tag", "v1.13.0"])
    assert capsys.readouterr().out == sha


@pytest.mark.parametrize("ref", ["missing-ref", "--invalid-option"])
def test_should_report_git_failure_when_cli_ref_is_invalid(
    source_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], ref: str
) -> None:
    monkeypatch.chdir(source_repo)

    with pytest.raises(SystemExit) as error:
        main(["tag", "v1.13.0", f"--ref={ref}"])

    assert error.value.code == 2
    assert "Git operation failed:" in capsys.readouterr().err
    assert run_git(source_repo, "tag", "--list") == b""


@pytest.mark.parametrize("use_module", [False, True])
def test_should_support_workflow_entry_point_from_arbitrary_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *, use_module: bool
) -> None:
    script = Path(__file__).with_name("release_auth_defaults.py").resolve()
    source = tmp_path / "auth.py"
    source.write_text("class AuthSettings:\n    AUTO_LOGIN: bool = Field(default=True)\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [str(script), "prepare", str(source)])
    if use_module:
        runpy.run_module("scripts.ci.release_auth_defaults", run_name="__main__")
    else:
        monkeypatch.syspath_prepend(str(script.parent))
        runpy.run_path(str(script), run_name="__main__")

    assert "default=False" in source.read_text()
    assert "AUTO_LOGIN=False" in capsys.readouterr().out
