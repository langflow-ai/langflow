from unittest.mock import patch

from lfx.base.data.utils import read_text_file


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
