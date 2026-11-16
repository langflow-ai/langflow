import unicodedata


def csv_safe_cell(value: object) -> str:
    """Neutralize spreadsheet formulas; the csv writer does the RFC 4180 quoting."""
    text = "" if value is None else str(value)
    first_visible = next(
        (char for char in text if not char.isspace() and unicodedata.category(char) not in {"Cc", "Cf"}), ""
    )
    return f"'{text}" if first_visible and first_visible in "=+-@" else text
