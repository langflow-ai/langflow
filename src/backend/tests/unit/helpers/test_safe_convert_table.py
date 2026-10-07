"""safe_convert must render a table in size proportional to its data.

tabulate turns every newline inside a cell into its own physical line and pads each one
to the full table width, so a multiline cell used to inflate a 242 KB row into 122 MB of
markdown (Loop.done -> Chat Output took workers down with OOMKilled).
"""

import pytest
from lfx.helpers.data import safe_convert
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


def _meeting_row(i: int) -> Data:
    protocol = "\n".join(f"{j}. " + "Decision item text " * 6 for j in range(1061))[:131_099]
    transcript = " ".join(f"Speaker {j % 3}: phrase {j}." for j in range(12000))[:120_041]
    return Data(data={"text": transcript, "protocol_text": protocol, **{f"field_{k}": f"v{i}-{k}" for k in range(21)}})


def _cell_chars(table: DataFrame) -> int:
    return sum(len(str(value)) for row in table.itertuples(index=False) for value in row)


def test_should_stay_proportional_to_data_when_cells_hold_long_multiline_text():
    table = DataFrame([_meeting_row(i) for i in range(3)])

    markdown = safe_convert(table)

    assert len(markdown) < 3 * _cell_chars(table)


def test_should_render_one_physical_line_per_row_when_cells_contain_newlines():
    table = DataFrame([{"name": "a", "notes": "line one\nline two\nline three"}, {"name": "b", "notes": "single"}])

    markdown = safe_convert(table)

    lines = markdown.splitlines()
    assert len(lines) == 4
    assert "line one<br/>line two<br/>line three" in lines[2]
    assert "single" in lines[3]


@pytest.mark.parametrize("line_break", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
def test_should_render_one_physical_line_per_row_for_any_line_break(line_break):
    table = DataFrame([{"name": "a", "notes": line_break.join(["line one", "line two", "line three"])}])

    markdown = safe_convert(table)

    assert len(markdown.split("\n")) == 3
    assert "\r" not in markdown
    assert "line one<br/>line two<br/>line three" in markdown


def test_should_collapse_blank_lines_before_joining_when_clean_data_is_set():
    table = DataFrame([{"notes": "first\n\n\nsecond"}])

    markdown = safe_convert(table, clean_data=True)

    assert "first<br/>second" in markdown
    assert "<br/><br/>" not in markdown


def test_should_keep_escaping_pipes_when_rendering_a_table():
    table = DataFrame([{"expr": "a | b"}])

    markdown = safe_convert(table)

    assert r"a \| b" in markdown
