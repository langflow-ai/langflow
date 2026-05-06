"""D-06 structural assertion + review-coverage enforcement for.

Plan 04-03 replaces two sequential lifespan blocks in
``src/backend/base/langflow/main.py`` with two ``asyncio.gather`` calls (wave 1:
``setup_llm_caching`` + ``copy_profile_pictures``; wave 2:
``load_bundles_with_error_handling`` + ``get_and_cache_all_types_dict``), each
wrapped in the ``_safe_step`` per-task error-isolation helper.

These tests enforce:

- **D-06 / Tests 1-3**: the two gathers exist and their task-name sets match the
  contract seeded in plan 04-02's review tables.
- **D-10 / Test 4**: every callable passed to a gather has a row in the
  co-located review comment block directly above it.
- **Defensive parity / Test 5**: no task is both sequential AND in a gather
  (guards against leaving the old sequential call alongside the new gather).
- **SVC-04 parity / Test 6**: ``initialize_services`` remains a single
  sequential await and is never passed to ``asyncio.gather``.

Source inspection only -- no live database, settings, or event loop needed.
"""

from __future__ import annotations

import inspect
import re

import langflow.main as main_mod
import pytest

from tests.phase_service_init_parity.ast_helpers import (
    extract_gather_task_names,
    find_calls_to,
    parse_lifespan_module,
)

EXPECTED_WAVE_1 = {"setup_llm_caching", "copy_profile_pictures"}
EXPECTED_WAVE_2 = {"load_bundles_with_error_handling", "get_and_cache_all_types_dict"}

# Regex matches an indented ``# | cell1 | ...`` comment-table row. First capture
# is the first cell (between the first and second pipe), which holds the task
# name. Separator rows (``# |---``) and header rows (``# | Task | ...``) are
# filtered downstream. Multi-line cells ending with ``_`` (e.g.,
# ``load_bundles_with_error_``) are stitched with the next row's first cell.
_TABLE_ROW_RE = re.compile(r"^\s*#\s*\|([^|]*)\|")

# Marker that identifies the start of a review comment block. Plan 04-02
# committed this marker verbatim in langflow/main.py.
_REVIEW_HEADER = "D-09 service-dependency review"

# How far to scan backward from a gather call to find its review block header.
# The review block sits 1-3 lines above the gather today; 25 lines is generous
# but still local enough that blocks belonging to other gathers (in shutdown /
# cleanup paths) don't leak in.
_REVIEW_LOOKBACK_LINES = 25


def _extract_table_rows_from_block(lines: list[str]) -> set[str]:
    """Parse a list of comment lines starting from a review block header.

    Same stitching rules as plan 04-02's ``_extract_table_rows``: skip the
    ``Task`` header and separator rows, stitch rows whose first cell ends with
    ``_`` to the next row's first cell, skip blank-first-column wrap rows when
    no continuation is pending.
    """
    names: list[str] = []
    pending: str | None = None
    for line in lines:
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        cell = m.group(1).strip()
        if cell == "Task":
            continue
        if cell.startswith("-"):
            continue
        if pending is not None:
            if cell:
                names.append(pending + cell)
            else:
                names.append(pending)
            pending = None
            continue
        if not cell:
            continue
        if cell.endswith("_"):
            pending = cell
            continue
        names.append(cell)
    if pending is not None:
        names.append(pending)
    return set(names)


def _find_review_block_above(source_lines: list[str], gather_lineno: int) -> list[str]:
    """Return the slice of source lines that contains the block above a gather.

    Scans up to ``_REVIEW_LOOKBACK_LINES`` lines backward from ``gather_lineno``
    (1-indexed AST line numbers, converted to 0-indexed slices) for the
    ``_REVIEW_HEADER`` marker. Returns the lines from the header down to (but
    not including) the gather call itself -- i.e., the comment-table rows.

    Returns an empty list if no header is found in the window.
    """
    # AST line numbers are 1-indexed; source_lines is 0-indexed.
    gather_idx = gather_lineno - 1
    start = max(0, gather_idx - _REVIEW_LOOKBACK_LINES)
    # Scan backwards for the marker.
    header_idx: int | None = None
    for i in range(gather_idx - 1, start - 1, -1):
        if _REVIEW_HEADER in source_lines[i]:
            header_idx = i
            break
    if header_idx is None:
        return []
    return source_lines[header_idx:gather_idx]


@pytest.fixture(scope="module")
def lifespan_tree():
    return parse_lifespan_module()


@pytest.fixture(scope="module")
def lifespan_source() -> str:
    return inspect.getsource(main_mod)


@pytest.fixture(scope="module")
def lifespan_source_lines(lifespan_source: str) -> list[str]:
    # Parse from the same source text that the AST was parsed from. ``main.py``
    # is read by ``parse_lifespan_module`` via ``Path.read_text``; here we get
    # it via ``inspect.getsource`` which returns equivalent text.
    return lifespan_source.splitlines()


@pytest.fixture(scope="module")
def lifespan_gathers(lifespan_tree):
    """Return the gathers in source order, filtered to startup-lifespan gathers.

    Excludes shutdown/cleanup gathers (which have no ``_safe_step`` wrappers
    and no review block above them). The filter is ``extract_gather_task_names``
    returning a non-empty list -- startup gathers always have at least one
    ``_safe_step`` wrapper and therefore yield one or more names; shutdown
    gathers pass bare task lists (or unpacked splats) and yield an empty list.
    """
    all_gathers = find_calls_to(lifespan_tree, "asyncio.gather")
    # Preserve source order.
    return [g for g in all_gathers if extract_gather_task_names(g)]


