from unittest.mock import Mock, patch

import httpx
import pytest
from langflow.utils.version import (
    _compute_non_prerelease_version,
    _get_version_info,
    fetch_latest_version,
    get_version_info,
    is_nightly,
    is_pre_release,
)


class TestComputeNonPrereleaseVersion:
    """Test cases for _compute_non_prerelease_version function."""

    def test_compute_alpha_version(self):
        """Test computing non-prerelease version from alpha version."""
        version = "1.2.3.a1"
        result = _compute_non_prerelease_version(version)
        assert result == "1.2.3"

    def test_compute_beta_version(self):
        """Test computing non-prerelease version from beta version."""
        version = "2.0.0.b2"
        result = _compute_non_prerelease_version(version)
        assert result == "2.0.0"

    def test_compute_rc_version(self):
        """Test computing non-prerelease version from release candidate version."""
        version = "1.5.0.rc1"
        result = _compute_non_prerelease_version(version)
        assert result == "1.5.0"

    def test_compute_dev_version(self):
        """Test computing non-prerelease version from dev version."""
        version = "1.0.0.dev123"
        result = _compute_non_prerelease_version(version)
        assert result == "1.0.0"

    def test_compute_post_version(self):
        """Test computing non-prerelease version from post version."""
        version = "1.1.0.post1"
        result = _compute_non_prerelease_version(version)
        assert result == "1.1.0"

    def test_compute_stable_version(self):
        """Test computing non-prerelease version from stable version."""
        version = "1.0.0"
        result = _compute_non_prerelease_version(version)
        assert result == "1.0.0"

    def test_compute_version_with_multiple_keywords(self):
        """Test computing version with multiple prerelease keywords (first match)."""
        version = "1.0.0.a1.dev"
        result = _compute_non_prerelease_version(version)
        assert result == "1.0.0"

    def test_compute_version_no_dot_before_keyword(self):
        """Test computing version without dot before keyword."""
        version = "1.0.0a1"
        result = _compute_non_prerelease_version(version)
        assert result == "1.0."

    def test_compute_version_complex_format(self):
        """Test computing version with complex format."""
        version = "2.1.0.rc2.post1"
        result = _compute_non_prerelease_version(version)
        assert result == "2.1.0"


