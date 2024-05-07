from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler import Job
from pydantic import BaseModel, Field, field_validator


# Adapted from
# https://github.com/amisadmin/fastapi-scheduler/blob/master/fastapi_scheduler/admin.py
class JobModel(BaseModel):
    id: str = Field(..., title="Job ID")
    name: str = Field(..., title="Job Name")
    next_run_time: Optional[datetime] = Field(
        None,
    )
    trigger: Optional[str] = Field(None)  # BaseTrigger
    func_ref: str = Field(..., title="Function")
    args: List[Any] = Field([], title="Tuple Args")
    kwargs: Dict[str, Any] = Field(
        {},
    )
    executor: str = Field("default")
    max_instances: Optional[int] = Field(None)
    misfire_grace_time: Optional[int] = Field(None, title="Misfire Grace Time")
    coalesce: Optional[bool] = Field(None, title="Coalesce")

    @field_validator("trigger", mode="before")
    def trigger_valid(cls, v):
        return str(v)

    @classmethod
    def parse_job(cls, job: Job):
        return job and cls(**{k: getattr(job, k, None) for k in cls.model_fields.keys()})
        return job and cls(**{k: getattr(job, k, None) for k in cls.model_fields.keys()})
