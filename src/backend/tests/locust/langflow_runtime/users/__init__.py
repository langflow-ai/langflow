"""Locust users for the performance suite."""

from tests.locust.langflow_runtime.users.helpers import require_flow
from tests.locust.langflow_runtime.users.registry import USER_REGISTRY

__all__ = ["USER_REGISTRY", "PerfBaseUser", "require_flow"]


def __getattr__(name: str):
    if name == "PerfBaseUser":
        from tests.locust.langflow_runtime.users.base import PerfBaseUser

        return PerfBaseUser
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
