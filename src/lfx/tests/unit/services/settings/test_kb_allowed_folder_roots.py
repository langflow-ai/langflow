"""Tests for the ``kb_allowed_folder_roots`` setting.

The folder-ingestion route (``POST /{kb_name}/ingest/folder``) gates which
server-side directories it may read via ``settings.kb_allowed_folder_roots``.
Before this field was declared on the model, the attribute did not exist:
reading it raised ``AttributeError`` (re-raised by the route as a generic
HTTP 500), and ``LANGFLOW_KB_ALLOWED_FOLDER_ROOTS`` bound to nothing because
``model_config`` uses ``extra="ignore"`` — so the allow-list could never be
configured and the endpoint was unusable.

These tests exercise the *real* Settings model (the endpoint unit tests inject
a mocked settings object, so they never caught the missing field).
"""

from lfx.services.settings.base import Settings


def test_kb_allowed_folder_roots_field_is_declared(monkeypatch):
    """The field must exist on the model — guards against the 1.10.0 regression."""
    monkeypatch.delenv("LANGFLOW_KB_ALLOWED_FOLDER_ROOTS", raising=False)
    settings = Settings()
    # Accessing the attribute must not raise AttributeError.
    assert hasattr(settings, "kb_allowed_folder_roots")


def test_kb_allowed_folder_roots_defaults_to_empty_list(monkeypatch):
    """With no env var configured the allow-list is empty (operators opt in)."""
    monkeypatch.delenv("LANGFLOW_KB_ALLOWED_FOLDER_ROOTS", raising=False)
    settings = Settings()
    assert settings.kb_allowed_folder_roots == []


def test_kb_allowed_folder_roots_binds_single_value_from_env(monkeypatch):
    """A single directory binds from the LANGFLOW_-prefixed env var."""
    monkeypatch.setenv("LANGFLOW_KB_ALLOWED_FOLDER_ROOTS", "/srv/docs")
    settings = Settings()
    assert settings.kb_allowed_folder_roots == ["/srv/docs"]


def test_kb_allowed_folder_roots_parses_comma_separated_env(monkeypatch):
    """Multiple roots are comma-separated, like the other list settings."""
    monkeypatch.setenv("LANGFLOW_KB_ALLOWED_FOLDER_ROOTS", "/srv/docs,/data/shared")
    settings = Settings()
    assert settings.kb_allowed_folder_roots == ["/srv/docs", "/data/shared"]
