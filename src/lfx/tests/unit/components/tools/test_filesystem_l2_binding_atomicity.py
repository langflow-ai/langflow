"""Regression for the L2 binding atomicity TOCTOU.

In isolated mode the L2 binding check (`_user_binding_error`) reads
``self._resolve_user_id()`` once, then ``_validate_root`` reads it again
to compute the namespace. If the live user_id shifts between the two
reads (component pool reuse across users, side-effecting property,
threaded reentrancy), the binding check passes for user A while the
file lands in user B's namespace.

The fix must ensure a single, atomic capture of ``user_id`` per tool
invocation: the value read by the binding check is the same value used
by ``_validate_root`` for the same call.
"""

import asyncio
import json
from pathlib import Path

import pytest
from lfx.components.files_and_knowledge._filesystem_namespace import (
    compute_user_namespace,
    load_or_create_pepper,
)
from lfx.components.files_and_knowledge.filesystem import FileSystemToolComponent


@pytest.fixture
def base_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def component(base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> FileSystemToolComponent:  # noqa: ARG001
    # base_dir fixture is consumed for its env-setting side effect.
    c = FileSystemToolComponent(root_path="", read_only=False)
    # Isolated mode is the threat scenario: shared mode bypasses the L2
    # check entirely (binding is a no-op when AUTO_LOGIN is True).
    monkeypatch.setattr(c, "_resolve_auto_login", lambda: False)
    return c


def test_should_use_consistent_user_id_within_a_single_tool_call(
    component: FileSystemToolComponent,
    base_dir: Path,
) -> None:
    """Mutate ``self._user_id`` mid-call and assert no namespace cross-write.

    Identity-shift TOCTOU: ``self._user_id`` is mutated between the L2
    binding check (which captures it) and ``_validate_root`` (which
    would read it again to compute the namespace). The fix must pin the
    value captured at the check so the path resolution sees the same
    identity even when the underlying attribute changed mid-call.
    """
    component._user_id = "alice"

    # Capture the user_id at _get_tools time (binding capture for "alice").
    tools = asyncio.run(component._get_tools())
    write_tool = next(t for t in tools if t.name == "write_file")

    # Simulate the concurrent mutation: wrap _write_file so it flips
    # ``self._user_id`` to "bob" right before the underlying write runs —
    # exactly the window the bug requires. Without the L2 atomic capture,
    # _validate_root would now read "bob" and resolve bob's namespace,
    # silently writing alice's content there.
    real_write_file = component._write_file

    def write_file_after_identity_shift(path: str, content: str) -> dict:
        component._user_id = "bob"
        return real_write_file(path, content)

    component._write_file = write_file_after_identity_shift  # type: ignore[method-assign]

    result_json = write_tool.func("alice_secret.txt", "alice's content")
    result = json.loads(result_json)

    pepper = load_or_create_pepper(base_dir / ".fs_pepper")
    # compute_user_namespace already includes the "users/<hash>" prefix
    bob_dir = base_dir / compute_user_namespace("bob", pepper=pepper)
    leaked = bob_dir / "alice_secret.txt"

    assert not leaked.exists(), (
        f"identity-shift TOCTOU: alice's write leaked into bob's namespace at {leaked!s}; result={result!r}"
    )

    # Acceptable outcomes: refused with a mismatch error, OR landed under alice.
    if "error" not in result:
        alice_dir = base_dir / compute_user_namespace("alice", pepper=pepper)
        assert (alice_dir / "alice_secret.txt").exists(), (
            "tool reported success but the file is not in alice's namespace"
        )


def test_should_refuse_when_binding_check_sees_different_user_than_capture(
    component: FileSystemToolComponent,
    base_dir: Path,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,  # noqa: ARG001
) -> None:
    """Refuse when the live user_id no longer matches the captured one.

    Sanity check: when the binding check itself sees a different user
    from the one captured at ``_get_tools()``, the call must be refused
    outright (this is the existing L2 contract — pin it in this file).
    """
    component._user_id = "alice"
    tools = asyncio.run(component._get_tools())
    write_tool = next(t for t in tools if t.name == "write_file")

    # Component reused for bob: live user_id != bound user_id.
    component._user_id = "bob"

    result = json.loads(write_tool.func("hello.txt", "hi"))
    assert "error" in result
    assert "mismatch" in result["error"].lower()
