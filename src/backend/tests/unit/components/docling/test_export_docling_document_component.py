"""Tests for ExportDoclingDocumentComponent metadata preservation."""

import pytest

pytest.importorskip("docling_core")

from lfx.components.docling.export_docling_document import ExportDoclingDocumentComponent


class _FakeOrigin:
    """Minimal stand-in for DoclingDocument.origin."""

    def __init__(self, *, filename=None, binary_hash=None, mimetype=None):
        self.filename = filename
        self.binary_hash = binary_hash
        self.mimetype = mimetype


class _FakeDoclingDocument:
    """Minimal stand-in for DoclingDocument with configurable metadata."""

    def __init__(self, *, name=None, origin=None, markdown_text="# Hello"):
        self.name = name
        self.origin = origin
        self._markdown_text = markdown_text

    def export_to_markdown(self, **_kwargs):
        return self._markdown_text

    def export_to_text(self, **_kwargs):
        return self._markdown_text

    def export_to_html(self, **_kwargs):
        return f"<p>{self._markdown_text}</p>"

    def export_to_doctags(self, **_kwargs):
        return f"<doc>{self._markdown_text}</doc>"


class TestExportDoclingDocumentMetadata:
    """Verify that export_document preserves DoclingDocument metadata."""

    def _run_export(self, monkeypatch, fake_doc, export_format="Markdown"):
        """Helper: run export_document with a mocked extract_docling_documents."""
        monkeypatch.setattr(
            "lfx.components.docling.export_docling_document.extract_docling_documents",
            lambda *_args, **_kwargs: ([fake_doc], None),
        )

        component = ExportDoclingDocumentComponent()
        component._attributes = {
            "data_inputs": None,
            "export_format": export_format,
            "image_mode": "placeholder",
            "md_image_placeholder": "<!-- image -->",
            "md_page_break_placeholder": "",
            "doc_key": "doc",
        }
        return component.export_document()

    def test_metadata_preserved_with_full_origin(self, monkeypatch):
        fake_doc = _FakeDoclingDocument(
            name="report.pdf",
            origin=_FakeOrigin(
                filename="report.pdf",
                binary_hash="abc123hash",
                mimetype="application/pdf",
            ),
            markdown_text="# Report",
        )

        results = self._run_export(monkeypatch, fake_doc)

        assert len(results) == 1
        data = results[0]
        assert data.get_text() == "# Report"
        assert data.data["export_format"] == "Markdown"
        assert data.data["name"] == "report.pdf"
        assert data.data["filename"] == "report.pdf"
        assert data.data["document_id"] == "abc123hash"
        assert data.data["mimetype"] == "application/pdf"

    def test_metadata_preserved_without_origin(self, monkeypatch):
        """When origin is None, metadata should still include export_format and name."""
        fake_doc = _FakeDoclingDocument(name="notes.md", origin=None, markdown_text="hello")

        results = self._run_export(monkeypatch, fake_doc)

        assert len(results) == 1
        data = results[0]
        assert data.data["export_format"] == "Markdown"
        assert data.data["name"] == "notes.md"
        assert "filename" not in data.data
        assert "document_id" not in data.data

    def test_metadata_preserved_with_partial_origin(self, monkeypatch):
        """When origin has only some fields, only those should appear."""
        fake_doc = _FakeDoclingDocument(
            name="scan.png",
            origin=_FakeOrigin(filename="scan.png", binary_hash=None, mimetype=None),
            markdown_text="image text",
        )

        results = self._run_export(monkeypatch, fake_doc)

        assert len(results) == 1
        data = results[0]
        assert data.data["filename"] == "scan.png"
        assert "document_id" not in data.data
        assert "mimetype" not in data.data

    def test_metadata_preserved_for_plaintext_export(self, monkeypatch):
        fake_doc = _FakeDoclingDocument(
            name="doc.pdf",
            origin=_FakeOrigin(filename="doc.pdf", binary_hash="xyz", mimetype="application/pdf"),
            markdown_text="plain content",
        )

        results = self._run_export(monkeypatch, fake_doc, export_format="Plaintext")

        assert len(results) == 1
        data = results[0]
        assert data.data["export_format"] == "Plaintext"
        assert data.data["document_id"] == "xyz"

    def test_no_metadata_when_doc_has_no_name_or_origin(self, monkeypatch):
        """Minimal doc with no name or origin should still export with export_format."""
        fake_doc = _FakeDoclingDocument(name=None, origin=None, markdown_text="bare")

        results = self._run_export(monkeypatch, fake_doc)

        assert len(results) == 1
        data = results[0]
        assert data.data["export_format"] == "Markdown"
        assert "name" not in data.data
        assert "filename" not in data.data
        assert "document_id" not in data.data
        assert "mimetype" not in data.data
