"""Credential-safe diagnostics for this client's own HTTP requests."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import logging
import re
from urllib.parse import quote, quote_plus

from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool

_active_key: ContextVar[str | None] = ContextVar("fxmacrodata_transport_key", default=None)


def redact_text(value: str, api_key: str) -> str:
    if api_key:
        variants = {api_key, quote(api_key, safe=""), quote_plus(api_key, safe="")}
        variants.update(re.sub(r"%[0-9A-F]{2}", lambda match: match[0].lower(), variant) for variant in tuple(variants))
        for encoded in sorted(variants, key=len, reverse=True):
            value = value.replace(encoded, "[redacted]")
    value = re.sub(r"(?i)((?:proxy[_-]?)?authorization[\"']?\s*[:=]\s*[\"']?)(?:Bearer|Basic)\s+[^\s\"'&<>]+", r"\1[redacted]", value)
    return re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|authorization|password|client[_-]?secret|token)[\"']?\s*[:=]\s*[\"']?)[^\s\"'&<>]+", r"\1[redacted]", value)


class _CredentialFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        key = _active_key.get()
        if key is None:
            return True
        try:
            record.msg = redact_text(record.getMessage(), key)
            record.args = ()
            if record.exc_info:
                record.exc_text = redact_text(logging.Formatter().formatException(record.exc_info), key)
                record.exc_info = None
            elif record.exc_text:
                record.exc_text = redact_text(record.exc_text, key)
            if record.stack_info:
                record.stack_info = redact_text(record.stack_info, key)
        except Exception:
            record.msg, record.args, record.exc_info, record.exc_text = "FXMacroData transport diagnostic unavailable.", (), None, None
        return True


_filter = _CredentialFilter()


@contextmanager
def protected_diagnostics(api_key: str):
    """Redact only the active request's diagnostics; retain other clients' logs."""
    for name in ("urllib3.connectionpool", "urllib3.util.retry", "urllib3.poolmanager", "requests.packages.urllib3.connectionpool"):
        logging.getLogger(name).addFilter(_filter)
    token = _active_key.set(api_key)
    try:
        yield
    finally:
        _active_key.reset(token)


class _PrivateHTTPSConnection(HTTPSConnection):
    # http.client wire debugging writes raw request bytes directly to stdout.
    # Its global flag must not enable that behavior on this connection.
    debuglevel = 0


class _PrivateHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PrivateHTTPSConnection


class CredentialSafeAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {**self.poolmanager.pool_classes_by_scheme, "https": _PrivateHTTPSPool}

    def proxy_manager_for(self, *args, **kwargs):
        manager = super().proxy_manager_for(*args, **kwargs)
        manager.pool_classes_by_scheme = {**manager.pool_classes_by_scheme, "https": _PrivateHTTPSPool}
        return manager
