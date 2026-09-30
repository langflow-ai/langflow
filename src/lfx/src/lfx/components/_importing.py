"""Import utilities for LangFlow components.

Backward-compatibility re-export: the canonical, contract-stable home of
:func:`import_mod` is :mod:`lfx.utils.lazy_import` (part of the BUNDLE_API
surface, since separately-installed bundle packages call it from their lazy
``__init__.py`` files).  In-tree callers may keep using this path; bundle
packages import from ``lfx.utils.lazy_import``.
"""

from __future__ import annotations

from lfx.utils.lazy_import import import_mod

__all__ = ["import_mod"]
