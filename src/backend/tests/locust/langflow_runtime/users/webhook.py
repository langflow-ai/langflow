"""Webhook Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.metrics.correctness import expect_webhook_n_accept_n_complete
from tests.locust.langflow_runtime.metrics.registry import TrackedWebhookCopy
from tests.locust.langflow_runtime.users.base import (
    PerfBaseUser,
    get_or_create_arrival_accountant,
    get_or_create_webhook_pool,
)
from tests.locust.langflow_runtime.v1_contracts import DEFAULT_WEBHOOK_PAYLOAD


class WebhookUser(PerfBaseUser):
    weight = 1
    workload_name = "webhook"
    flow_class = "passthrough"

    def _paced(self) -> bool:
        return bool(self.run_context is not None and self.run_context.profile.workload.workload_model == "paced_closed")

    @task
    def webhook(self) -> None:
        if self.run_context is None:
            return
        accountant = get_or_create_arrival_accountant(self.environment) if self._paced() else None
        if accountant is not None:
            accountant.record_intended_slot()
        if self.stop_new_arrivals():
            if accountant is not None:
                accountant.record_miss("stop_new_arrivals")
            return

        client = self.webhooks_client()
        pool = get_or_create_webhook_pool(self.environment, self.provision_state)
        if client is None or pool is None:
            if accountant is not None:
                accountant.record_miss("missing_client_or_pool")
            raise RuntimeError("webhook client/pool unavailable")

        if accountant is not None:
            accountant.record_attempt()
        copy = pool.lease(timeout_s=5.0)
        copy_id = f"{copy.flow_id}:{copy.endpoint_name}"
        if not any(row.copy_id == copy_id for row in self.registry.list_webhooks()):
            self.registry.register_webhook(TrackedWebhookCopy(copy_id=copy_id, endpoint=copy.endpoint_name))
        current = next(row for row in self.registry.list_webhooks() if row.copy_id == copy_id)
        self.registry.update_webhook(copy_id, in_flight=current.in_flight + 1)

        try:
            result = client.subscribe_post_complete(copy, dict(DEFAULT_WEBHOOK_PAYLOAD), timeout_s=self.deadline_s())
            if result.accepted and accountant is not None:
                accountant.record_accepted()
            current = next(row for row in self.registry.list_webhooks() if row.copy_id == copy_id)
            accepted = current.accepted_count + (1 if result.accepted else 0)
            completed = current.completed_count + (1 if result.completed else 0)
            self.registry.update_webhook(copy_id, accepted_count=accepted, completed_count=completed)
            check = expect_webhook_n_accept_n_complete(accepted, completed)
            if result.error:
                if accountant is not None and not result.accepted:
                    accountant.record_miss("webhook_error")
                raise RuntimeError(result.error)
            if result.completed and accountant is not None:
                accountant.record_terminal(success=True)
            if result.accepted and result.completed and not check.ok:
                raise AssertionError(check.reason)
        finally:
            current = next((row for row in self.registry.list_webhooks() if row.copy_id == copy_id), None)
            if current is not None:
                self.registry.update_webhook(copy_id, in_flight=max(0, current.in_flight - 1))
            pool.release(copy)
