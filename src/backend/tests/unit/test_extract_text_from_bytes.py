from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from lfx.base.data.utils import extract_text_from_bytes
from pypdf import PdfWriter

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DOCX_NAMESPACES = (
    f'xmlns:w="{_W_NS}" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)


def _docx_with_body(*fragments: str) -> bytes:
    """Build a DOCX whose body holds the given WordprocessingML fragments, in order."""
    from docx import Document
    from docx.oxml import parse_xml

    doc = Document()
    section_properties = doc.element.body[-1]
    for element in list(parse_xml(f"<w:body {_DOCX_NAMESPACES}>{''.join(fragments)}</w:body>")):
        section_properties.addprevious(element)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _run(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


def _make_blank_pdf(num_pages: int = 1) -> bytes:
    """Create a valid PDF with blank pages."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _mock_pdf_reader(pages_text: list[str]):
    """Create a mock PdfReader that returns pages with given text."""
    mock_reader = MagicMock()
    mock_pages = []
    for text in pages_text:
        page = MagicMock()
        page.extract_text.return_value = text
        mock_pages.append(page)
    mock_reader.pages = mock_pages
    mock_reader.__enter__ = MagicMock(return_value=mock_reader)
    mock_reader.__exit__ = MagicMock(return_value=False)
    return mock_reader


class TestExtractTextFromBytesPDF:
    @patch("lfx.base.data.utils.PdfReader")
    def test_should_extract_text_from_valid_pdf(self, mock_reader_cls):
        mock_reader_cls.return_value = _mock_pdf_reader(["Hello World"])
        result = extract_text_from_bytes("document.pdf", _make_blank_pdf())
        assert "Hello World" in result

    @patch("lfx.base.data.utils.PdfReader")
    def test_should_extract_text_from_multi_page_pdf(self, mock_reader_cls):
        mock_reader_cls.return_value = _mock_pdf_reader(["Page one content", "Page two content"])
        result = extract_text_from_bytes("multi.pdf", _make_blank_pdf(2))
        assert "Page one content" in result
        assert "Page two content" in result

    @patch("lfx.base.data.utils.PdfReader")
    def test_should_join_pages_with_double_newline(self, mock_reader_cls):
        mock_reader_cls.return_value = _mock_pdf_reader(["First", "Second"])
        result = extract_text_from_bytes("test.pdf", _make_blank_pdf(2))
        assert result == "First\n\nSecond"

    @patch("lfx.base.data.utils.PdfReader")
    def test_should_be_case_insensitive_on_extension(self, mock_reader_cls):
        mock_reader_cls.return_value = _mock_pdf_reader(["Test"])
        result = extract_text_from_bytes("DOC.PDF", _make_blank_pdf())
        assert "Test" in result

    def test_should_raise_value_error_for_corrupted_pdf(self):
        with pytest.raises(ValueError, match="Failed to parse PDF file"):
            extract_text_from_bytes("bad.pdf", b"this is not a pdf")

    def test_should_raise_value_error_for_empty_pdf_bytes(self):
        with pytest.raises(ValueError, match="Failed to parse PDF file"):
            extract_text_from_bytes("empty.pdf", b"")

    def test_should_handle_pdf_with_blank_pages(self):
        result = extract_text_from_bytes("blank.pdf", _make_blank_pdf())
        assert isinstance(result, str)

    @patch("lfx.base.data.utils.PdfReader")
    def test_should_handle_page_returning_none(self, mock_reader_cls):
        mock_reader_cls.return_value = _mock_pdf_reader(["Text"])
        mock_reader_cls.return_value.pages[0].extract_text.return_value = None
        mock_reader_cls.return_value.__enter__.return_value = mock_reader_cls.return_value
        result = extract_text_from_bytes("null_page.pdf", _make_blank_pdf())
        assert isinstance(result, str)


class TestExtractTextFromBytesDOCX:
    def test_should_extract_text_from_valid_docx(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("Hello from DOCX")
        buf = BytesIO()
        doc.save(buf)

        result = extract_text_from_bytes("file.docx", buf.getvalue())
        assert "Hello from DOCX" in result

    def test_should_extract_multiple_paragraphs(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("First paragraph")
        doc.add_paragraph("Second paragraph")
        buf = BytesIO()
        doc.save(buf)

        result = extract_text_from_bytes("file.docx", buf.getvalue())
        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "\n\n" in result

    def test_should_be_case_insensitive_on_extension(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("Case test")
        buf = BytesIO()
        doc.save(buf)

        result = extract_text_from_bytes("FILE.DOCX", buf.getvalue())
        assert "Case test" in result

    def test_should_raise_value_error_for_corrupted_docx(self):
        with pytest.raises(ValueError, match="Failed to parse DOCX file"):
            extract_text_from_bytes("bad.docx", b"not a valid docx")

    def test_should_raise_value_error_for_empty_docx_bytes(self):
        with pytest.raises(ValueError, match="Failed to parse DOCX file"):
            extract_text_from_bytes("empty.docx", b"")

    def test_should_handle_docx_with_no_paragraphs(self):
        from docx import Document

        doc = Document()
        buf = BytesIO()
        doc.save(buf)

        result = extract_text_from_bytes("empty_doc.docx", buf.getvalue())
        assert isinstance(result, str)

    def test_should_keep_table_cells(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("Before the table")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Name"
        table.cell(0, 1).text = "Role"
        table.cell(1, 0).add_paragraph("Ada")  # after the cell's empty first paragraph
        table.cell(1, 1).text = "Engineer\nLead"  # a line break inside the cell
        buf = BytesIO()
        doc.save(buf)

        result = extract_text_from_bytes("table.docx", buf.getvalue())
        assert result == "Before the table\n\nName | Role\nAda | Engineer Lead"

    def test_should_read_a_text_box_once_after_its_paragraph(self):
        # Word writes every text box twice: a DrawingML shape and a VML fallback copy.
        box = "<w:txbxContent><w:p>" + _run("Callout text") + "</w:p></w:txbxContent>"
        content = _docx_with_body(
            "<w:p>"
            + _run("Host paragraph")
            + "<w:r><mc:AlternateContent>"
            + '<mc:Choice Requires="wps">'
            + f"<w:drawing><wps:wsp><wps:txbx>{box}</wps:txbx></wps:wsp></w:drawing></mc:Choice>"
            + f"<mc:Fallback><w:pict><v:shape><v:textbox>{box}</v:textbox></v:shape></w:pict></mc:Fallback>"
            + "</mc:AlternateContent></w:r></w:p>"
        )

        result = extract_text_from_bytes("box.docx", content)
        assert result.endswith("Host paragraph\n\nCallout text")
        assert result.count("Callout text") == 1

    def test_should_read_a_text_box_inside_a_text_box_once(self):
        inner = "<w:r><w:pict><v:shape><v:textbox><w:txbxContent><w:p>" + _run("Inner box")
        inner += "</w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r>"
        outer = "<w:r><w:pict><v:shape><v:textbox><w:txbxContent><w:p>" + _run("Outer box") + inner
        outer += "</w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r>"

        result = extract_text_from_bytes("nested.docx", _docx_with_body("<w:p>" + _run("Host") + outer + "</w:p>"))
        assert result.endswith("Host\n\nOuter box\n\nInner box")
        assert result.count("Inner box") == 1

    def test_should_drop_a_text_box_inside_a_tracked_deletion_or_move(self):
        def box(text: str) -> str:
            shape = f"<w:txbxContent><w:p>{_run(text)}</w:p></w:txbxContent>"
            return f"<w:r><w:pict><v:shape><v:textbox>{shape}</v:textbox></v:shape></w:pict></w:r>"

        content = _docx_with_body(
            "<w:p>"
            + _run("Kept")
            + f'<w:del w:id="1" w:author="a">{box("Deleted box")}</w:del>'
            + f'<w:moveFrom w:id="2" w:author="a">{box("Moved-away box")}</w:moveFrom>'
            + "</w:p>"
        )

        assert extract_text_from_bytes("deleted-box.docx", content) == "Kept"

    def test_should_keep_tracked_insertions_and_drop_deletions(self):
        content = _docx_with_body(
            "<w:p>"
            + _run("The fee is ")
            + '<w:del w:id="1" w:author="a"><w:r><w:delText>ten</w:delText><w:tab/></w:r></w:del>'
            + f'<w:ins w:id="2" w:author="a">{_run("twelve")}</w:ins>'
            + '<w:moveFrom w:id="3" w:author="a"><w:r><w:t> moved away</w:t></w:r></w:moveFrom>'
            + _run(" euros.")
            + "</w:p>"
        )

        assert extract_text_from_bytes("tracked.docx", content).endswith("The fee is twelve euros.")

    def test_should_keep_content_controls_fields_and_smart_tags(self):
        content = _docx_with_body(
            "<w:p>"
            + _run("Client: ")
            + f"<w:sdt><w:sdtPr/><w:sdtContent>{_run('Acme Corp')}</w:sdtContent></w:sdt>"
            + "</w:p>",
            f"<w:sdt><w:sdtPr/><w:sdtContent><w:p>{_run('Block control')}</w:p></w:sdtContent></w:sdt>",
            f'<w:p><w:fldSimple w:instr=" DOCPROPERTY Company ">{_run("Field result")}</w:fldSimple></w:p>',
            f'<w:p><w:smartTag w:uri="urn:x" w:element="place">{_run("Smart tag")}</w:smartTag></w:p>',
            f'<w:customXml w:element="clause"><w:p>{_run("Custom XML")}</w:p></w:customXml>',
            "<w:tbl><w:tr><w:tc><w:p>"
            + _run("Row")
            + "</w:p></w:tc></w:tr><w:sdt><w:sdtContent><w:tr><w:tc><w:p>"
            + _run("Repeated row")
            + "</w:p></w:tc></w:tr></w:sdtContent></w:sdt></w:tbl>",
        )

        result = extract_text_from_bytes("controls.docx", content)
        assert result.endswith(
            "Client: Acme Corp\n\nBlock control\n\nField result\n\nSmart tag\n\nCustom XML\n\nRow\nRepeated row"
        )

    def test_should_read_one_branch_of_alternate_content(self):
        content = _docx_with_body(
            "<w:p><mc:AlternateContent>"
            f'<mc:Choice Requires="w14">{_run("Preferred")}</mc:Choice>'
            f"<mc:Fallback>{_run('Fallback')}</mc:Fallback>"
            "</mc:AlternateContent></w:p>"
        )

        assert extract_text_from_bytes("alternate.docx", content).endswith("Preferred")

    def test_should_read_ruby_base_text_without_its_guide(self):
        content = _docx_with_body(
            "<w:p><w:r><w:ruby><w:rubyPr/>"
            f"<w:rt>{_run('kanji')}</w:rt><w:rubyBase>{_run('漢字')}</w:rubyBase>"
            "</w:ruby></w:r></w:p>"
        )

        assert extract_text_from_bytes("ruby.docx", content) == "漢字"

    def test_should_extract_plain_paragraphs_exactly_as_before(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("First line\twith a tab")
        doc.add_paragraph("")
        doc.add_paragraph("Second").add_run().add_break()
        buf = BytesIO()
        doc.save(buf)

        expected = "\n\n".join(p.text for p in Document(BytesIO(buf.getvalue())).paragraphs)
        assert extract_text_from_bytes("plain.docx", buf.getvalue()) == expected


class TestExtractTextFromBytesPlainText:
    def test_should_decode_utf8_text(self):
        content = b"Hello plain text"
        result = extract_text_from_bytes("readme.txt", content)
        assert result == "Hello plain text"

    def test_should_handle_non_utf8_gracefully(self):
        content = b"\xff\xfe\x00\x01 some text"
        result = extract_text_from_bytes("binary.txt", content)
        assert isinstance(result, str)
        assert "some text" in result

    def test_should_handle_empty_content(self):
        result = extract_text_from_bytes("empty.txt", b"")
        assert result == ""

    def test_should_handle_csv_as_plain_text(self):
        content = b"col1,col2\nval1,val2"
        result = extract_text_from_bytes("data.csv", content)
        assert "col1,col2" in result

    def test_should_handle_json_as_plain_text(self):
        content = b'{"key": "value"}'
        result = extract_text_from_bytes("data.json", content)
        assert '"key"' in result

    def test_should_handle_unknown_extension_as_plain_text(self):
        content = b"some content"
        result = extract_text_from_bytes("file.xyz", content)
        assert result == "some content"

    def test_should_handle_file_without_extension(self):
        content = b"no extension"
        result = extract_text_from_bytes("Makefile", content)
        assert result == "no extension"

    def test_should_preserve_unicode_characters(self):
        content = "café résumé naïve".encode()
        result = extract_text_from_bytes("unicode.txt", content)
        assert result == "café résumé naïve"
