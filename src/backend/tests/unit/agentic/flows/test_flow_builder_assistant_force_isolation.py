"""B1 — build_toolkit must bind user_id + force_isolation on the FS component.

The agent's write_file / edit_file tools are produced by
``FileSystemToolComponent._get_tools()`` inside ``build_toolkit``. Without
explicit binding the standalone component has no user_id and falls back to
the shared root under ``AUTO_LOGIN=True`` — but the /agentic/files endpoint
(B1) now forces per-user isolation, so the agent must mirror it or its
writes become unreadable from the endpoint.

This test asserts the toolkit-build-time binding: when ``current_user_id``
is bound to the request, the fs component used to mint the tools has
``_user_id`` set AND ``_force_isolation = True``.
"""

from __future__ import annotations

from langflow.agentic.flows import flow_builder_assistant as fba
from langflow.agentic.services.user_components_context import (
    reset_current_user_id,
    set_current_user_id,
)


class _StubStructuredTool:
    """Minimal stand-in returned by the patched FS toolkit.

    Carries the attributes ``wrap_file_tool_with_event`` reads
    (``name``, ``func``, ``coroutine``, ``args_schema``) so the wrapping
    branch in build_toolkit doesn't crash mid-test.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.description = ""
        self.func = lambda *_a, **_k: {"status": "ok"}
        self.coroutine = None
        self.args_schema = None


class _CapturingFSComponent:
    """Capture the per-call state for assertion.

    Mimics the small subset of FileSystemToolComponent the toolkit builder
    actually touches.
    """

    instances: list[_CapturingFSComponent] = []

    def __init__(self) -> None:
        self._user_id: str | None = None
        self._force_isolation: bool = False
        self._get_tools_called_with: dict | None = None
        _CapturingFSComponent.instances.append(self)

    async def _get_tools(self) -> list:
        # Snapshot the binding state AT THE MOMENT _get_tools is called,
        # because that's when bound_user_id is captured for the lifetime of
        # the tools.
        self._get_tools_called_with = {
            "user_id": self._user_id,
            "force_isolation": self._force_isolation,
        }
        # Return both a read tool and a write tool to exercise the wrapping
        # branch in build_toolkit.
        return [_StubStructuredTool("read_file"), _StubStructuredTool("write_file")]


class TestBuildToolkitBindsForceIsolation:
    async def test_should_bind_user_id_and_force_isolation_when_user_context_set(self, monkeypatch):
        # Arrange — replace the heavy FS component with our capturing stub.
        _CapturingFSComponent.instances.clear()
        monkeypatch.setattr(fba, "FileSystemToolComponent", _CapturingFSComponent)

        # Skip the canvas-component instantiation (heavy registry side effects).
        async def fake_to_toolkit(_self):
            return []

        for component_cls in (
            fba.SearchComponentTypes,
            fba.DescribeComponentType,
            fba.DescribeFlowIO,
            fba.GenerateComponent,
            fba.GetFieldValue,
            fba.ProposeFieldEdit,
            fba.ProposePlan,
            fba.AddComponent,
            fba.RemoveComponent,
            fba.ConnectComponents,
            fba.ConfigureComponent,
            fba.BuildFlowFromSpec,
            fba.RunFlow,
        ):
            monkeypatch.setattr(component_cls, "to_toolkit", fake_to_toolkit, raising=True)

        # Bind the request's user context (mirrors assistant_service:578).
        set_current_user_id("user-alice")
        try:
            await fba.build_toolkit()
        finally:
            reset_current_user_id()

        # Assert — exactly one fs component was instantiated and it captured
        # the user_id + force_isolation at _get_tools time.
        assert len(_CapturingFSComponent.instances) == 1
        captured = _CapturingFSComponent.instances[0]._get_tools_called_with
        assert captured == {"user_id": "user-alice", "force_isolation": True}
