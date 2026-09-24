"""Prepare the authentication default in a disposable release checkout."""

from pathlib import Path

from .parsing import parse_auto_login_default


def prepare_release_source(source: bytes) -> bytes:
    """Return release source bytes with only the AUTO_LOGIN literal changed.

    The result is idempotent and preserves unrelated settings and formatting.
    Invalid source raises before callers write anything to disk or Git.
    """
    default = parse_auto_login_default(source)
    if default.value is False:
        return source
    # AST column offsets are UTF-8 byte offsets. Preserve every other byte,
    # including comments, line endings, and unrelated authentication defaults.
    lines = source.splitlines(keepends=True)
    start = sum(map(len, lines[: default.lineno - 1])) + default.col_offset
    end = start + len(b"True")
    prepared = source[:start] + b"False" + source[end:]
    if parse_auto_login_default(prepared).value is not False:
        msg = "Failed to disable auto-login in the release source"
        raise ValueError(msg)
    return prepared


def prepare_release_auth(path: Path) -> None:
    """Set only AUTO_LOGIN's default to False in a release build checkout."""
    path.write_bytes(prepare_release_source(path.read_bytes()))
