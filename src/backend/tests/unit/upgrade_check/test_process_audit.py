"""Process audit refusals happen before dispatch and survive callbacks that swallow them."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from langflow.upgrade_check import command, engine
from langflow.upgrade_check.isolation import is_local_metadata_probe

from tests.unit.upgrade_check.test_offline_discovery import _options

REFUSED_EVENTS = [
    ("subprocess.Popen", ("/synthetic/unused", ["/synthetic/unused"], None, {})),
    ("os.system", (b"synthetic unused",)),
    ("os.posix_spawn", ("/synthetic/unused", ["/synthetic/unused"], {})),
    ("os.spawn", (0, "/synthetic/unused", ["/synthetic/unused"], {})),
    ("os.exec", ("/synthetic/unused", ["/synthetic/unused"], {})),
    ("os.fork", ()),
    ("os.forkpty", ()),
    ("os.startfile", ("/synthetic/unused", "open")),
    ("os.startfile/2", ("/synthetic/unused", "open", None, None, None)),
    ("pty.spawn", (["/synthetic/unused"],)),
    ("socket.sendmsg", (None, ("synthetic.invalid", 443))),
    ("socket.getnameinfo", (("synthetic.invalid", 443), 0)),
]


def _callback(event, arguments, *, swallow):
    try:
        sys.audit(event, *arguments)
    except (PermissionError, ConnectionRefusedError):
        if not swallow:
            raise


@pytest.mark.parametrize(("event", "arguments"), REFUSED_EVENTS)
@pytest.mark.parametrize("swallow", [False, True], ids=["propagated", "swallowed"])
def test_discovery_process_audit_event_prevents_partial_report(monkeypatch, tmp_path, event, arguments, swallow):
    options = _options(tmp_path)

    def discover(**_kwargs):
        _callback(event, arguments, swallow=swallow)
        return {}

    monkeypatch.setattr(command, "load_upgrade_registry", discover)
    events = []
    with pytest.raises(command.CheckError, match="process") as caught:
        command.run(options, events.append)
    assert caught.value.code == "registry_unavailable"
    assert any(refused.startswith(event) for refused in engine._refused_calls)
    assert events == []


@pytest.mark.skipif(not Path("/usr/bin/git").is_file(), reason="system git metadata probe is unavailable")
def test_exact_system_git_metadata_probe_is_allowed_without_launching_it():
    for executable in ("git", str(Path("/usr/bin/git").resolve())):
        assert is_local_metadata_probe((executable, [executable, "version"], None, {"PATH": os.defpath}))


@pytest.mark.skipif(not Path("/usr/bin/file").is_file(), reason="system file metadata probe is unavailable")
def test_exact_current_interpreter_metadata_probe_allows_a_path_alias_without_launching_it(tmp_path):
    alias = tmp_path / "interpreter"
    alias.symlink_to(sys.executable)
    for executable in ("file", str(Path("/usr/bin/file").resolve())):
        assert is_local_metadata_probe(
            (executable, [executable, "-b", str(alias)], None, {"PATH": os.defpath, "LC_ALL": "C"})
        )


@pytest.mark.parametrize("program", ["git", "file"])
@pytest.mark.parametrize(("value", "allowed"), [("http", True), ("http/dup", False)])
def test_metadata_probe_retains_only_the_current_semantic_convention_flag(monkeypatch, program, value, allowed):
    if not Path(f"/usr/bin/{program}").is_file():
        pytest.skip("system metadata probe is unavailable")
    monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
    argv = [program, "version"] if program == "git" else [program, "-b", sys.executable]
    environment = {"PATH": os.defpath, "OTEL_SEMCONV_STABILITY_OPT_IN": value}
    arguments = (program, argv, None, environment)
    assert is_local_metadata_probe(arguments) is allowed

    def discover():
        _callback("subprocess.Popen", arguments, swallow=True)
        return {}

    if allowed:
        assert engine.discover_offline(discover) == {}
        assert engine._refused_calls == []
    else:
        with pytest.raises(engine.ComponentDiscoveryError, match="process"):
            engine.discover_offline(discover)
        assert engine._refused_calls == ["subprocess.Popen"]


@pytest.mark.parametrize(("value", "allowed"), [("0x1F5:0x0:0x0", True), ("modified", False)])
def test_metadata_probe_retains_only_the_current_macos_encoding(monkeypatch, value, allowed):
    if not Path("/usr/bin/file").is_file():
        pytest.skip("system metadata probe is unavailable")
    monkeypatch.setenv("__CF_USER_TEXT_ENCODING", "0x1F5:0x0:0x0")
    assert (
        is_local_metadata_probe(
            ("file", ["file", "-b", sys.executable], None, {"PATH": os.defpath, "__CF_USER_TEXT_ENCODING": value})
        )
        is allowed
    )


@pytest.mark.parametrize(
    "variant",
    ["path", "extra_arg", "shell", "lookalike", "argv_lookalike", "injected_env", "wrong_target", "relative_target"],
)
def test_metadata_lookalikes_are_refused_without_launching_them(tmp_path, variant):
    fake = tmp_path / "git"
    fake.write_text("inert metadata fixture")
    fake.chmod(0o755)
    executable, argv, environment = "git", ["git", "version"], {"PATH": os.defpath}
    if variant == "path":
        environment["PATH"] = str(tmp_path) + os.pathsep + os.defpath
    elif variant == "extra_arg":
        argv.append("extra")
    elif variant == "shell":
        executable = "/bin/sh"
    elif variant == "lookalike":
        executable = str(fake)
    elif variant == "argv_lookalike":
        argv[0] = str(fake)
    elif variant == "injected_env":
        environment["LD_PRELOAD"] = "/synthetic/unused"
    elif variant == "wrong_target":
        executable, argv = "file", ["file", "-b", str(fake)]
    else:
        executable, argv = "file", ["file", "-b", "interpreter"]
    assert not is_local_metadata_probe((executable, argv, None, environment))
    with pytest.raises(engine.ComponentDiscoveryError, match="process"):
        engine.discover_offline(
            lambda: _callback("subprocess.Popen", (executable, argv, None, environment), swallow=True)
        )
    assert engine._refused_calls == ["subprocess.Popen"]


def test_metadata_probe_validation_error_is_a_persistent_refusal(monkeypatch):
    def fail(_arguments):
        message = "synthetic validation failure"
        raise OSError(message)

    monkeypatch.setattr(engine, "is_local_metadata_probe", fail)
    with pytest.raises(engine.ComponentDiscoveryError, match="process"):
        engine.discover_offline(
            lambda: _callback("subprocess.Popen", ("git", ["git", "version"], None, {}), swallow=True)
        )
    assert engine._refused_calls == ["subprocess.Popen"]


@pytest.mark.parametrize(("event", "arguments"), REFUSED_EVENTS)
@pytest.mark.parametrize("swallow", [False, True], ids=["propagated", "swallowed"])
def test_dry_run_process_audit_event_cannot_appear_verified(monkeypatch, event, arguments, swallow):
    def build(_component, **_kwargs):
        _callback(event, arguments, swallow=swallow)
        return {}, object()

    async def rebuild(_instance, _built, saved, **_kwargs):
        return saved

    monkeypatch.setattr(engine, "build_custom_component_template", build)
    monkeypatch.setattr(engine, "update_rebuilt_node", rebuild)
    engine._install_network_guard()
    _outcome, failure = engine._dry_run({"template": {"code": {"value": ""}}}, {}, None)

    assert failure is not None
    assert failure["code"] == "could_not_verify"
    assert event in failure["message"]
    assert ("network call" if event.startswith("socket.") else "child process launch") in failure["message"]
    assert any(refused.startswith(event) for refused in engine._refused_calls)
