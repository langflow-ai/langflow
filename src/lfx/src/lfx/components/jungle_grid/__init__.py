from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .artifact_download_url import JungleGridCreateArtifactDownloadURLComponent
    from .cancel_job import JungleGridCancelJobComponent
    from .create_job_input_upload import JungleGridCreateJobInputUploadComponent
    from .estimate_job import JungleGridEstimateJobComponent
    from .get_job_events import JungleGridGetJobEventsComponent
    from .get_job_logs import JungleGridGetJobLogsComponent
    from .get_job_runtime import JungleGridGetJobRuntimeComponent
    from .get_job_status import JungleGridGetJobStatusComponent
    from .list_job_artifacts import JungleGridListJobArtifactsComponent
    from .list_job_inputs import JungleGridListJobInputsComponent
    from .list_jobs import JungleGridListJobsComponent
    from .submit_job import JungleGridSubmitJobComponent

_dynamic_imports = {
    "JungleGridCancelJobComponent": "cancel_job",
    "JungleGridCreateArtifactDownloadURLComponent": "artifact_download_url",
    "JungleGridCreateJobInputUploadComponent": "create_job_input_upload",
    "JungleGridEstimateJobComponent": "estimate_job",
    "JungleGridGetJobEventsComponent": "get_job_events",
    "JungleGridGetJobLogsComponent": "get_job_logs",
    "JungleGridGetJobRuntimeComponent": "get_job_runtime",
    "JungleGridGetJobStatusComponent": "get_job_status",
    "JungleGridListJobInputsComponent": "list_job_inputs",
    "JungleGridListJobArtifactsComponent": "list_job_artifacts",
    "JungleGridListJobsComponent": "list_jobs",
    "JungleGridSubmitJobComponent": "submit_job",
}

__all__ = [
    "JungleGridCancelJobComponent",
    "JungleGridCreateArtifactDownloadURLComponent",
    "JungleGridCreateJobInputUploadComponent",
    "JungleGridEstimateJobComponent",
    "JungleGridGetJobEventsComponent",
    "JungleGridGetJobLogsComponent",
    "JungleGridGetJobRuntimeComponent",
    "JungleGridGetJobStatusComponent",
    "JungleGridListJobArtifactsComponent",
    "JungleGridListJobInputsComponent",
    "JungleGridListJobsComponent",
    "JungleGridSubmitJobComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import Jungle Grid components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
