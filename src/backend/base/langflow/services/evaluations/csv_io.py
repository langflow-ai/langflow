"""CSV import and export for dataset items."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langflow.services.evaluations.schemas import TEXT_MAX_CHARS
from langflow.utils.csv_safety import csv_safe_cell

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

PREVIEW_ROWS = 5
SNIFF_SAMPLE_CHARS = 64 * 1024
CANDIDATE_DELIMITERS = ",;\t|"
EXPORT_HEADERS = ("input", "expected_output")

# Process-wide and only ever raised: restoring it per read would race concurrent imports.
csv.field_size_limit(max(csv.field_size_limit(), TEXT_MAX_CHARS * 2))


class CsvFormatError(ValueError):
    """The upload is not a readable CSV with a header row."""


@dataclass(frozen=True)
class ParsedRow:
    input: str
    expected_output: str | None


@dataclass
class ImportPlan:
    rows: list[ParsedRow] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)


def decode_upload(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        msg = "The file is not UTF-8 encoded. Save it as CSV UTF-8 and try again."
        raise CsvFormatError(msg) from exc


class _SingleColumn(csv.excel):
    # A header without any candidate delimiter means one column: commas in the text are not separators.
    delimiter = "\x1f"


def _header_line(text: str) -> str:
    for line in text[:SNIFF_SAMPLE_CHARS].splitlines():
        if line.strip():
            return line
    return ""


def _dialect(text: str) -> type[csv.Dialect]:
    """Pick the delimiter from the header row only: data rows often contain commas or semicolons."""
    header = _header_line(text)
    counts = {delimiter: header.count(delimiter) for delimiter in CANDIDATE_DELIMITERS}
    delimiter, count = max(counts.items(), key=lambda pair: pair[1])
    if count == 0:
        return _SingleColumn
    return type("_Detected", (csv.excel,), {"delimiter": delimiter})


def _reader(text: str) -> Iterator[list[str]]:
    try:
        yield from csv.reader(io.StringIO(text, newline=""), dialect=_dialect(text))
    except csv.Error as exc:
        msg = f"The file could not be read as CSV: {exc}"
        raise CsvFormatError(msg) from exc


def _headers(rows: Iterator[list[str]]) -> list[str]:
    for row in rows:
        if any(cell.strip() for cell in row):
            return [cell.strip() for cell in row]
    msg = "The file has no header row."
    raise CsvFormatError(msg)


def preview(text: str) -> tuple[list[str], list[list[str]], int]:
    rows = _reader(text)
    headers = _headers(rows)
    sample: list[list[str]] = []
    total = 0
    for row in rows:
        if not any(cell.strip() for cell in row):
            continue
        total += 1
        if len(sample) < PREVIEW_ROWS:
            sample.append(row)
    return headers, sample, total


def _column_index(headers: list[str], column: str | None, *, required: bool) -> int | None:
    if column is None:
        if required:
            msg = "Choose the column that holds the input."
            raise CsvFormatError(msg)
        return None
    if column not in headers:
        msg = f"Column {column!r} is not in the file. Columns: {', '.join(headers)}"
        raise CsvFormatError(msg)
    return headers.index(column)


def _cell(row: list[str], index: int | None) -> str | None:
    if index is None or index >= len(row):
        return None
    return row[index]


def plan_import(text: str, *, input_column: str, expected_column: str | None, max_rows: int) -> ImportPlan:
    rows = _reader(text)
    headers = _headers(rows)
    input_index = _column_index(headers, input_column, required=True)
    expected_index = _column_index(headers, expected_column, required=False)
    plan = ImportPlan()
    for line_number, row in enumerate(rows, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(plan.rows) >= max_rows:
            extra = 1 + sum(1 for rest in rows if any(cell.strip() for cell in rest))
            plan.skipped.append((line_number, f"Row limit of {max_rows} reached: {extra} more rows were not imported"))
            break
        input_text = (_cell(row, input_index) or "").strip()
        if not input_text:
            plan.skipped.append((line_number, "Input is empty"))
            continue
        expected = _cell(row, expected_index)
        expected = expected.strip() if expected is not None and expected.strip() else None
        if len(input_text) > TEXT_MAX_CHARS or (expected is not None and len(expected) > TEXT_MAX_CHARS):
            plan.skipped.append((line_number, f"A cell is longer than {TEXT_MAX_CHARS} characters"))
            continue
        plan.rows.append(ParsedRow(input=input_text, expected_output=expected))
    return plan


def export_rows(rows: Iterable[tuple[str, str | None]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(EXPORT_HEADERS)
    yield "﻿" + buffer.getvalue()
    for input_text, expected in rows:
        buffer.seek(0)
        buffer.truncate()
        writer.writerow([csv_safe_cell(input_text), csv_safe_cell(expected)])
        yield buffer.getvalue()
