r"""Tests for ``chunk_text_for_ingestion`` — the splitter every KB ingestion path uses.

A user-supplied separator is the *preferred* split point, not the only one:
text between two separators that is still longer than ``chunk_size`` must be
split further, exactly as the ``/preview-chunks`` endpoint shows it.
"""

import pytest
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langflow.api.utils.kb_helpers import chunk_text_for_ingestion

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _line(length: int, word: str = "lorem") -> str:
    """Return a single line of space-separated words, at least ``length`` characters long."""
    words = []
    while len(" ".join(words)) < length:
        words.append(word)
    return " ".join(words)


@pytest.mark.parametrize("separator", ["\n", "\\n"])
def test_segments_longer_than_chunk_size_are_split(separator):
    text = "\n".join(_line(1500) for _ in range(3))

    chunks = chunk_text_for_ingestion(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separator=separator)

    assert len(chunks) > 3
    assert max(len(chunk) for chunk in chunks) <= CHUNK_SIZE


def test_single_line_longer_than_chunk_size_is_not_stored_whole():
    text = _line(60_000)

    chunks = chunk_text_for_ingestion(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separator="\\n")

    assert len(chunks) > 1
    assert max(len(chunk) for chunk in chunks) <= CHUNK_SIZE


def test_split_segments_keep_the_requested_overlap():
    text = _line(3000)

    chunks = chunk_text_for_ingestion(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separator="\\n")

    # Consecutive chunks share a tail/head when the splitter falls back to words.
    assert all(chunks[i][-50:] in chunks[i + 1] for i in range(len(chunks) - 1))


def test_user_separator_is_still_the_preferred_split_point():
    text = "x" * 50 + "|" + "y" * 50

    chunks = chunk_text_for_ingestion(text, chunk_size=60, chunk_overlap=0, separator="|")

    assert chunks[0] == "x" * 50


def test_escaped_tab_separator_is_unescaped():
    text = "a" * 600 + "\t" + "b" * 600

    chunks = chunk_text_for_ingestion(text, chunk_size=CHUNK_SIZE, chunk_overlap=0, separator="\\t")

    assert chunks == ["a" * 600, "b" * 600]


@pytest.mark.parametrize("separator", [None, ""])
def test_no_separator_uses_splitter_defaults(separator):
    """Memory Base ingestion passes no separator; its chunking must not change."""
    text = "\n\n".join(_line(700, word=w) for w in ("alpha", "beta", "gamma"))
    expected = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_text(text)

    assert chunk_text_for_ingestion(text, chunk_size=500, chunk_overlap=50, separator=separator) == expected


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_blank_text_yields_no_chunks(text):
    assert chunk_text_for_ingestion(text, separator="\\n") == []
