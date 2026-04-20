"""Local conftest for the benchmark-driver tests subdirectory.

The parent `src/backend/tests/benchmarks/conftest.py` sets `collect_ignore_glob = ["*.py"]`
because the scripts there (driver.py, snapshot.py, scenarios/*.py) are hyperfine /
pyinstrument entry points, not pytest tests. This subdirectory IS pytest tests, so we
reset the ignore list here.

Additionally inject the repo root into sys.path so `from src.backend.tests.benchmarks
import driver` resolves. The benchmark scaffolding uses absolute repo-root imports
(`src.backend.tests.benchmarks...`) consistently; the top-level pyproject doesn't expose
`src` as a package, so tests here must self-bootstrap.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

collect_ignore_glob: list[str] = []
