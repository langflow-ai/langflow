"""OpenSSL trust settings remain private to selected source connections."""

import os
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest
from langflow.upgrade_check.isolation import child_environment, resolve_input_paths, source_connection_context


def test_capture_keeps_openssl_trust_only_for_source_connections(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SSL_CERT_FILE", "roots.pem")
    monkeypatch.setenv("SSL_CERT_DIR", "trust")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-provider-key")
    options = {
        "database_url": "postgresql://127.0.0.1:15476/fixture?sslrootcert=system",
        "settings": {"components_path": []},
    }
    selected = resolve_input_paths(options)
    assert selected["database_url"].endswith("sslrootcert=system")
    private = selected["_source_connection"]["environment"]
    assert private["SSL_CERT_FILE"] == "roots.pem"
    assert private["SSL_CERT_DIR"] == "trust"
    assert "OPENAI_API_KEY" not in private
    runtime = child_environment(str(tmp_path / "isolated"), os.environ)
    assert "SSL_CERT_FILE" not in runtime
    assert "SSL_CERT_DIR" not in runtime


@pytest.mark.parametrize("fail", [False, True])
def test_relative_trust_paths_and_cleanup_stay_in_the_source_phase(monkeypatch, tmp_path, fail):
    source, isolated = tmp_path / "source", tmp_path / "isolated"
    source.mkdir()
    isolated.mkdir()
    trust = source / "roots.pem"
    trust.write_bytes(b"synthetic trust-root fixture")
    (source / "trust").mkdir()
    monkeypatch.chdir(isolated)
    inputs = {
        "working_directory": str(source),
        "environment": {"HOME": str(source), "SSL_CERT_FILE": "roots.pem", "SSL_CERT_DIR": "trust"},
    }
    with patch.dict(os.environ, child_environment(str(isolated), os.environ), clear=True):
        previous = dict(os.environ)
        expected = pytest.raises(RuntimeError, match="synthetic source refusal") if fail else nullcontext()
        with expected, source_connection_context(inputs):
            assert Path.cwd() == source
            assert Path(os.environ["SSL_CERT_FILE"]).read_bytes() == b"synthetic trust-root fixture"
            assert Path(os.environ["SSL_CERT_DIR"]).is_dir()
            if fail:
                message = "synthetic source refusal"
                raise RuntimeError(message)
        assert dict(os.environ) == previous
        assert Path.cwd() == isolated
    assert trust.read_bytes() == b"synthetic trust-root fixture"
