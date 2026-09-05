"""Load the INT-13 reference samples that ``docs/docs/Lfx/lfx-connections.mdx`` embeds.

The documentation page renders these files verbatim with ``raw-loader``, and these
tests execute the same files, so the page cannot document code that does not run.
The samples deliberately live under ``docs/`` rather than inside the ``lfx``
package: they are reference code to copy, not public API.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

# .../<repo>/src/lfx/tests/unit/services/connection/sample_loader.py -> <repo>
_REPO_ROOT = Path(__file__).resolve().parents[6]
SAMPLES_DIR = _REPO_ROOT / "docs" / "docs" / "Lfx" / "samples" / "connections"

#: The samples ship in the repository, not in the ``lfx`` wheel. A test run made
#: from a source tree without ``docs/`` (an sdist-only smoke run) skips them
#: rather than failing on a file it was never given.
SAMPLES_AVAILABLE = SAMPLES_DIR.is_dir()
requires_samples = pytest.mark.skipif(
    not SAMPLES_AVAILABLE,
    reason=f"reference samples not present at {SAMPLES_DIR}",
)


def sample_path(module_name: str) -> Path:
    """Return the on-disk path of one sample module."""
    path = SAMPLES_DIR / f"{module_name}.py"
    if not path.is_file():
        msg = f"Reference sample {path} is missing; docs and tests must ship together"
        raise FileNotFoundError(msg)
    return path


def load_connection_sample(module_name: str) -> ModuleType:
    """Import one sample module by path and register it under its own name.

    The module is registered in ``sys.modules`` so ``lfx.toml`` can select a class
    from it with the same ``"<module>:<Class>"`` string an operator would write.
    """
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, sample_path(module_name))
    if spec is None or spec.loader is None:
        msg = f"Could not load reference sample {module_name}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module
