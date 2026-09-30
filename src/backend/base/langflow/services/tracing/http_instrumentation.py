"""Process-scoped HTTP client instrumentation manager with reference counting.

The OpenTelemetry RequestsInstrumentor and URLLib3Instrumentor monkeypatch globally,
so we need to coordinate instrumentation across all tracer instances to avoid one
tracer's end() call breaking propagation for other in-flight traces.
"""

import threading
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider


class HTTPClientInstrumentationManager:
    """Manages HTTP client instrumentation with reference counting.

    This ensures instrumentation is only enabled once per process and only
    disabled when all tracers have finished.
    """

    _instance: "HTTPClientInstrumentationManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "HTTPClientInstrumentationManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._ref_count = 0
        self._ref_lock = threading.Lock()
        self._requests_instrumented = False
        self._urllib3_instrumented = False
        self._initialized = True

    def enable(self, tracer_provider: "TracerProvider | None" = None) -> None:
        """Enable HTTP client instrumentation, incrementing the reference count.

        Only instruments on the first call; subsequent calls just increment the count.
        """
        with self._ref_lock:
            self._ref_count += 1
            if self._ref_count == 1:
                self._instrument(tracer_provider)

    def disable(self) -> None:
        """Disable HTTP client instrumentation, decrementing the reference count.

        Only uninstruments when the count reaches zero.
        """
        with self._ref_lock:
            if self._ref_count > 0:
                self._ref_count -= 1
            if self._ref_count == 0:
                self._uninstrument()

    def _instrument(self, tracer_provider: "TracerProvider | None") -> None:
        """Instrument requests and urllib3 libraries."""
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor

            RequestsInstrumentor().instrument(tracer_provider=tracer_provider)
            self._requests_instrumented = True
            logger.debug("HTTP client instrumentation enabled for requests library")
        except ImportError:
            logger.debug("opentelemetry-instrumentation-requests not available, skipping.")

        try:
            from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

            URLLib3Instrumentor().instrument(tracer_provider=tracer_provider)
            self._urllib3_instrumented = True
            logger.debug("HTTP client instrumentation enabled for urllib3 library")
        except ImportError:
            logger.debug("opentelemetry-instrumentation-urllib3 not available, skipping.")

    def _uninstrument(self) -> None:
        """Uninstrument HTTP clients with proper error logging."""
        if self._requests_instrumented:
            try:
                from opentelemetry.instrumentation.requests import RequestsInstrumentor

                RequestsInstrumentor().uninstrument()
                self._requests_instrumented = False
                logger.debug("HTTP client instrumentation disabled for requests library")
            except ImportError:
                pass
            except Exception:  # noqa: BLE001
                logger.warning("Unexpected error uninstrumenting requests library", exc_info=True)

        if self._urllib3_instrumented:
            try:
                from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

                URLLib3Instrumentor().uninstrument()
                self._urllib3_instrumented = False
                logger.debug("HTTP client instrumentation disabled for urllib3 library")
            except ImportError:
                pass
            except Exception:  # noqa: BLE001
                logger.warning("Unexpected error uninstrumenting urllib3 library", exc_info=True)


def get_http_instrumentation_manager() -> HTTPClientInstrumentationManager:
    """Get the singleton HTTP client instrumentation manager."""
    return HTTPClientInstrumentationManager()
