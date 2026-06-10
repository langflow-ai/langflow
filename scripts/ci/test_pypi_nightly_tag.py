"""Unit tests for pypi_nightly_tag.py (lockstep nightly versioning).

Run directly (matches test_constraint_preservation.py style) or via pytest:

    cd scripts/ci && uv run python -m pytest test_pypi_nightly_tag.py -q
    cd scripts/ci && uv run python test_pypi_nightly_tag.py

All PyPI HTTP traffic is mocked; no network access. `_root_base_version` is patched so the
tests do not depend on the repo's live version.
"""

import sys
from pathlib import Path
from unittest import mock

import pytest
import requests

# Ensure the sibling module is importable regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).parent))
import pypi_nightly_tag as nt

MAIN_URL = nt.PYPI_LANGFLOW_URL
BASE_URL = nt.PYPI_LANGFLOW_BASE_URL


class _FakeResponse:
    """Minimal stand-in for a requests.Response from PyPI's /pypi/<pkg>/json endpoint."""

    def __init__(self, *, releases=None, status_code=200, malformed=False):
        self._releases = list(releases) if releases else []
        self.status_code = status_code
        self._malformed = malformed

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != requests.codes.not_found:
            msg = f"status {self.status_code}"
            raise requests.HTTPError(msg)

    def json(self):
        if self._malformed:
            return {"info": {"version": "1.10.0.dev1"}}  # 200 OK but missing "releases"
        # Real PyPI shape: {"releases": {"<version>": [<files>], ...}}.
        return {"releases": {version: [] for version in self._releases}}


def _build_response(spec):
    """Turn a per-package spec into a _FakeResponse.

    spec: iterable of version strings, an int HTTP status (e.g. 404), the string "malformed",
    or None (absent package -> empty release list).
    """
    if spec is None:
        return _FakeResponse(releases=[])
    if isinstance(spec, int):
        return _FakeResponse(status_code=spec)
    if spec == "malformed":
        return _FakeResponse(malformed=True)
    return _FakeResponse(releases=spec)


def _run(main=None, base=None, *, base_version="1.10.0", build_type="both"):
    """Compute a tag with mocked PyPI responses for the main and base nightly packages."""
    responses = {MAIN_URL: _build_response(main), BASE_URL: _build_response(base)}

    def fake_get(url, timeout=10):  # noqa: ARG001
        return responses[url]

    with (
        mock.patch.object(nt.requests, "get", side_effect=fake_get),
        mock.patch.object(nt, "_root_base_version", return_value=base_version),
    ):
        return nt.create_tag(build_type)


# --- core invariant: main and base always resolve to the identical shared version -------------


def test_main_and_base_return_identical_version_given_offset_histories():
    # Live-state analog: langflow-nightly latest dev54, langflow-base-nightly latest dev48.
    main_hist = [f"1.10.0.dev{n}" for n in range(55)]
    base_hist = [f"1.10.0.dev{n}" for n in range(49)]
    main_tag = _run(main_hist, base_hist, build_type="main")
    base_tag = _run(main_hist, base_hist, build_type="base")
    both_tag = _run(main_hist, base_hist, build_type="both")
    assert main_tag == base_tag == both_tag == "v1.10.0.dev55"  # max(54, 48) + 1


def test_aligned_histories_increment_by_one():
    hist = [f"1.10.0.dev{n}" for n in range(43)]  # both latest dev42
    assert _run(hist, hist) == "v1.10.0.dev43"


# --- edge cases -------------------------------------------------------------------------------


def test_first_ever_nightly_both_404():
    assert _run(404, 404) == "v1.10.0.dev0"


def test_first_ever_nightly_both_absent():
    assert _run(None, None) == "v1.10.0.dev0"


def test_base_version_bump_resets_counter():
    # Root pyproject bumped to 1.10.1; old 1.10.0 devs must not leak into the new series.
    old_series = [f"1.10.0.dev{n}" for n in range(55)]
    assert _run(old_series, old_series, base_version="1.10.1") == "v1.10.1.dev0"


def test_base_version_bump_with_some_new_series_releases():
    main_hist = ["1.10.0.dev54", "1.10.1.dev0", "1.10.1.dev1"]
    base_hist = ["1.10.0.dev48", "1.10.1.dev0"]
    assert _run(main_hist, base_hist, base_version="1.10.1") == "v1.10.1.dev2"


def test_one_present_one_404():
    assert _run(["1.10.0.dev54"], 404) == "v1.10.0.dev55"
    assert _run(404, ["1.10.0.dev70"]) == "v1.10.0.dev71"


def test_final_release_does_not_advance_counter():
    # A non-dev/final release must not bump the nightly dev counter.
    assert _run(["1.10.0", "1.10.0.dev3"], ["1.10.0.dev2"]) == "v1.10.0.dev4"


def test_only_final_releases_yield_dev0():
    assert _run(["1.10.0"], ["1.10.0"]) == "v1.10.0.dev0"


def test_malformed_response_raises():
    # A 200 response missing "releases" is fatal (fail closed), not silently ignored.
    with pytest.raises(RuntimeError):
        _run("malformed", ["1.10.0.dev10"])


def test_server_error_raises():
    # A non-404 HTTP status on the higher-versioned package must abort, not emit a stale tag.
    with pytest.raises(requests.HTTPError):
        _run(500, ["1.10.0.dev48"])


def test_higher_package_lookup_failure_aborts():
    # P1 regression: langflow-nightly (dev54) lookup fails transiently while
    # langflow-base-nightly reports dev48. Must NOT emit v1.10.0.dev49 -- must raise so the job
    # stops before deleting/recreating tags or republishing an already-existing version.
    with pytest.raises(requests.HTTPError):
        _run(503, [f"1.10.0.dev{n}" for n in range(49)])


def test_network_error_raises():
    # A transient connection failure must abort rather than lower the computed dev number.
    def boom(url, timeout=10):  # noqa: ARG001
        raise requests.ConnectionError("transient")

    with (
        mock.patch.object(nt.requests, "get", side_effect=boom),
        mock.patch.object(nt, "_root_base_version", return_value="1.10.0"),
        pytest.raises(requests.ConnectionError),
    ):
        nt.create_tag("both")


def test_unparseable_version_string_is_skipped():
    assert _run(["not-a-version", "1.10.0.dev9"], None) == "v1.10.0.dev10"


def test_invalid_build_type_raises():
    with pytest.raises(ValueError, match="Invalid build type"):
        _run(["1.10.0.dev1"], ["1.10.0.dev1"], build_type="frontend")


def _main():
    """Run all tests without pytest (mirrors test_constraint_preservation.py)."""
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {exc}")
            else:
                print(f"ok   {name}")
    if failures:
        msg = f"{failures} test(s) failed."
        raise SystemExit(msg)
    print("All pypi_nightly_tag tests passed.")


if __name__ == "__main__":
    _main()
