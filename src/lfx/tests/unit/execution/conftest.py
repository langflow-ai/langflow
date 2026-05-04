"""Reset the module-level singletons between every test in this folder.

The default coordinator and registry are import-time singletons so that
production callers can use them without DI. Tests that mutate them
(register a new backend, swap the default, etc.) must not bleed state
into the next test.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_execution_singletons():
    from lfx import execution

    execution._default_registry = None
    execution._default_coordinator = None
    yield
    execution._default_registry = None
    execution._default_coordinator = None
