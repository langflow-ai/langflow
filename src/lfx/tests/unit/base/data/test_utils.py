from unittest.mock import Mock, patch

import pytest
from lfx.base.data.utils import parse_text_file_to_data, read_text_file, read_text_file_async
from lfx.services.deps import get_settings_service


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
        assert read_text_file(str(f), encoding="latin-1") == content

    def test_cp1252_file_with_smart_quotes(self, tmp_path):
        """A Windows-1252 file must not come back as latin-1 control characters.

        chardet reports Windows-1252 for this file; latin-1 maps those bytes to
        control characters, so the file must be decoded as cp1252 instead.
        """
        content = "He said “hello” and it costs 5€ – really.\n"  # noqa: RUF001
        f = tmp_path / "smart.txt"
        f.write_bytes(content.encode("cp1252"))
        assert read_text_file(str(f)) == content

    def test_cp1252_file_detected_as_macroman(self, tmp_path):
        """gb18030 decodes some cp1252 punctuation, so cp1252 must be tried first.

        chardet reports MacRoman for this file, and gb18030 accepts those bytes as
        a CJK sequence, which silently turned the apostrophe into mojibake.
        """
        content = "It’s fine\n"  # noqa: RUF001
        f = tmp_path / "apostrophe.txt"
        f.write_bytes(content.encode("cp1252"))
        assert read_text_file(str(f)) == content

    def test_cp1252_fallback_does_not_shadow_gb18030(self):
        """cp1252 stays behind gb18030 for files chardet does not call Windows-1252."""
        from lfx.base.data.utils import _detect_encoding_with_fallbacks

        chain = _detect_encoding_with_fallbacks("中文测试文件内容\n".encode("gb18030"))
        assert chain.index("gb18030") < chain.index("cp1252")

    @pytest.mark.parametrize("reader", ["sync", "async"])
    @pytest.mark.parametrize(
        ("content", "encoding"),
        [
            ("😀", "gb18030"),
            ("Hello 😀\n", "gb18030"),
            ("He said “hello” and it costs 5€ – really.\n", "cp1252"),  # noqa: RUF001
            ("It’s fine\n", "cp1252"),  # noqa: RUF001
            ("Hello 😀\n", "utf-8"),
        ],
    )
    async def test_text_encoding_round_trip(self, tmp_path, monkeypatch, reader, content, encoding):
        """Both readers preserve GB18030 four-byte characters and Windows punctuation."""
        settings = get_settings_service().settings
        monkeypatch.setattr(settings, "storage_type", "local")
        monkeypatch.setattr(settings, "restrict_local_file_access", False)
        f = tmp_path / "encoded.txt"
        f.write_bytes(content.encode(encoding))

        result = await read_text_file_async(str(f)) if reader == "async" else read_text_file(str(f))

        assert result == content

    @pytest.mark.parametrize("reader", ["sync", "async"])
    @pytest.mark.parametrize("detected_encoding", ["Windows-1252", "Windows-1254", "MacRoman"])
    @pytest.mark.parametrize(
        ("content", "encoding"),
        [("Hello 😀\n", "gb18030"), ("It’s fine: „9„9\n", "cp1252")],  # noqa: RUF001
    )
    async def test_four_byte_encoding_with_ambiguous_detection(
        self, tmp_path, monkeypatch, reader, detected_encoding, content, encoding
    ):
        """Invalid GB18030 patterns still fall back to Windows-1252 punctuation."""
        settings = get_settings_service().settings
        monkeypatch.setattr(settings, "storage_type", "local")
        monkeypatch.setattr(settings, "restrict_local_file_access", False)
        f = tmp_path / "ambiguous.txt"
        f.write_bytes(content.encode(encoding))

        with patch(
            "lfx.base.data.utils.chardet.detect", return_value={"encoding": detected_encoding, "confidence": 0.1}
        ):
            result = await read_text_file_async(str(f)) if reader == "async" else read_text_file(str(f))

        assert result == content

    @pytest.mark.parametrize("reader", ["sync", "async"])
    async def test_gb18030_sequence_at_sample_boundary(self, tmp_path, monkeypatch, reader):
        """Detection must not truncate a four-byte sequence into a cp1252 guess."""
        from lfx.base.data.utils import _CHARDET_SAMPLE_BYTES

        settings = get_settings_service().settings
        monkeypatch.setattr(settings, "storage_type", "local")
        monkeypatch.setattr(settings, "restrict_local_file_access", False)
        content = "a" * (_CHARDET_SAMPLE_BYTES - 1) + "😀"
        f = tmp_path / "boundary.txt"
        f.write_bytes(content.encode("gb18030"))

        with patch("lfx.base.data.utils.chardet.detect", return_value={"encoding": "Windows-1252", "confidence": 0.1}):
            result = await read_text_file_async(str(f)) if reader == "async" else read_text_file(str(f))

        assert result == content

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
