from __future__ import annotations

import httpx
import pytest
from lfx.base.data.base_file import BaseFileComponent
from lfx.components.baidu.paddleocr import PaddleOCRComponent
from lfx.schema.data import Data


def make_base_file(path):
    return BaseFileComponent.BaseFile(Data(data={"file_path": str(path)}), path)


def test_paddleocr_ocr_mode_processes_text(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.png"
    file_path.write_bytes(b"fake image")

    captured = {}

    def fake_submit(_self, *, base_url, headers, file_path, options):
        captured["submit"] = {
            "base_url": base_url,
            "headers": headers,
            "file_path": file_path,
            "options": options,
        }
        return "ocr-job-id"

    def fake_poll(_self, *, base_url, headers, job_id, poll_timeout):
        captured["poll"] = {
            "base_url": base_url,
            "headers": headers,
            "job_id": job_id,
            "poll_timeout": poll_timeout,
        }
        return [
            {
                "result": {
                    "ocrResults": [
                        {
                            "prunedResult": {"rec_texts": ["hello", "world"]},
                            "ocrImage": "https://example.com/ocr.png",
                        }
                    ]
                }
            }
        ]

    monkeypatch.setattr(PaddleOCRComponent, "_submit_job", fake_submit)
    monkeypatch.setattr(PaddleOCRComponent, "_poll_job", fake_poll)

    component = PaddleOCRComponent()
    component.set_attributes(
        {
            "access_token": "token",
            "base_url": "",
            "task_type": "ocr",
            "model": "PP-OCRv6",
            "poll_timeout": 123,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
    )

    processed = component.process_files([make_base_file(file_path)])

    data = processed[0].data[0].data
    assert data["text"] == "hello\nworld"
    assert data["task_type"] == "ocr"
    assert data["output_format"] == "plain_text"
    assert data["model"] == "PP-OCRv6"
    assert data["job_id"] == "ocr-job-id"
    assert data["pages"][0]["pruned_result"] == {"rec_texts": ["hello", "world"]}

    assert captured["submit"]["base_url"] == PaddleOCRComponent.DEFAULT_BASE_URL
    assert captured["submit"]["headers"] == {
        "Authorization": "Bearer token",
        "Client-Platform": "langflow",
    }
    assert captured["submit"]["file_path"] == file_path
    assert captured["submit"]["options"]["use_doc_orientation_classify"] is False
    assert captured["poll"]["poll_timeout"] == 123


def test_paddleocr_document_parsing_processes_markdown(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"fake pdf")

    captured = {}

    def fake_submit(_self, *, base_url, headers, file_path, options):
        captured["submit"] = {"base_url": base_url, "headers": headers, "file_path": file_path, "options": options}
        return "doc-job-id"

    def fake_poll(_self, **_kwargs):
        return [
            {
                "result": {
                    "layoutParsingResults": [
                        {
                            "markdown": {
                                "text": "# Title",
                                "images": {"image.png": "https://example.com/image.png"},
                            },
                            "outputImages": {},
                        }
                    ]
                }
            }
        ]

    monkeypatch.setattr(PaddleOCRComponent, "_submit_job", fake_submit)
    monkeypatch.setattr(PaddleOCRComponent, "_poll_job", fake_poll)

    component = PaddleOCRComponent()
    component.set_attributes(
        {
            "access_token": "token",
            "base_url": "https://example.com/",
            "task_type": "document_parsing",
            "model": "PaddleOCR-VL-1.6",
            "poll_timeout": 600,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_table_recognition": True,
            "use_formula_recognition": False,
            "use_chart_recognition": False,
            "use_seal_recognition": False,
            "prettify_markdown": True,
            "visualize": False,
        }
    )

    processed = component.process_files([make_base_file(file_path)])

    data = processed[0].data[0].data
    assert data["text"] == "# Title"
    assert data["task_type"] == "document_parsing"
    assert data["output_format"] == "markdown"
    assert data["model"] == "PaddleOCR-VL-1.6"
    assert data["job_id"] == "doc-job-id"
    assert data["pages"][0]["markdown_text"] == "# Title"
    assert data["pages"][0]["markdown_images"] == {"image.png": "https://example.com/image.png"}

    assert captured["submit"]["base_url"] == "https://example.com"
    assert captured["submit"]["file_path"] == file_path
    assert captured["submit"]["options"]["use_table_recognition"] is True


def test_paddleocr_document_parsing_falls_back_to_ocr_results(tmp_path):
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"fake pdf")

    component = PaddleOCRComponent()
    component.set_attributes({"task_type": "document_parsing", "model": "PP-OCRv6"})

    data = component._document_result_to_data(
        "job-id",
        [
            {
                "result": {
                    "ocrResults": [
                        {
                            "prunedResult": {"rec_texts": ["fallback", "text"]},
                            "ocrImage": "https://example.com/ocr.png",
                        }
                    ]
                }
            }
        ],
        file_path,
    ).data

    assert data["text"] == "fallback\ntext"
    assert data["pages"][0]["pruned_result"] == {"rec_texts": ["fallback", "text"]}


def test_paddleocr_requires_access_token(tmp_path):
    file_path = tmp_path / "sample.png"
    file_path.write_bytes(b"fake image")

    component = PaddleOCRComponent()
    component.set_attributes({"access_token": "", "task_type": "ocr", "model": "PP-OCRv6"})

    with pytest.raises(ValueError, match="Access Token is required"):
        component.process_files([make_base_file(file_path)])


def test_paddleocr_formats_auth_error():
    component = PaddleOCRComponent()
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(401, request=request, text="unauthorized")
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)

    assert component._format_paddleocr_error(error) == (
        "PaddleOCR authentication failed. Please check the AI Studio Access Token."
    )


def test_task_type_updates_model_options():
    component = PaddleOCRComponent()
    build_config = {
        "model": {"options": ["PP-StructureV3", "PaddleOCR-VL-1.6"], "value": "PP-StructureV3"},
    }

    updated = component.update_build_config(build_config, "ocr", "task_type")
    assert updated["model"]["options"] == ["PP-OCRv6", "PP-OCRv5"]
    assert updated["model"]["value"] == "PP-OCRv6"

    updated = component.update_build_config(build_config, "document_parsing", "task_type")
    assert updated["model"]["options"] == ["PP-StructureV3", "PaddleOCR-VL-1.6"]
    assert updated["model"]["value"] == "PP-StructureV3"