class TestGetVersionInfo:
    """Test cases for _get_version_info function."""

    @patch("langflow.utils.version.metadata")
    def test_get_version_info_langflow_package(self, mock_metadata):
        """Test getting version info for langflow package."""
        mock_metadata.version.return_value = "1.0.0"

        result = _get_version_info()

        assert result["version"] == "1.0.0"
        assert result["main_version"] == "1.0.0"
        assert result["package"] == "Langflow"

    @patch("langflow.utils.version.metadata")
    def test_get_version_info_langflow_base_package(self, mock_metadata):
        """Test getting version info for langflow-base package."""
        from importlib import metadata as real_metadata

        mock_metadata.PackageNotFoundError = real_metadata.PackageNotFoundError

        def mock_version(pkg_name):
            if pkg_name == "langflow":
                raise mock_metadata.PackageNotFoundError
            if pkg_name == "langflow-base":
                return "1.0.0.dev123"
            raise mock_metadata.PackageNotFoundError

        mock_metadata.version.side_effect = mock_version

        result = _get_version_info()

        assert result["version"] == "1.0.0.dev123"
        assert result["main_version"] == "1.0.0"
        assert result["package"] == "Langflow Base"

    @patch("langflow.utils.version.metadata")
    def test_get_version_info_nightly_package(self, mock_metadata):
        """Test getting version info for nightly package."""
        from importlib import metadata as real_metadata

        mock_metadata.PackageNotFoundError = real_metadata.PackageNotFoundError

        def mock_version(pkg_name):
            if pkg_name in ["langflow", "langflow-base"]:
                raise mock_metadata.PackageNotFoundError
            if pkg_name == "langflow-nightly":
                return "1.0.0.dev456"
            raise mock_metadata.PackageNotFoundError

        mock_metadata.version.side_effect = mock_version

        result = _get_version_info()

        assert result["version"] == "1.0.0.dev456"
        assert result["main_version"] == "1.0.0"
        assert result["package"] == "Langflow Nightly"

    @patch("langflow.utils.version.metadata")
    def test_get_version_info_base_nightly_package(self, mock_metadata):
        """Test getting version info for base nightly package."""
        from importlib import metadata as real_metadata

        mock_metadata.PackageNotFoundError = real_metadata.PackageNotFoundError

        def mock_version(pkg_name):
            if pkg_name in ["langflow", "langflow-base", "langflow-nightly"]:
                raise mock_metadata.PackageNotFoundError
            if pkg_name == "langflow-base-nightly":
                return "1.0.0.a1"
            raise mock_metadata.PackageNotFoundError

        mock_metadata.version.side_effect = mock_version

        result = _get_version_info()

        assert result["version"] == "1.0.0.a1"
        assert result["main_version"] == "1.0.0"
        assert result["package"] == "Langflow Base Nightly"

    @patch("langflow.utils.version.metadata")
    def test_get_version_info_no_package_found(self, mock_metadata):
        """Test getting version info when no package is found."""
        from importlib import metadata as real_metadata

        mock_metadata.PackageNotFoundError = real_metadata.PackageNotFoundError
        mock_metadata.version.side_effect = mock_metadata.PackageNotFoundError()

        with pytest.raises(ValueError, match="Package not found from options"):
            _get_version_info()

    @patch("langflow.utils.version.metadata")
    def test_get_version_info_import_error(self, mock_metadata):
        """Test getting version info when ImportError occurs."""
        from importlib import metadata as real_metadata

        mock_metadata.PackageNotFoundError = real_metadata.PackageNotFoundError
        mock_metadata.version.side_effect = ImportError()

        with pytest.raises(ValueError, match="Package not found from options"):
            _get_version_info()


class TestIsPreRelease:
    """Test cases for is_pre_release function."""

    def test_is_pre_release_alpha(self):
        """Test alpha versions are pre-release."""
        assert is_pre_release("1.0.0a1") is True
        assert is_pre_release("1.0.0.a1") is True

    def test_is_pre_release_beta(self):
        """Test beta versions are pre-release."""
        assert is_pre_release("1.0.0b1") is True
        assert is_pre_release("1.0.0.b1") is True

    def test_is_pre_release_rc(self):
        """Test release candidate versions are pre-release."""
        assert is_pre_release("1.0.0rc1") is True
        assert is_pre_release("1.0.0.rc1") is True

    def test_is_not_pre_release_stable(self):
        """Test stable versions are not pre-release."""
        assert is_pre_release("1.0.0") is False

    def test_is_not_pre_release_dev(self):
        """Test dev versions are not considered pre-release."""
        assert is_pre_release("1.0.0.dev123") is False

    def test_is_not_pre_release_post(self):
        """Test post versions are not considered pre-release."""
        assert is_pre_release("1.0.0.post1") is False

    def test_is_pre_release_mixed_version(self):
        """Test mixed versions with pre-release markers."""
        assert is_pre_release("1.0.0a1.dev123") is True
        assert is_pre_release("1.0.0.rc1.post1") is True


class TestIsNightly:
    """Test cases for is_nightly function."""

    def test_is_nightly_dev_version(self):
        """Test dev versions are nightly."""
        assert is_nightly("1.0.0.dev123") is True
        assert is_nightly("1.0.0dev456") is True

    def test_is_not_nightly_stable(self):
        """Test stable versions are not nightly."""
        assert is_nightly("1.0.0") is False

    def test_is_not_nightly_alpha(self):
        """Test alpha versions are not nightly."""
        assert is_nightly("1.0.0a1") is False

    def test_is_not_nightly_beta(self):
        """Test beta versions are not nightly."""
        assert is_nightly("1.0.0b1") is False

    def test_is_not_nightly_rc(self):
        """Test release candidate versions are not nightly."""
        assert is_nightly("1.0.0rc1") is False

    def test_is_nightly_mixed_version(self):
        """Test mixed versions with dev marker."""
        assert is_nightly("1.0.0a1.dev123") is True


