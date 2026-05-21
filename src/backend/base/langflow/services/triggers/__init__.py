"""Native triggers — schedule, queue, dispatch flow runs.

The schedule lives as a ``CronTrigger`` component inside a flow's
canvas. This package owns the surrounding machinery:

* ``scheduler`` — pure cron/timezone math (validation, next-fire).
* ``discovery`` — pure parsing of CronTrigger nodes out of
  ``flow.data``.
* ``lifecycle`` — side effects on flow save (reconcile trigger_jobs).
* ``worker`` — the in-process async loop draining the queue.
"""

from .discovery import (
    CronTriggerConfig,
    find_cron_trigger_configs,
    find_cron_trigger_nodes,
    parse_cron_trigger_config,
)
from .lifecycle import reconcile_trigger_jobs_for_flow
from .scheduler import (
    InvalidTriggerConfigError,
    next_fire_time_utc,
    validate_cron_expression,
    validate_timezone,
    validate_trigger_config,
)
from .worker import recover_stalled_jobs, trigger_worker_loop

__all__ = [
    "CronTriggerConfig",
    "InvalidTriggerConfigError",
    "find_cron_trigger_configs",
    "find_cron_trigger_nodes",
    "next_fire_time_utc",
    "parse_cron_trigger_config",
    "reconcile_trigger_jobs_for_flow",
    "recover_stalled_jobs",
    "trigger_worker_loop",
    "validate_cron_expression",
    "validate_timezone",
    "validate_trigger_config",
]
