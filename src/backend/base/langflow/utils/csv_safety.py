def csv_safe_cell(value: object) -> str:
    """Neutralize spreadsheet formulas; the csv writer does the RFC 4180 quoting."""
    text = "" if value is None else str(value)
    first_visible = text.lstrip("\x00\t\n\r ")[:1]
    return f"'{text}" if first_visible and first_visible in "=+-@" else text
