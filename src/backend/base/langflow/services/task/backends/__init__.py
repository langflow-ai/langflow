"""Compatibility re-export from the standalone ``services`` package."""

from __future__ import annotations

import services.task.backends as _impl

globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})
if hasattr(_impl, "__all__"):
    __all__ = list(_impl.__all__)
_getattr = getattr(_impl, "__getattr__", None)
if _getattr is not None:
    __getattr__ = _getattr
_dir = getattr(_impl, "__dir__", None)
if _dir is not None:
    __dir__ = _dir
