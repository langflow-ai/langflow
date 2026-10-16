from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from lfx.base.data.utils import (
    _detect_encoding_with_fallbacks,
    parse_text_file_to_data,
    read_text_file,
    read_text_file_async,
)
from lfx.utils.async_helpers import run_until_complete


class TestReadTextFile:
    def test_utf8_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Hello world", encoding="utf-8")
        assert read_text_file(str(f)) == "Hello world"

    def test_chinese_characters_utf8(self, tmp_path):
        content = "# 新概念物理教程\n这是一个测试文件"
        f = tmp_path / "chinese.md"
        f.write_text(content, encoding="utf-8")
        assert read_text_file(str(f)) == content

    def test_latin1_file(self, tmp_path):
        content = "café résumé naïve"
        f = tmp_path / "latin.txt"
        f.write_bytes(content.encode("latin-1"))
        # chardet may detect as latin-1 or fall through; either way should not raise
        result = read_text_file(str(f))
        assert "caf" in result

    def test_chardet_returns_none(self, tmp_path):
        """read_text_file should not crash when chardet returns None encoding."""
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        with patch("lfx.base.data.utils.chardet.detect", return_value={"encoding": None, "confidence": 0.0}):
            result = read_text_file(str(f))
        assert result == "hello"

    def test_chardet_returns_invalid_encoding(self, tmp_path):
        """read_text_file should fall back when chardet returns an unrecognized encoding."""
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        with patch("lfx.base.data.utils.chardet.detect", return_value={"encoding": "FAKE-ENCODING", "confidence": 1.0}):
            result = read_text_file(str(f))
        assert result == "hello"

    def test_binary_like_content_falls_back_to_latin1(self, tmp_path):
        """Files with bytes that aren't valid in detected encoding should fall back gracefully."""
        # Create bytes that are valid latin-1 but not valid utf-8
        raw = bytes(range(128, 256))
        f = tmp_path / "binary.txt"
        f.write_bytes(raw)
        # Should not raise, should fall back to latin-1
        result = read_text_file(str(f))
        assert len(result) == 128


class TestParseTextFileToDataS3Mode:
    """Regression tests for issue #13798.

    When S3 storage is configured, reading a real local file (e.g. the bundled
    lfx components directory the Langflow Assistant scans) must still read from
    disk instead of being forced through the S3 key parser.
    """

    def test_should_read_existing_local_file_when_storage_type_is_s3(self, tmp_path):
        """A real local file on disk must be read locally even when storage_type is s3.

        Local reads outside the storage scope require the operator opt-out
        (``restrict_local_file_access=False``), which is the default only before 1.12.3.
        """
        local_file = tmp_path / "_importing.py"
        local_file.write_text("x = 1\n", encoding="utf-8")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"
        mock_settings.settings.restrict_local_file_access = False

        with (
            patch("lfx.base.data.utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.utils.file_path_security.get_settings_service", return_value=mock_settings),
        ):
            result = parse_text_file_to_data(str(local_file), silent_errors=False)

        assert result is not None
        assert result.data["text"] == "x = 1\n"
        assert result.data["file_path"] == str(local_file)


