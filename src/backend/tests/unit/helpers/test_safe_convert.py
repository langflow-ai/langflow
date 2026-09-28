import pandas as pd
import pytest
from lfx.helpers.data import safe_convert
from lfx.schema.dataframe import DataFrame

LIMIT = 2000


def _transcript(lines: int = 1000) -> str:
    """A cell shaped like a real transcript: many short lines."""
    return "\n".join(f"Speaker {i % 3}: line {i}" for i in range(lines))


def _protocol(size: int = 100_000) -> str:
    """A cell shaped like a generated protocol: one very wide line.

    Paired with a many-newline cell this is what tabulate amplifies: the wide cell
    sets the table width, the multiline one multiplies the number of padded lines.
    """
    return "word " * (size // 5)


def test_safe_convert_keeps_cells_intact_without_a_limit():
    oversized = "x" * 100_000

    markdown = safe_convert(DataFrame([{"text": oversized}]))

    assert oversized in markdown
    assert "truncated" not in markdown


def test_safe_convert_keeps_short_cells_intact():
    markdown = safe_convert(DataFrame([{"name": "meeting", "id": "42"}]), max_cell_chars=LIMIT)

    assert "meeting" in markdown
    assert "truncated" not in markdown
    assert "<br/>" not in markdown


@pytest.mark.parametrize("length", [LIMIT - 1, LIMIT])
def test_safe_convert_leaves_cells_at_the_limit_alone(length):
    markdown = safe_convert(DataFrame([{"a": "x" * length}]), max_cell_chars=LIMIT)

    assert "truncated" not in markdown


def test_safe_convert_truncates_just_over_the_limit():
    markdown = safe_convert(DataFrame([{"a": "x" * (LIMIT + 1)}]), max_cell_chars=LIMIT)

    assert f"[truncated, {LIMIT + 1} chars]" in markdown


def test_safe_convert_truncates_long_cell():
    oversized = "x" * (LIMIT * 3)

    markdown = safe_convert(DataFrame([{"text": oversized}]), max_cell_chars=LIMIT)

    assert f"[truncated, {len(oversized)} chars]" in markdown
    assert oversized not in markdown


def test_safe_convert_truncates_long_non_string_cell():
    urls = [f"http://storage/{i}.wav" for i in range(500)]

    markdown = safe_convert(DataFrame([{"audio_urls": urls}]), max_cell_chars=LIMIT)

    assert "truncated" in markdown
    assert len(markdown) < LIMIT * 5


def test_safe_convert_preserves_missing_values():
    df = DataFrame([{"a": None, "b": "x" * (LIMIT * 2)}])

    markdown = safe_convert(df, max_cell_chars=LIMIT)

    assert "nan" not in markdown.lower()
    assert "truncated" in markdown


def test_safe_convert_keeps_the_table_parseable_after_truncation():
    df = DataFrame([{"a": "a|b" * LIMIT, "b": "short"}])

    markdown = safe_convert(df, max_cell_chars=LIMIT)
    body = markdown.splitlines()[2]

    assert "truncated" in markdown
    assert body.count("|") - body.count(r"\|") == 3  # two outer pipes + one column separator


@pytest.mark.parametrize("rows", [1, 5])
def test_safe_convert_does_not_amplify_multiline_cells(rows):
    """Tabulate pads every physical line of a cell to the full table width.

    Without a cap, a single row holding a long multiline transcript renders as
    megabytes of markdown; the cap must keep the output proportional to the cap.
    """
    df = DataFrame([{"transcript": _transcript(), "protocol": _protocol()} for _ in range(rows)])

    markdown = safe_convert(df, max_cell_chars=LIMIT)
    unbounded = pd.DataFrame(df.to_dict("records")).to_markdown(index=False)

    assert len(unbounded) > len(markdown) * 100  # without the cap the table inflates by orders of magnitude
    assert len(markdown) < LIMIT * 10 * (rows + 1)


def test_safe_convert_collapses_newlines_in_cells_under_the_limit():
    """A cell under the limit is not truncated, but its newlines would still multiply the padding."""
    chatter = "a\n" * (LIMIT // 4)  # under the limit, but almost all newlines
    df = DataFrame([{"chatter": chatter, "wide": "x" * (LIMIT // 2)}])

    assert len(chatter) < LIMIT

    markdown = safe_convert(df, max_cell_chars=LIMIT)

    assert "truncated" not in markdown
    assert len(markdown) < LIMIT * 20


def test_safe_convert_clean_data_collapses_blank_lines():
    df = DataFrame([{"a": "first\n\n\nsecond"}])

    raw = safe_convert(df)
    cleaned = safe_convert(df, clean_data=True)

    assert raw.count("\n") > cleaned.count("\n")


def test_safe_convert_cleans_before_joining_lines_under_a_limit():
    """clean_data must still collapse blank lines when cells are also capped."""
    df = DataFrame([{"a": "first\n\n\nsecond"}])

    markdown = safe_convert(df, clean_data=True, max_cell_chars=LIMIT)

    assert "first<br/>second" in markdown
