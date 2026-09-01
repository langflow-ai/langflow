"""Policy denials must not name operator-only settings in the message they raise.

Reproduced from alpha customer feedback: a non-admin evaluator who had
uploaded no file was shown

    Access to local file paths outside the authenticated user's storage scope is
    disabled (LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true). Use an uploaded file...

They cannot read that setting, cannot change it, and have no documentation to look
it up in. It also arrived truncated at 150 chars by the assistant's error handling,
cutting off the one remediation the message carried.

The setting name belongs in the server log, which is where the operator who *can*
change it looks. These tests pin that split at the raise site, so it holds for every
consumer of these errors rather than only for the one that happened to sanitize.
"""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.file_path_security import (
    LocalFileAccessError,
    enforce_local_file_access,
    package_resource_root,
)
from lfx.utils.ssrf_protection import SSRFProtectionError, validate_database_url_for_ssrf

SCOPE = str(uuid.uuid4())


@pytest.fixture
def restricted(tmp_path):
    settings = MagicMock()
    settings.settings.restrict_local_file_access = True
    settings.settings.config_dir = str(tmp_path)
    with patch("lfx.utils.file_path_security.get_settings_service", return_value=settings):
        (tmp_path / SCOPE).mkdir(parents=True, exist_ok=True)
        yield tmp_path


@pytest.mark.usefixtures("restricted")
class TestLocalFileDenials:
    def test_outside_scope_denial_names_no_setting(self):
        with pytest.raises(LocalFileAccessError) as exc:
            enforce_local_file_access("/etc/passwd", scope_ids=(SCOPE,))
        assert "LANGFLOW_" not in str(exc.value)

    def test_outside_scope_denial_keeps_its_remediation(self):
        with pytest.raises(LocalFileAccessError) as exc:
            enforce_local_file_access("/etc/passwd", scope_ids=(SCOPE,))
        message = str(exc.value)
        assert "Use an uploaded file" in message
        assert "administrator" in message

    def test_missing_scope_denial_names_no_setting(self):
        with pytest.raises(LocalFileAccessError) as exc:
            enforce_local_file_access("/etc/passwd", scope_ids=())
        assert "LANGFLOW_" not in str(exc.value)

    def test_reserved_file_denial_names_no_setting(self, restricted):
        secret = Path(restricted) / "secret_key"
        secret.write_text("x", encoding="utf-8")
        with pytest.raises(LocalFileAccessError) as exc:
            enforce_local_file_access(str(secret), scope_ids=(SCOPE,), allow_storage_root=True)
        assert "LANGFLOW_" not in str(exc.value)

    def test_denial_stays_short_enough_to_survive_downstream_truncation(self):
        """The assistant truncates at 150 chars, which used to eat the remediation."""
        with pytest.raises(LocalFileAccessError) as exc:
            enforce_local_file_access("/etc/passwd", scope_ids=(SCOPE,))
        assert len(str(exc.value)) <= 150

    def test_operator_still_gets_the_setting_name_in_the_log(self):
        with patch("lfx.utils.file_path_security.logger") as log, pytest.raises(LocalFileAccessError):
            enforce_local_file_access("/etc/passwd", scope_ids=(SCOPE,))
        logged = " ".join(str(call) for call in log.warning.call_args_list)
        assert "LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS" in logged


class TestDatabaseDialectDenial:
    def test_dialect_denial_names_no_setting_but_keeps_remediation(self):
        # file_restricted comes from is_local_file_access_restricted(), which reads the
        # settings service through file_path_security -- patch it there.
        settings = MagicMock()
        settings.settings.restrict_local_file_access = True
        with (
            patch("lfx.utils.file_path_security.get_settings_service", return_value=settings),
            pytest.raises(SSRFProtectionError) as exc,
        ):
            validate_database_url_for_ssrf("sqlite:////tmp/x.db")
        message = str(exc.value)
        assert "LANGFLOW_" not in message
        # Its own remediation, not a canned one -- uploading a file does not fix this.
        assert "network database" in message


@pytest.mark.usefixtures("restricted")
class TestPackagedFlowPackageExemption:
    """The package read exemption must not become a write channel.

    A write into the installed component library is code execution on the next component
    discovery, so every caller that gates a *write destination* must declare ``for_write``.
    ``allow_package_read`` defaults to False and is derived per component from its own graph
    (``component_may_read_package_resources``), so nothing is exempt by ambient state.
    """

    def test_read_is_allowed_for_a_packaged_graph(self):
        enforce_local_file_access(str(package_resource_root()), scope_ids=(SCOPE,), allow_package_read=True)

    def test_write_is_refused_even_for_a_packaged_graph(self):
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(
                str(package_resource_root()), scope_ids=(SCOPE,), allow_package_read=True, for_write=True
            )

    def test_read_is_refused_without_the_packaged_graph(self):
        """Default is closed: the exemption is opt-in per component, from its own graph."""
        with pytest.raises(LocalFileAccessError):
            enforce_local_file_access(str(package_resource_root()), scope_ids=(SCOPE,))

    def test_exemption_is_the_component_library_not_the_whole_package(self):
        """A narrower root is a smaller blast radius if the write guard is ever missed."""
        import lfx

        assert package_resource_root() == (Path(lfx.__file__).parent / "components").resolve()

    @pytest.mark.parametrize(
        ("module", "call"),
        [
            ("lfx_bundles/chroma/chroma.py", "self.resolve_path(self.persist_directory), for_write=True"),
            ("lfx_bundles/chroma/local_db.py", "self.collection_name, for_write=True"),
            ("lfx_bundles/faiss/faiss.py", "self.resolve_path(self.persist_directory), for_write=True"),
        ],
    )
    def test_vector_store_write_destinations_declare_for_write(self, module, call):
        """Each of these persists tenant data to a tenant-controlled directory."""
        source = Path(__file__).parents[4] / "bundles" / "lfx-bundles" / "src" / module
        assert call in source.read_text(encoding="utf-8")
