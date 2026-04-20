"""D-10 precondition enforcement: dependency-review comment blocks.

These tests assert that ``src/backend/base/langflow/main.py`` contains the two
review comment blocks (wave 1 + wave 2) that anchor where will
insert its ``asyncio.gather`` calls. The actual gather + task-name cross-check
lives in plan 04-03's own test; this module only guards the review anchor.

Also asserts the parity guardrail: ``initialize_services`` is called
exactly once and is NOT passed to ``asyncio.gather``.

Source inspection only -- no live database, settings, or event loop needed.
"""

from __future__ import annotations

import inspect
import re

import langflow.main as main_mod
import pytest

EXPECTED_WAVE_1 = {"setup_llm_caching", "copy_profile_pictures"}
EXPECTED_WAVE_2 = {"load_bundles_with_error_handling", "get_and_cache_all_types_dict"}

# Regex: an indented ``# |`` comment-table row. First capture = cell 1 contents
# (everything between the first and second pipe, whitespace-trimmed).
# Separator rows (``# |---``) are filtered downstream by checking for ``-`` at
# the start of the captured text.
_TABLE_ROW_RE = re.compile(r"^\s*#\s*\|([^|]*)\|")


def _extract_table_rows(source: str, marker: str) -> set[str]:
    """Return the set of task names from the table following ``marker``.

    Scans forward up to 25 lines from the line containing ``marker``, collects
    first-column cells of comment-table rows (``# | ... | ... | ... |``), skips
    the header row (``Task``), skips separator rows (``|---``), and stitches
    multi-line cells.

    Multi-line cells are detected as rows whose first column ends with ``_``
    (e.g., ``load_bundles_with_error_``). The next row's first column is
    assumed to be the continuation (e.g., ``handling``) and is concatenated
    without the trailing underscore drop -- the underscore is the literal
    connector between the two lines in the review block.
    """
    lines = source.splitlines()
    # Locate the first line containing the marker.
    start = next((i for i, line in enumerate(lines) if marker in line), None)
    if start is None:
        return set()

    names: list[str] = []
    pending: str | None = None
    for line in lines[start : start + 25]:
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        cell = m.group(1).strip()
        # Skip the header row.
        if cell == "Task":
            continue
        # Skip separator rows (``# |-----|-----|-----|``).
        if cell.startswith("-"):
            continue
        if pending is not None:
            # Second half of a multi-line cell: first-column continuation OR
            # a blank first-column row that belongs to the previous task. If
            # the current cell is non-empty, treat it as the continuation name
            # fragment (e.g., "handling"). If empty, the previous cell was a
            # complete name whose Reads/Writes wrap; keep the name as-is.
            if cell:
                names.append(pending + cell)
            else:
                names.append(pending)
            pending = None
            continue
        # Blank first-column rows (wrap-only rows for the previous task) are
        # skipped outright when there's no pending continuation.
        if not cell:
            continue
        if cell.endswith("_"):
            # First half of a multi-line cell (e.g., "load_bundles_with_error_").
            pending = cell
            continue
        # Single-line cell.
        names.append(cell)

    if pending is not None:
        # Dangling continuation (malformed table); surface as-is so tests fail loudly.
        names.append(pending)

    return set(names)


@pytest.fixture(scope="module")
def lifespan_source() -> str:
    return inspect.getsource(main_mod)


def test_wave_1_review_block_present(lifespan_source: str) -> None:
    """Test 1: wave-1 review block anchors the future gather insertion point."""
    if lifespan_source.count("SVC-02 wave 1") != 1:
        pytest.fail(
            "expected exactly one 'SVC-02 wave 1' marker in langflow/main.py; "
            f"got {lifespan_source.count('SVC-02 wave 1')}. The review block "
            "anchor for plan 04-03's wave-1 gather is missing or duplicated."
        )
    if "D-09 service-dependency review" not in lifespan_source:
        pytest.fail(
            "expected 'D-09 service-dependency review' marker in langflow/main.py; "
            "the review block header was removed or renamed."
        )
    # Both wave-1 tasks appear somewhere after the wave-1 marker.
    wave_1_slice = lifespan_source.split("SVC-02 wave 1", 1)[1].splitlines()[:20]
    wave_1_text = "\n".join(wave_1_slice)
    for task in EXPECTED_WAVE_1:
        if task not in wave_1_text:
            pytest.fail(
                f"expected task '{task}' inside the wave-1 review block (first 20 "
                f"lines after 'SVC-02 wave 1' marker); got block:\n{wave_1_text}"
            )