def test_lifespan_has_two_startup_gathers(lifespan_gathers) -> None:
    """Test 1: two startup-wave gathers exist in the lifespan."""
    assert len(lifespan_gathers) >= 2, (
        f"expected at least two asyncio.gather calls with _safe_step-wrapped tasks "
        f"in langflow/main.py lifespan (wave 1 + wave 2); found {len(lifespan_gathers)}. "
        f"Plan 04-03 landed the two gathers directly below the review blocks."
    )


def test_gather_wave_1_task_set_matches_expected(lifespan_gathers) -> None:
    """Test 2: wave-1 gather task set equals ``EXPECTED_WAVE_1``."""
    wave_1 = lifespan_gathers[0]
    names = set(extract_gather_task_names(wave_1))
    assert names == EXPECTED_WAVE_1, (
        f"wave-1 gather (line {wave_1.lineno}) task set {sorted(names)!r} does "
        f"not match expected {sorted(EXPECTED_WAVE_1)!r}. Adjust the gather "
        f"arguments in langflow/main.py OR the EXPECTED_WAVE_1 constant here."
    )


def test_gather_wave_2_task_set_matches_expected(lifespan_gathers) -> None:
    """Test 3: wave-2 gather task set equals ``EXPECTED_WAVE_2``."""
    wave_2 = lifespan_gathers[1]
    names = set(extract_gather_task_names(wave_2))
    assert names == EXPECTED_WAVE_2, (
        f"wave-2 gather (line {wave_2.lineno}) task set {sorted(names)!r} does "
        f"not match expected {sorted(EXPECTED_WAVE_2)!r}. Adjust the gather "
        f"arguments in langflow/main.py OR the EXPECTED_WAVE_2 constant here."
    )


def test_every_gather_task_has_review_row(
    lifespan_gathers,
    lifespan_source_lines: list[str],
) -> None:
    """Test 4: every task inside a startup gather has a table row.

    For each startup gather, walks backwards from the gather's line number until
    the ``_REVIEW_HEADER`` marker is found, then parses the comment-table rows
    between the header and the gather. Asserts the set of extracted row names
    is a superset of the set of gather task names.

    This is the enforcement: if a reviewer adds a new callable to the
    gather without updating the review table above it, the set inclusion check
    fails and points to the exact gather line number.
    """
    for i, gather in enumerate(lifespan_gathers):
        task_names = set(extract_gather_task_names(gather))
        assert task_names, (
            f"gather #{i} at line {gather.lineno} has no extractable task names; "
            "the _safe_step wrapping convention was broken."
        )
        review_lines = _find_review_block_above(lifespan_source_lines, gather.lineno)
        assert review_lines, (
            f"gather #{i} at line {gather.lineno} has no review block "
            f"within {_REVIEW_LOOKBACK_LINES} lines above it; the 04-02 anchor "
            f"('{_REVIEW_HEADER}') was removed or moved."
        )
        row_names = _extract_table_rows_from_block(review_lines)
        missing = task_names - row_names
        assert not missing, (
            f"gather #{i} at line {gather.lineno} passes task(s) {sorted(missing)!r} "
            f"to asyncio.gather but the review table above it has no row for "
            f"them (extracted rows: {sorted(row_names)!r}). Add a row to the "
            f"review table -- or remove the task from the gather."
        )


def test_no_task_is_both_sequential_and_in_a_gather(lifespan_source: str) -> None:
    """Test 5 (defensive parity): each wave-1/wave-2 task appears only in a gather.

    Scans the lifespan source for bare ``await <task_name>(...)`` lines for each
    expected task. These must NOT appear, because plan 04-03's conversion
    removed the sequential calls. A leftover bare-await indicates the sequential
    block was duplicated rather than replaced.
    """
    for task in EXPECTED_WAVE_1 | EXPECTED_WAVE_2:
        bare_await = re.compile(rf"^\s*await\s+{re.escape(task)}\s*\(", re.MULTILINE)
        matches = bare_await.findall(lifespan_source)
        assert not matches, (
            f"found bare 'await {task}(' call in langflow/main.py lifespan. "
            f"Plan 04-03 moved this task inside asyncio.gather via _safe_step; "
            f"a bare await indicates the old sequential call was left behind. "
            f"Remove the duplicate."
        )


def test_initialize_services_parity_guardrail(
    lifespan_source: str,
    lifespan_gathers,
) -> None:
    """Test 6 (SVC-04 parity): ``initialize_services`` stays a single sequential await.

    Asserts:
    - Exactly one ``await initialize_services(fix_migration=fix_migration)``
      occurrence in the source.
    - That call is not on the same line as an ``asyncio.gather`` (cross-check
      with the lifespan gathers collected via AST).
    """
    call_marker = "await initialize_services(fix_migration=fix_migration)"
    count = lifespan_source.count(call_marker)
    assert count == 1, (
        f"expected exactly 1 '{call_marker}' occurrence in langflow/main.py "
        f"(SVC-04 parity guardrail); got {count}. initialize_services must "
        f"remain a single sequential await."
    )
    for line in lifespan_source.splitlines():
        if "initialize_services" in line and "asyncio.gather" in line:
            pytest.fail(
                "SVC-04 parity violated: initialize_services appears on the same "
                f"line as asyncio.gather. Offending line: {line!r}"
            )
    # Cross-check: none of the AST-collected gathers contain 'initialize_services'
    # as a task name (defense-in-depth against someone formatting the gather
    # across multiple lines in a way the substring check above misses).
    for i, gather in enumerate(lifespan_gathers):
        names = set(extract_gather_task_names(gather))
        assert "initialize_services" not in names, (
            f"SVC-04 parity violated: gather #{i} at line {gather.lineno} includes initialize_services as a task."
        )
