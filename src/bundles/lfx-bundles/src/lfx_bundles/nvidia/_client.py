"""Session policy for the NVIDIA SDK's blocking and asynchronous clients."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock

from lfx.base.models.provider_ssrf import validate_provider_base_url
from lfx.utils.ssrf_protection import is_connector_ssrf_validation_enabled, validate_and_resolve_url
from lfx.utils.ssrf_requests import refuse_aiohttp_redirects, refuse_redirects

from lfx_bundles.nvidia._transport import pin_aiohttp_session, pin_requests_session

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
# NVIDIA hosts some catalog models separately and polls its status service after a 202.
_POLLING_ORIGIN = "https://api.nvcf.nvidia.com"
_HOSTED_MODEL_ORIGIN = "https://ai.api.nvidia.com"
_PENDING_PIN: ContextVar[tuple[str, list[str]] | None] = ContextVar("nvidia_endpoint_pin", default=None)
_POLICY_LOCK = Lock()
_SESSION_POLICY_INSTALLED = "_lfx_nvidia_session_policy_installed"


@contextmanager
def nvidia_client_policy(base_url: str | None) -> Iterator[None]:
    """Bind the validated endpoint to the client's sessions before model discovery."""
    validate_provider_base_url(base_url, default_url=DEFAULT_NVIDIA_BASE_URL)
    ips = []
    if base_url and base_url.rstrip("/") != DEFAULT_NVIDIA_BASE_URL and is_connector_ssrf_validation_enabled():
        # The shared provider preflight enforces HTTPS. Resolve and validate the
        # addresses we actually hand to the SDK using the same LFX IP policy.
        _, ips = validate_and_resolve_url(base_url)
    _install_session_policy()
    token = _PENDING_PIN.set((base_url, ips) if base_url and ips else None)
    try:
        yield
    finally:
        _PENDING_PIN.reset(token)


def _guard_session_factory(client_cls, factory_name, field_name, refuse_redirect, pin_session):
    if client_cls.__dict__.get(_SESSION_POLICY_INSTALLED):
        return
    original_init = client_cls.__init__
    original_factory = getattr(client_cls, factory_name)

    def create_session(self):
        session = refuse_redirect(original_factory(self))
        # The constructor can use a session before returning. Later calls use
        # the pin captured by this instance, including calls on another thread.
        pin = getattr(self, "_lfx_nvidia_endpoint_pin", _PENDING_PIN.get())
        if pin:
            base_url, ips = pin
            trusted = (_POLLING_ORIGIN, _HOSTED_MODEL_ORIGIN) if self.is_hosted else (_POLLING_ORIGIN,)
            pin_session(session, base_url, ips, trusted_origins=trusted)
        return session

    def guarded_init(self, **kwargs):
        kwargs.setdefault(field_name, getattr(self, factory_name))
        original_init(self, **kwargs)
        self._lfx_nvidia_endpoint_pin = _PENDING_PIN.get()

    setattr(client_cls, factory_name, create_session)
    client_cls.__init__ = guarded_init
    setattr(client_cls, _SESSION_POLICY_INSTALLED, True)


def _install_session_policy() -> None:
    """Wrap the SDK's session factories once, including constructor-time requests."""
    try:
        from langchain_nvidia_ai_endpoints import _common
    except ImportError as e:
        msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
        raise ImportError(msg) from e

    client_specs = (
        ("_NVIDIABaseClient", "_create_session", "get_session_fn", refuse_redirects, pin_requests_session),
        (
            "_NVIDIAAsyncClient",
            "_create_async_session",
            "get_async_session_fn",
            refuse_aiohttp_redirects,
            pin_aiohttp_session,
        ),
    )
    with _POLICY_LOCK:
        clients = []
        for class_name, factory_name, field_name, refuse_redirect, pin_session in client_specs:
            client_cls = getattr(_common, class_name, None)
            if client_cls is None:
                msg = f"Cannot protect NVIDIA sessions: the SDK no longer exposes '{class_name}'."
                raise ValueError(msg)
            if not all(callable(getattr(client_cls, name, None)) for name in ("__init__", factory_name)):
                msg = "Cannot protect NVIDIA sessions: the SDK no longer exposes its session factories."
                raise ValueError(msg)
            clients.append((client_cls, factory_name, field_name, refuse_redirect, pin_session))
        for client in clients:
            _guard_session_factory(*client)