class TestFetchLatestVersion:
    """Test cases for fetch_latest_version function."""

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_success(self, mock_httpx):
        """Test successful fetching of latest version."""
        mock_response = Mock()
        mock_response.json.return_value = {"releases": {"1.0.0": [], "1.1.0": [], "1.2.0": [], "2.0.0a1": []}}
        mock_httpx.get.return_value = mock_response

        result = fetch_latest_version("test-package", include_prerelease=False)

        assert result == "1.2.0"
        mock_httpx.get.assert_called_once_with("https://pypi.org/pypi/test-package/json")

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_with_prerelease(self, mock_httpx):
        """Test fetching latest version including prerelease."""
        mock_response = Mock()
        mock_response.json.return_value = {"releases": {"1.0.0": [], "1.1.0": [], "2.0.0a1": [], "2.0.0b1": []}}
        mock_httpx.get.return_value = mock_response

        result = fetch_latest_version("test-package", include_prerelease=True)

        assert result == "2.0.0b1"

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_no_stable_versions(self, mock_httpx):
        """Test fetching when no stable versions exist."""
        mock_response = Mock()
        mock_response.json.return_value = {"releases": {"1.0.0a1": [], "1.0.0b1": [], "1.0.0rc1": []}}
        mock_httpx.get.return_value = mock_response

        result = fetch_latest_version("test-package", include_prerelease=False)

        assert result is None

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_package_name_normalization(self, mock_httpx):
        """Test package name normalization."""
        mock_response = Mock()
        mock_response.json.return_value = {"releases": {"1.0.0": []}}
        mock_httpx.get.return_value = mock_response

        fetch_latest_version("Test Package Name", include_prerelease=False)

        mock_httpx.get.assert_called_once_with("https://pypi.org/pypi/test-package-name/json")

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_http_error(self, mock_httpx):
        """Test handling HTTP errors."""
        mock_httpx.get.side_effect = httpx.HTTPError("Network error")

        result = fetch_latest_version("test-package", include_prerelease=False)

        assert result is None

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_json_error(self, mock_httpx):
        """Test handling JSON parsing errors."""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_httpx.get.return_value = mock_response

        result = fetch_latest_version("test-package", include_prerelease=False)

        assert result is None

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_empty_releases(self, mock_httpx):
        """Test handling empty releases."""
        mock_response = Mock()
        mock_response.json.return_value = {"releases": {}}
        mock_httpx.get.return_value = mock_response

        result = fetch_latest_version("test-package", include_prerelease=False)

        assert result is None

    @patch("langflow.utils.version.httpx")
    def test_fetch_latest_version_complex_versions(self, mock_httpx):
        """Test fetching with complex version numbers."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "releases": {"1.0.0": [], "1.0.1": [], "1.0.10": [], "1.0.2": [], "1.1.0": [], "2.0.0": []}
        }
        mock_httpx.get.return_value = mock_response

        result = fetch_latest_version("test-package", include_prerelease=False)

        # Should correctly parse and find the highest version
        assert result == "2.0.0"


class TestGetVersionInfoFunction:
    """Test cases for get_version_info function."""

    @patch("langflow.utils.version.VERSION_INFO")
    def test_get_version_info_returns_version_info(self, mock_version_info):
        """Test that get_version_info returns VERSION_INFO."""
        mock_version_info = {"version": "1.0.0", "main_version": "1.0.0", "package": "Langflow"}

        with patch("langflow.utils.version.VERSION_INFO", mock_version_info):
            result = get_version_info()

            assert result == mock_version_info
