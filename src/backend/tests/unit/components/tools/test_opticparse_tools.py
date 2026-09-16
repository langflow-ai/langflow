from unittest.mock import MagicMock, patch

import pytest
from lfx.components.tools.opticparse_tool import (
    OpticParseToolComponent,
    normalize_target_url,
    resolve_portal_url,
)
from lfx.components.tools.phishvision_tool import PhishVisionToolComponent


def test_url_normalization():
    """Verify URL normalization handles bare domains and enforces schemes."""
    assert normalize_target_url("example.com") == "https://example.com"
    assert normalize_target_url("http://test.org/path") == "http://test.org/path"
    assert normalize_target_url("https://secure.site") == "https://secure.site"

    with pytest.raises(ValueError, match="Target URL or domain cannot be empty"):
        normalize_target_url("")

    with pytest.raises(ValueError, match="Invalid or unsupported URL scheme"):
        normalize_target_url("ftp://invalid.scheme")


def test_https_enforcement_with_api_key():
    """Verify custom HTTP portal URLs are rejected when API keys are configured."""
    with pytest.raises(ValueError, match="Insecure HTTP portal URL is not allowed"):
        resolve_portal_url("http://insecure-portal.com", "test_api_key")

    # Allowed when no API key is set
    assert resolve_portal_url("http://localhost:8000", "") == "http://localhost:8000"


def test_opticparse_component_attributes_and_tool_build():
    """Verify OpticParse component schema, attributes, and tool builder."""
    component = OpticParseToolComponent()
    assert component.name == "OpticParseTool"
    assert component.display_name == "OpticParse Web Scraper"
    assert len(component.inputs) == 4

    tool = component.build_tool()
    assert tool.name == "opticparse_scrape"


def test_opticparse_scrape_success_mock():
    """Verify OpticParse mock execution and response parsing."""
    component = OpticParseToolComponent()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"content": "# Extracted Markdown Title\nBody text."}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = component._scrape_webpage("news.ycombinator.com", "get titles")
        assert "# Extracted Markdown Title" in result
        mock_post.assert_called_once()
        assert mock_post.call_args[1]["allow_redirects"] is False


def test_phishvision_component_attributes_and_tool_build():
    """Verify PhishVision component schema, attributes, and tool builder."""
    component = PhishVisionToolComponent()
    assert component.name == "PhishVisionTool"
    assert component.display_name == "PhishVision Threat Scanner"
    assert len(component.inputs) == 3

    tool = component.build_tool()
    assert tool.name == "phishvision_scan"


def test_phishvision_scan_redirect_abort():
    """Verify PhishVision aborts on redirect to protect credential privacy."""
    component = PhishVisionToolComponent()
    mock_resp = MagicMock()
    mock_resp.status_code = 302

    with patch("requests.post", return_value=mock_resp):
        result = component._scan_threat("phishing-attempt.xyz")
        assert "unexpected redirect" in result.lower()


def test_phishvision_scan_success_mock():
    """Verify PhishVision successfully executes scan against /api/phish-detect."""
    component = PhishVisionToolComponent()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"verdict": "safe", "threat_score": 5}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = component._scan_threat("https://example.com")
        assert '"verdict": "safe"' in result
        mock_post.assert_called_once()
        assert "/api/phish-detect" in mock_post.call_args[0][0]
