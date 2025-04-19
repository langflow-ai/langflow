from __future__ import annotations

import asyncio
import os
import platform
import socket
import sys
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import uvicorn
from loguru import logger
from prometheus_client import make_asgi_app

from langflow.services.base import Service
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from langflow.services.telemetry.schema import (
    ComponentPayload,
    PlaygroundPayload,
    RunPayload,
    ShutdownPayload,
    VersionPayload,
)
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from langflow.services.settings.service import SettingsService


class TelemetryService(Service):
    name = "telemetry_service"

    # Class-level lock for thread-safe metrics server operations
    _metrics_server_lock = threading.Lock()

    def __init__(self, settings_service: SettingsService, uvicorn_run: Callable | None = None):
        """Initialize the TelemetryService.

        Args:
            settings_service: Service providing configuration settings
            uvicorn_run: Optional callable that replaces uvicorn.run (for testing)
        """
        super().__init__()
        self.settings_service = settings_service
        self.base_url = settings_service.settings.telemetry_base_url
        self.telemetry_queue: asyncio.Queue = asyncio.Queue()
        self.client = httpx.AsyncClient(timeout=10.0)  # Set a reasonable timeout
        self.running = False
        self._stopping = False

        self.ot = OpenTelemetry(prometheus_enabled=settings_service.settings.prometheus_enabled)
        self.architecture: str | None = None
        self.worker_task: asyncio.Task | None = None
        # Check for do-not-track settings
        self.do_not_track = (
            os.getenv("DO_NOT_TRACK", "False").lower() == "true" or settings_service.settings.do_not_track
        )
        self.log_package_version_task: asyncio.Task | None = None

        # Metrics server management
        self._metrics_thread: threading.Thread | None = None
        self._metrics_server_started = False
        # Event to signal the metrics server thread to stop
        self._metrics_server_stop_event = threading.Event()
        # For testability; allows mocking the server during tests
        self._uvicorn_run = uvicorn_run  # Defaults to uvicorn.run if None

    async def telemetry_worker(self) -> None:
        while self.running:
            func, payload, path = await self.telemetry_queue.get()
            try:
                await func(payload, path)
            except Exception:  # noqa: BLE001
                logger.error("Error sending telemetry data")
            finally:
                self.telemetry_queue.task_done()

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        if self.do_not_track:
            logger.debug("Telemetry tracking is disabled.")
            return

        url = f"{self.base_url}"
        if path:
            url = f"{url}/{path}"
        try:
            payload_dict = payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
            response = await self.client.get(url, params=payload_dict)
            if response.status_code != httpx.codes.OK:
                logger.error(f"Failed to send telemetry data: {response.status_code} {response.text}")
            else:
                logger.debug("Telemetry data sent successfully.")
        except httpx.HTTPStatusError:
            logger.error("HTTP error occurred")
        except httpx.RequestError:
            logger.error("Request error occurred")
        except Exception:  # noqa: BLE001
            logger.error("Unexpected error occurred")

    async def log_package_run(self, payload: RunPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "run"))

    async def log_package_shutdown(self) -> None:
        payload = ShutdownPayload(time_running=(datetime.now(timezone.utc) - self._start_time).seconds)
        await self._queue_event(payload)

    async def _queue_event(self, payload) -> None:
        if self.do_not_track or self._stopping:
            return
        await self.telemetry_queue.put(payload)

    def _get_langflow_desktop(self) -> bool:
        # Coerce to bool, could be 1, 0, True, False, "1", "0", "True", "False"
        return str(os.getenv("LANGFLOW_DESKTOP", "False")).lower() in {"1", "true"}

    async def log_package_version(self) -> None:
        python_version = ".".join(platform.python_version().split(".")[:2])
        version_info = get_version_info()
        if self.architecture is None:
            self.architecture = (await asyncio.to_thread(platform.architecture))[0]
        payload = VersionPayload(
            package=version_info["package"].lower(),
            version=version_info["version"],
            platform=platform.platform(),
            python=python_version,
            cache_type=self.settings_service.settings.cache_type,
            backend_only=self.settings_service.settings.backend_only,
            arch=self.architecture,
            auto_login=self.settings_service.auth_settings.AUTO_LOGIN,
            desktop=self._get_langflow_desktop(),
        )
        await self._queue_event((self.send_telemetry_data, payload, None))

    async def log_package_playground(self, payload: PlaygroundPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "playground"))

    async def log_package_component(self, payload: ComponentPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "component"))

    def start(self, fastapi_version: str, langflow_version: str) -> None:
        """Start the telemetry service and optionally the metrics server.

        This method initializes the telemetry worker and starts the Prometheus
        metrics server if enabled in settings.

        Args:
            fastapi_version: Version of FastAPI being used
            langflow_version: Version of Langflow being used
        """
        if self.running:
            logger.info("TelemetryService already running; skipping telemetry startup")
            return

        try:
            if (
                self.settings_service.settings.prometheus_enabled
                and os.getenv("LANGFLOW_METRICS_PORT_MODE") == "separate"
                and not self._metrics_server_started
            ):
                # Add metrics for fastapi and langflow versions
                self.ot.update_gauge(metric_name="fastapi_version", value=1.0, labels={"version": fastapi_version})
                self.ot.update_gauge(metric_name="langflow_version", value=1.0, labels={"version": langflow_version})

                # Start metrics server
                logger.debug("Starting metrics server")
                self.start_metrics_server()

            self.running = True

            if self.do_not_track:
                logger.info("TelemetryService disabled due to do_not_track; skipping telemetry startup")
                return

            self._start_time = datetime.now(timezone.utc)
            self.worker_task = asyncio.create_task(self.telemetry_worker())
            self.log_package_version_task = asyncio.create_task(self.log_package_version())
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Error starting TelemetryService telemetry: {e}")
            self.running = False  # Reset running state on failure

    async def flush(self) -> None:
        if self.do_not_track:
            return
        try:
            await self.telemetry_queue.join()
        except Exception:  # noqa: BLE001
            logger.exception("Error flushing logs")

    @staticmethod
    async def _cancel_task(task: asyncio.Task, cancel_msg: str) -> None:
        task.cancel(cancel_msg)
        await asyncio.wait([task])
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                raise exc

    async def stop(self) -> None:
        if self.do_not_track or self._stopping:
            return
        try:
            self._stopping = True
            # flush all the remaining events and then stop
            await self.flush()
            self.running = False
            if self.worker_task:
                await self._cancel_task(self.worker_task, "Cancel telemetry worker task")
            if self.log_package_version_task:
                await self._cancel_task(self.log_package_version_task, "Cancel telemetry log package version task")
            await self.client.aclose()
        except Exception:  # noqa: BLE001
            logger.exception("Error stopping tracing service")

    async def teardown(self) -> None:
        # First stop the metrics server (synchronous operation)
        self.stop_metrics_server(join=True, timeout=2.0)  # Add a reasonable timeout

        await self.stop()

    @classmethod
    def is_test_environment(cls) -> bool:
        """Check if we're running in a test environment.

        Returns:
            bool: True if running in a test environment, False otherwise.
        """
        return "pytest" in sys.modules or os.environ.get("TESTING") == "True"

    def start_metrics_server(
        self,
        thread_name: str = "PrometheusMetricsServer",
        daemon: bool = True,  # noqa: FBT001, FBT002
        on_error: Callable[[Exception], None] | None = None,
        bypass_test_check: bool = False,  # Add this parameter  # noqa: FBT001, FBT002
    ) -> None:
        """Start Prometheus metrics server on a separate port if configured.

        This method ensures thread safety using a lock mechanism and prevents
        port conflicts by checking for port availability before starting the server.
        It also handles proper state management to maintain consistency.

        Args:
            thread_name: Name of the server thread (default: "PrometheusMetricsServer")
            daemon: Whether the server thread is a daemon (default: True)
            on_error: Optional callback to notify on server startup failure
                    Function signature: callback(exception)
            bypass_test_check: Whether to bypass test environment detection (default: False).
                            This should only be used in specific test cases that
                            explicitly need to verify server functionality.

        Implementation details:
            - Uses thread lock to prevent race conditions when multiple threads try to start the server
            - Checks if port is already in use to prevent "address already in use" errors
            - Sets flag before starting thread to prevent race conditions
            - Provides configurable thread properties for better control
            - Supports error notification through callback
            - Avoids starting the actual server in test environments to prevent
                port conflicts and race conditions during parallel test execution
        """
        with self._metrics_server_lock:  # Thread safety lock
            # Early exit if already started (flag check)
            if self._metrics_server_started:
                logger.debug("Prometheus metrics server already marked as started. Skipping start.")
                return

            # Check if we're in a test environment (unless bypass_test_check is True)
            # This helps prevent port conflicts and resource issues during parallel testing
            if not bypass_test_check and self.is_test_environment():
                logger.debug("Test environment detected. Skipping metrics server startup.")
                self._metrics_server_started = True
                return

            # Check if thread exists and is running (thread check)
            if self._metrics_thread and self._metrics_thread.is_alive():
                logger.debug("Prometheus metrics server already running (thread check). Skipping start.")
                self._metrics_server_started = True
                return

            # Set flag before starting the thread to prevent race conditions
            self._metrics_server_started = True
            self._metrics_server_stop_event.clear()

            port = self.settings_service.settings.prometheus_port
            host = os.getenv("LANGFLOW_METRICS_HOST", "0.0.0.0")  # noqa: S104
            log_level = os.getenv("LANGFLOW_METRICS_LOG_LEVEL", "warning")

            metrics_app = make_asgi_app()
            # Use injected function or default to uvicorn.run (for testability)
            uvicorn_run = self._uvicorn_run or uvicorn.run

            def run_metrics_server():
                """Thread target function that runs the metrics server."""
                try:
                    # Check if the port is already in use before starting
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        if s.connect_ex((host, port)) == 0:
                            logger.warning(f"Port {port} is already in use. Metrics server will not start.")
                            self._metrics_server_started = False
                            return
                    logger.info(f"Starting Prometheus metrics server at http://{host}:{port}/metrics")
                    uvicorn_run(
                        metrics_app,
                        host=host,
                        port=port,
                        log_level=log_level,
                        # Optional future tuning
                        access_log=False,
                        timeout_keep_alive=5,
                    )
                except BaseException as e:  # catch Exception *and* SystemExit  # noqa: BLE001
                    logger.exception(f"Failed to start Prometheus metrics server on {host}:{port}: {e}")
                    # Reset the flag if the server fails to start
                    self._metrics_server_started = False
                    # Notify caller of failure if callback provided
                    if on_error:
                        on_error(e)

            # Create and start the server thread
            self._metrics_thread = threading.Thread(
                target=run_metrics_server,
                name=thread_name,
                daemon=daemon,  # daemon threads exit when main process exits
            )
            self._metrics_thread.start()
            logger.info(f"Prometheus metrics server thread '{thread_name}' started (daemon={daemon}) on port {port}")

    def stop_metrics_server(self, join: bool = True, timeout: float | None = None) -> None:  # noqa: FBT001, FBT002
        """Attempt to gracefully stop the metrics server thread.

        Since uvicorn.run() doesn't provide a built-in way to stop the server,
        this method signals the thread to stop and optionally waits for it.

        Args:
            join: Whether to join the thread after signaling stop (default: True)
            timeout: Timeout in seconds for joining the thread (default: None, wait indefinitely)

        Implementation details:
            - Uses thread lock to prevent race conditions with start operations
            - Sets stop event to signal the server thread
            - Optionally joins the thread with timeout
            - Resets state flags to maintain consistency
        """
        with self._metrics_server_lock:  # Thread safety lock
            # Early exit if server not running
            if not self._metrics_server_started or not self._metrics_thread:
                logger.info("Metrics server is not running.")
                return
            # Signal thread to stop via event
            # NOTE: There is no direct way to stop uvicorn.run in this context,
            # but the stop event is set for future implementations that might use it
            self._metrics_server_stop_event.set()

            # Optionally wait for thread to finish
            if join and self._metrics_thread:
                self._metrics_thread.join(timeout=timeout)

            # Reset state flag to indicate server is no longer running
            self._metrics_server_started = False
            logger.info("Prometheus metrics server stopped.")