def test_wave_2_review_block_present(lifespan_source: str) -> None:
    """Test 2: wave-2 review block anchors the future gather insertion point."""
    if lifespan_source.count("SVC-02 wave 2") != 1:
        pytest.fail(
            "expected exactly one 'SVC-02 wave 2' marker in langflow/main.py; "
            f"got {lifespan_source.count('SVC-02 wave 2')}. The review block "
            "anchor for plan 04-03's wave-2 gather is missing or duplicated."
        )
    wave_2_slice = lifespan_source.split("SVC-02 wave 2", 1)[1].splitlines()[:20]
    wave_2_text = "\n".join(wave_2_slice)
    # Wave-2 row uses a multi-line cell for load_bundles_with_error_handling:
    # the first half ("load_bundles_with_error_") is what appears on one comment line.
    for fragment in ("load_bundles_with_error_", "get_and_cache_all_types_dict"):
        if fragment not in wave_2_text:
            pytest.fail(
                f"expected task fragment '{fragment}' inside the wave-2 review "
                f"block (first 20 lines after 'SVC-02 wave 2' marker); got "
                f"block:\n{wave_2_text}"
            )


def test_table_rows_match_expected_sets(lifespan_source: str) -> None:
    """Test 3: parsed task-name set equals the contract 04-03 must honor.

    Uses ``_extract_table_rows`` which handles the multi-line
    ``load_bundles_with_error_`` / ``handling`` cell by stitching rows whose
    first column ends with ``_``.
    """
    got_wave_1 = _extract_table_rows(lifespan_source, "SVC-02 wave 1")
    if got_wave_1 != EXPECTED_WAVE_1:
        pytest.fail(
            f"wave-1 parsed task set {sorted(got_wave_1)!r} does not match the "
            f"contract {sorted(EXPECTED_WAVE_1)!r} that will pass to "
            "asyncio.gather. Update the review table OR the EXPECTED_WAVE_1 "
            "constant (whichever is authoritative) before 04-03 lands."
        )
    got_wave_2 = _extract_table_rows(lifespan_source, "SVC-02 wave 2")
    if got_wave_2 != EXPECTED_WAVE_2:
        pytest.fail(
            f"wave-2 parsed task set {sorted(got_wave_2)!r} does not match the "
            f"contract {sorted(EXPECTED_WAVE_2)!r} that will pass to "
            "asyncio.gather. Update the review table OR the EXPECTED_WAVE_2 "
            "constant (whichever is authoritative) before 04-03 lands."
        )


def test_initialize_services_parity_guardrail(lifespan_source: str) -> None:
    """Test 4: parity -- initialize_services stays a single sequential await.

    Asserts:
    - ``await initialize_services(fix_migration=fix_migration)`` appears exactly once.
    - No ``asyncio.gather`` on the same line as ``initialize_services`` (defensive:
      someone later moving services init into a gather would silently break).
    """
    call_marker = "await initialize_services(fix_migration=fix_migration)"
    call_count = lifespan_source.count(call_marker)
    if call_count != 1:
        pytest.fail(
            f"expected exactly 1 '{call_marker}' occurrence in langflow/main.py "
            f"(SVC-04 parity guardrail); got {call_count}. initialize_services "
            "must remain a sequential await."
        )
    for line in lifespan_source.splitlines():
        if "initialize_services" in line and "asyncio.gather" in line:
            pytest.fail(
                "SVC-04 parity violated: initialize_services appears on the same "
                f"line as asyncio.gather. Offending line: {line!r}"
            )
