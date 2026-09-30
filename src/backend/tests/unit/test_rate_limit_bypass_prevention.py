"""Tests for rate limit bypass prevention via X-Forwarded-For spoofing."""

import pytest


@pytest.mark.parametrize(
    ("trust_proxy", "expected"),
    [
        (False, ""),
        (True, "*"),
    ],
)
def test_direct_uvicorn_forwarded_allow_ips(trust_proxy, expected):
    """build_direct_uvicorn_kwargs must set forwarded_allow_ips to control uvicorn's ProxyHeadersMiddleware.

    Empty string = trust nobody; "*" = trust all.
    """
    from langflow.__main__ import build_direct_uvicorn_kwargs

    kwargs = build_direct_uvicorn_kwargs(
        host="localhost",
        port=7860,
        log_level="info",
        workers=1,
        loop="asyncio",
        ssl_cert_file_path=None,
        ssl_key_file_path=None,
        trust_proxy=trust_proxy,
    )

    assert kwargs["forwarded_allow_ips"] == expected


@pytest.mark.parametrize(
    ("trust_proxy", "expected"),
    [
        (False, ""),
        (True, "*"),
    ],
)
def test_gunicorn_worker_forwarded_allow_ips(trust_proxy, expected):
    """LangflowUvicornWorker.init_process must update BOTH self.cfg and self.config.

    UvicornWorker.__init__ snapshots cfg.forwarded_allow_ips into self.config before
    init_process runs.  Only patching cfg is insufficient — ProxyHeadersMiddleware
    reads self.config.forwarded_allow_ips when the server starts serving.
    """
    from unittest.mock import MagicMock, patch

    from langflow.server import LangflowUvicornWorker

    mock_settings = MagicMock()
    mock_settings.rate_limit_trust_proxy = trust_proxy
    mock_service = MagicMock()
    mock_service.settings = mock_settings

    # Bypass __init__ so we don't need a real gunicorn environment.
    worker = object.__new__(LangflowUvicornWorker)
    worker.cfg = MagicMock()
    worker.config = MagicMock()  # uvicorn Config, already snapshotted by __init__

    with (
        patch("langflow.services.deps.get_settings_service", return_value=mock_service),
        patch("uvicorn.workers.UvicornWorker.init_process", return_value=None),
    ):
        worker.init_process()

    worker.cfg.set.assert_called_once_with("forwarded_allow_ips", expected)
    assert worker.config.forwarded_allow_ips == expected


def test_default_trust_proxy_is_false():
    """rate_limit_trust_proxy must default to False (secure by default)."""
    from langflow.services.deps import get_settings_service

    assert get_settings_service().settings.rate_limit_trust_proxy is False