class TestWindows1252TextDecoding:
    """Regression coverage for issue #15702.

    Files saved as Windows-1252 whose 0x80-0x9F bytes carry curly quotes, dashes or
    the euro sign used to come back as control characters: the fallback chain threw
    the chardet Windows-1252 guess away and let latin-1 decode those bytes instead.
    """

    # "He said \u201chello\u201d and it costs 5\u20ac \u2013 really." in Windows-1252.
    # 0x93/0x94 are the curly quotes, 0x80 the euro sign and 0x96 the en dash -- every
    # one of them a C1 control character in latin-1.
    _SMART_PUNCTUATION = "He said \u201chello\u201d and it costs 5\u20ac \u2013 really.\n"

    # Longer sample so chardet has more than a handful of bytes to go on.
    _ACCENTED = "Le caf\u00e9 est tr\u00e8s chaud ; il co\u00fbte 5 \u20ac, n'est-ce pas ? Oui, vraiment.\n"

    # A curly quote directly followed by a letter. gb18030 accepts that byte pair
    # (0x92 + "t" is a legal two-byte sequence decoding to U+62B0), so a chain that
    # tries gb18030 before the Windows-1252 guess returns mojibake for this file.
    _QUOTE_THEN_LETTER = "I don\u2019t know what you mean, it\u2019s fine.\n"

    @staticmethod
    def _write(path, text, encoding):
        Path(path).write_bytes(text.encode(encoding))

    def test_smart_punctuation_is_decoded_as_written(self, tmp_path):
        """A Windows-1252 file keeps its quotes, euro sign and dashes."""
        target = tmp_path / "smart.txt"
        self._write(target, self._SMART_PUNCTUATION, "cp1252")

        assert read_text_file(str(target)) == self._SMART_PUNCTUATION

    def test_accents_and_euro_sign_in_a_longer_windows_1252_file(self, tmp_path):
        """Accented Windows-1252 text is not mangled by the latin-1 last resort."""
        target = tmp_path / "accents.txt"
        self._write(target, self._ACCENTED, "cp1252")

        assert read_text_file(str(target)) == self._ACCENTED

    def test_windows_1252_guess_precedes_gb18030(self, tmp_path):
        """A 0x92 byte followed by a letter must not be eaten by gb18030."""
        target = tmp_path / "quote.txt"
        self._write(target, self._QUOTE_THEN_LETTER, "cp1252")

        assert read_text_file(str(target)) == self._QUOTE_THEN_LETTER

    def test_async_reader_decodes_windows_1252_like_the_sync_one(self):
        """read_text_file_async shares the fallback chain, so it agrees."""
        raw = self._SMART_PUNCTUATION.encode("cp1252")
        # Stub the storage fetch: read_text_file_async is on the other side of the local
        # file access policy, and the bug is in the decoding step behind it.
        # read_text_file_async imports read_file_bytes locally, so patch it at its source.
        with patch("lfx.base.data.storage_utils.read_file_bytes", AsyncMock(return_value=raw)):
            decoded = run_until_complete(read_text_file_async("ignored.txt"))

        assert decoded == self._SMART_PUNCTUATION

    @pytest.mark.parametrize(
        ("encoding", "content"),
        [
            ("utf-8", "\u4e2d\u6587\u6d4b\u8bd5\u5185\u5bb9\uff0c\u5305\u542b\u6807\u70b9\u7b26\u53f7\u3002\n"),
            ("utf-8", "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8\u30c6\u30ad\u30b9\u30c8\u3067\u3059\u3002\n"),
            ("gb18030", "\u4e2d\u6587\u6d4b\u8bd5\u5185\u5bb9\uff0c\u5305\u542b\u6807\u70b9\u7b26\u53f7\u3002\n"),
            ("big5", "\u6e2c\u8a66\u7e41\u9ad4\u4e2d\u6587\u5167\u5bb9\u3002\n"),
        ],
    )
    def test_multibyte_files_are_untouched(self, tmp_path, encoding, content):
        """Chinese, Japanese and traditional-Chinese files still decode correctly.

        The Windows-1252 candidate only takes over once utf-8 has failed, so anything
        that already decoded with utf-8 is unaffected.
        """
        target = tmp_path / f"sample.{encoding}"
        self._write(target, content, encoding)

        assert read_text_file(str(target)) == content

    def test_detected_windows_1252_guess_is_kept_in_the_chain(self, monkeypatch):
        """The chain still tries utf-8 first, but no longer drops the guess entirely."""
        monkeypatch.setattr(
            "lfx.base.data.utils.chardet.detect",
            lambda _bytes: {"encoding": "Windows-1252", "confidence": 0.07},
        )

        chain = _detect_encoding_with_fallbacks(self._QUOTE_THEN_LETTER.encode("cp1252"))

        assert chain[0] == "utf-8"
        assert chain.index("Windows-1252") < chain.index("gb18030")
        assert chain.index("Windows-1252") < chain.index("latin-1")
