from threading import Lock

from langflow_execution.services.job_queue.service import JobQueueService
from langflow_execution.services.settings.service import SettingsService
from langflow_execution.services.state.service import InMemoryStateService
from langflow_execution.services.telemetry.service import TelemetryService


class ServiceManager:
    """Singleton service manager for the execution layer.

    Ensures only one instance exists (thread-safe) and provides lifecycle management (start/stop) for all services.
    """

    _instance = None
    _instance_lock = Lock()

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("Use ServiceManager.get_instance() to get the singleton instance.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._start_services()
                    cls._instance = obj
        return cls._instance

    def _start_services(self):
        self.settings_service = SettingsService()
        self.job_queue_service = JobQueueService()
        self.state_service = InMemoryStateService()
        self.telemetry_service = TelemetryService(settings_service=self.settings_service)

        self.job_queue_service.start()
        self.telemetry_service.start()

    async def stop(self):
        await self.job_queue_service.teardown()
        await self.state_service.teardown()
        await self.settings_service.teardown()
        await self.telemetry_service.teardown()

    def get_telemetry_service(self):
        return self.telemetry_service

    def get_job_queue_service(self):
        return self.job_queue_service

    def get_state_service(self):
        return self.state_service

    def get_settings_service(self):
        return self.settings_service
