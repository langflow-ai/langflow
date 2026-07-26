"""Ensemble suite Locust user — optional marker only.

Prefer listing solo user classes in ``user_mix`` (see ``ensemble_suite.json``).
This class remains registered for backward-compatible profiles that name it
explicitly; it should not be the only entry in a Tutti suite profile.
"""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.users.base import PerfBaseUser


class EnsembleSuiteUser(PerfBaseUser):
    """Deprecated marker user — Tutti suite profiles should compose solo classes."""

    weight = 1
    workload_name = "ensemble_suite"
    flow_class = "marker"

    @task
    def suite_step(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        raise RuntimeError(
            "EnsembleSuiteUser is a marker only; update the profile user_mix to "
            "list concurrent solo user classes (ChatDbUser, QueueUser, ...)"
        )
