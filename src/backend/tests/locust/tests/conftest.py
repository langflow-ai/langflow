"""Keep Locust unit/integration tests free of the heavy backend conftest tree."""

from __future__ import annotations

# Intentionally empty: presence of this file does not stop parent conftests, but
# tests under tests/locust/tests are intended to run with --noconftest when
# invoked from Make / CI helpers for the performance suite.
