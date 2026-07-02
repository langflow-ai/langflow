import asyncio
import importlib
import platform
import sys


def test_windows_event_loop_policy_set(monkeypatch):
    called = {}

    class DummyPolicy:
        pass

    def fake_set_event_loop_policy(policy):
        called["policy"] = policy

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(asyncio, "WindowsSelectorEventLoopPolicy", DummyPolicy, raising=False)
    monkeypatch.setattr(asyncio, "set_event_loop_policy", fake_set_event_loop_policy)

    sys.modules.pop("langflow.main", None)
    importlib.import_module("langflow.main")

    assert isinstance(called.get("policy"), DummyPolicy)
