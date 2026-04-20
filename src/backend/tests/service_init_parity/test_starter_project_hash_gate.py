"""SVC-01 starter-projects hash-gate behavioral tests (D-05 /).

Exercises ``run_starter_projects_hash_gate`` against the synthetic
starter folders. The gate is the exact helper ``langflow/main.py`` calls
inside its ``FileLock`` block (see ``04-01-PLAN.md`` Task 3 approach (b) --
planner chose "extract testable helper" so tests and production share code),
minus the lock itself -- locking is orthogonal infrastructure covered by the
existing FileLock behavior.

Tests use a hand-written ``_CallCounter`` rather than ``unittest.mock``
(``monkeypatch`` + call-site spy per / global CLAUDE.md "avoid
mocking in tests").

Pitfall 7 reminder: the wall-clock tripwire is 200ms (generous, local). The
50ms number lives in CI's ``cold-start-benchmark.yml`` + ``thresholds.json``
pipeline, not here. Do not tighten.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from langflow.initial_setup.starter_project_hash import (
    HASH_FILENAME,
    compute_starter_projects_hash,
    is_force_resync_requested,
    run_starter_projects_hash_gate,
    write_hash_file_safe,
)

if TYPE_CHECKING:
    from pathlib import Path

    import anyio


class _CallCounter:
    """Minimal async call counter -- no mocking framework dependency.

    Matches the analog in ``src/backend/tests/unit/test_main_superuser_init.py``
    and Pattern A in ``04-PATTERNS.md``.
    """

    def __init__(self) -> None:
        self.count = 0

    async def __call__(self, *_args, **_kwargs) -> None:
        self.count += 1

    def reset(self) -> None:
        self.count = 0


async def _seed_matching_hash(hash_path: Path, starter_folder: anyio.Path, version_string: str = "test") -> str:
    """Compute and write the correct hash so the gate will see a match on next call."""
    expected = await compute_starter_projects_hash(starter_folder)
    await write_hash_file_safe(hash_path, expected, version_string)
    return expected


@pytest.mark.asyncio
async def test_svc01_second_invocation_skips_sync_and_is_fast(
    tmp_config_dir: Path,
    starter_folder_minimal: anyio.Path,
) -> None:
    """D-05 core: first call runs sync, second call (hash present) skips + finishes in <200ms.

    The local 200ms wall-clock tripwire is intentionally generous per Pitfall 7
    -- the 50ms number is CI-only. What we care about here is the behavioral
    assertion ``counter.count == 0`` on the second invocation (cache hit).
    """
    hash_path = tmp_config_dir / HASH_FILENAME
    counter = _CallCounter()

    # First invocation -- no hash file exists, so full sync runs and hash is written.
    resynced_first = await run_starter_projects_hash_gate(
        starter_folder=starter_folder_minimal,
        hash_path=hash_path,
        sync_fn=counter,
    )
    assert resynced_first is True, "first call should run the full sync"
    assert counter.count == 1, f"first call should fire sync_fn once, got {counter.count}"
    assert hash_path.exists(), "first call should have written the hash file"

    # Second invocation -- hash file exists and content matches, so the gate short-circuits.
    counter.reset()
    t0 = time.perf_counter()
    resynced_second = await run_starter_projects_hash_gate(
        starter_folder=starter_folder_minimal,
        hash_path=hash_path,
        sync_fn=counter,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert resynced_second is False, "second call should skip the full sync"
    assert counter.count == 0, (
        f"second invocation must not fire sync_fn; got {counter.count} calls. Hash gate did not short-circuit on match."
    )
    # Pitfall 7: 200ms local tripwire, NOT 50ms (CI owns 50ms).
    assert elapsed_ms < 200, (
        f"second invocation took {elapsed_ms:.1f}ms; expected < 200ms "
        "(local tripwire; authoritative 50ms budget lives in CI)."
    )


@pytest.mark.asyncio
async def test_svc01_mutated_starter_triggers_full_resync(
    tmp_config_dir: Path,
    starter_folder_minimal: anyio.Path,
    starter_folder_mutated: anyio.Path,
) -> None:
    """Mutating one byte of the starter JSON invalidates the cached hash.

    Seeds the hash file with the ``starter_folder_minimal`` digest, then calls
    the gate with ``starter_folder_mutated`` (same filenames, one byte
    different). The recomputed hash mismatches the seed, so full sync fires.
    """
    hash_path = tmp_config_dir / HASH_FILENAME
    await _seed_matching_hash(hash_path, starter_folder_minimal)

    counter = _CallCounter()
    resynced = await run_starter_projects_hash_gate(
        starter_folder=starter_folder_mutated,
        hash_path=hash_path,
        sync_fn=counter,
    )
    assert resynced is True, "mutated starter must trigger a full re-sync"
    assert counter.count == 1, (
        f"mutated-starter gate must fire sync_fn; got {counter.count} calls. "
        "A byte-level change did NOT invalidate the hash."
    )


@pytest.mark.asyncio
async def test_svc01_force_resync_env_var_bypasses_hash_match(
    tmp_config_dir: Path,
    starter_folder_minimal: anyio.Path,
    monkeypatch,
) -> None:
    """D-04: LANGFLOW_FORCE_STARTER_RESYNC=1 forces re-sync even when hash matches."""
    hash_path = tmp_config_dir / HASH_FILENAME
    await _seed_matching_hash(hash_path, starter_folder_minimal)

    monkeypatch.setenv("LANGFLOW_FORCE_STARTER_RESYNC", "1")
    assert is_force_resync_requested() is True

    counter = _CallCounter()
    resynced = await run_starter_projects_hash_gate(
        starter_folder=starter_folder_minimal,
        hash_path=hash_path,
        sync_fn=counter,
    )
    assert resynced is True, "LANGFLOW_FORCE_STARTER_RESYNC=1 must force a re-sync"
    assert counter.count == 1, f"force-resync must fire sync_fn regardless of hash match; got {counter.count} calls."


@pytest.mark.asyncio
async def test_svc01_corrupt_hash_file_falls_through_to_resync(
    tmp_config_dir: Path,
    starter_folder_minimal: anyio.Path,
) -> None:
    """D-04: corrupt hash file content is treated as cache miss (no crash)."""
    hash_path = tmp_config_dir / HASH_FILENAME
    # Non-hex garbage plus a comment -- neither line matches the 64-hex contract.
    hash_path.write_text("not-a-valid-hash\n# garbage\n", encoding="utf-8")

    counter = _CallCounter()
    resynced = await run_starter_projects_hash_gate(
        starter_folder=starter_folder_minimal,
        hash_path=hash_path,
        sync_fn=counter,
    )
    assert resynced is True, "corrupt hash file must fall through to full re-sync"
    assert counter.count == 1, (
        f"corrupt-hash gate must fire sync_fn; got {counter.count} calls. "
        "read_hash_file_safe returned something other than None for a corrupt file."
    )
    # After the fall-through, the hash file must now contain a valid digest.
    written = hash_path.read_text(encoding="utf-8")
    first_line = next(
        (ln.strip() for ln in written.splitlines() if ln.strip() and not ln.strip().startswith("#")),
        "",
    )
    assert len(first_line) == 64, (
        f"expected a 64-hex-char sha on the first non-comment line; got {first_line!r}. "
        "write_hash_file_safe was not invoked on the miss path."
    )


@pytest.mark.asyncio
async def test_svc01_missing_hash_file_falls_through_and_writes(
    tmp_config_dir: Path,
    starter_folder_minimal: anyio.Path,
) -> None:
    """D-04: a missing hash file is a cache miss; the full sync runs and persists the hash."""
    hash_path = tmp_config_dir / HASH_FILENAME
    assert not hash_path.exists(), "precondition: hash file must not exist yet"

    counter = _CallCounter()
    resynced = await run_starter_projects_hash_gate(
        starter_folder=starter_folder_minimal,
        hash_path=hash_path,
        sync_fn=counter,
    )
    assert resynced is True, "missing hash file must fall through to full re-sync"
    assert counter.count == 1
    assert hash_path.exists(), "write_hash_file_safe should have created the hash file after a successful re-sync."
