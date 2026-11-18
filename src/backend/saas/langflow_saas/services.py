"""Service layer for the SaaS plugin.

Three services:

  AuditService   — append-only audit log writer.
  EmailService   — abstraction over multiple email providers (console,
                   SMTP, SendGrid, Resend).  Provider is selected at startup
                   from SAAS_EMAIL_PROVIDER.
  BillingService — Stripe integration: create/sync subscriptions, handle
                   webhook events.

All services are module-level singletons initialised lazily on first use.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from uuid import UUID

logger = logging.getLogger("langflow_saas.services")


# ===========================================================================
# Audit Service
# ===========================================================================


class AuditService:
    """Append-only structured audit log.  Never modifies or deletes rows."""

    async def log(
        self,
        *,
        action: str,
        org_id: UUID | None = None,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        log_metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        try:
            from langflow.services.deps import session_scope

            from langflow_saas.models import AuditLog

            entry = AuditLog(
                action=action,
                org_id=org_id,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                log_metadata=log_metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            async with session_scope() as db:
                db.add(entry)
                await db.commit()
        except Exception:  # noqa: BLE001
            # Audit failures must never surface to callers.
            logger.warning("Failed to write audit log: action=%s org=%s user=%s", action, org_id, user_id)


_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service


# ===========================================================================
# Email Service
# ===========================================================================


class BaseEmailService(ABC):
    """Abstract email sender.  Implement send_raw() in subclasses."""

    @abstractmethod
    async def send_raw(self, *, to: str, subject: str, html: str, text: str) -> None: ...

    async def send_invitation(
        self,
        *,
        to_email: str,
        org_name: str,
        inviter_name: str,
        role: str,
        accept_url: str,
        expire_hours: int,
    ) -> None:
        subject = f"You've been invited to join {org_name} on Langflow"
        html = f"""
        <h2>You're invited!</h2>
        <p><b>{inviter_name}</b> has invited you to join <b>{org_name}</b>
           as a <b>{role}</b>.</p>
        <p>This invitation expires in {expire_hours} hours.</p>
        <p><a href="{accept_url}" style="padding:10px 20px;background:#4f46e5;color:white;
           text-decoration:none;border-radius:4px">Accept Invitation</a></p>
        <p>Or copy this URL: {accept_url}</p>
        """
        text = (
            f"{inviter_name} invited you to join {org_name} as {role}.\n"
            f"Accept here: {accept_url}\n"
            f"Expires in {expire_hours} hours."
        )
        await self.send_raw(to=to_email, subject=subject, html=html, text=text)

    async def send_password_reset(self, *, to_email: str, reset_url: str, expire_hours: int) -> None:
        subject = "Reset your Langflow password"
        html = f"""
        <h2>Password Reset Request</h2>
        <p>We received a request to reset your password.</p>
        <p>This link expires in {expire_hours} hours.</p>
        <p><a href="{reset_url}" style="padding:10px 20px;background:#4f46e5;color:white;
           text-decoration:none;border-radius:4px">Reset Password</a></p>
        <p>If you didn't request this, ignore this email.</p>
        """
        text = f"Reset your password: {reset_url}\nExpires in {expire_hours} hours."
        await self.send_raw(to=to_email, subject=subject, html=html, text=text)

    async def send_quota_warning(self, *, to_email: str, org_name: str, metric: str, used: int, limit: int) -> None:
        pct = int(used / limit * 100) if limit else 0
        subject = f"[{org_name}] Usage alert: {pct}% of {metric} quota used"
        html = f"""
        <h2>Usage Alert for {org_name}</h2>
        <p>Your organization has used <b>{used}/{limit}</b> ({pct}%) of its
           daily <b>{metric}</b> quota.</p>
        <p>Upgrade your plan to increase your limits.</p>
        """
        text = f"[{org_name}] {metric}: {used}/{limit} ({pct}%) used."
        await self.send_raw(to=to_email, subject=subject, html=html, text=text)


class ConsoleEmailService(BaseEmailService):
    """Development stub — prints emails to stdout instead of sending them."""

    async def send_raw(self, *, to: str, subject: str, html: str, text: str) -> None:
        logger.info("=== [EMAIL] To: %s | Subject: %s ===\n%s", to, subject, text)


class SMTPEmailService(BaseEmailService):
    def __init__(self) -> None:
        from langflow_saas.settings import get_saas_settings

        s = get_saas_settings()
        self._host = s.smtp_host
        self._port = s.smtp_port
        self._starttls = s.smtp_starttls
        self._user = s.smtp_user
        self._password = s.smtp_password.get_secret_value()
        self._from = f"{s.email_from_name} <{s.email_from}>"

    async def send_raw(self, *, to: str, subject: str, html: str, text: str) -> None:
        import asyncio

        await asyncio.to_thread(self._send_sync, to=to, subject=subject, html=html, text=text)

    def _send_sync(self, *, to: str, subject: str, html: str, text: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = to
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(self._host, self._port) as server:
            if self._starttls:
                server.starttls(context=context)
            if self._user:
                server.login(self._user, self._password)
            server.sendmail(self._from, [to], msg.as_string())


class SendGridEmailService(BaseEmailService):
    def __init__(self) -> None:
        from langflow_saas.settings import get_saas_settings

        s = get_saas_settings()
        self._api_key = s.sendgrid_api_key.get_secret_value()
        self._from = s.email_from
        self._from_name = s.email_from_name

    async def send_raw(self, *, to: str, subject: str, html: str, text: str) -> None:
        import httpx

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self._from, "name": self._from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text},
                {"type": "text/html", "value": html},
            ],
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10,
            )
            resp.raise_for_status()


class ResendEmailService(BaseEmailService):
    def __init__(self) -> None:
        from langflow_saas.settings import get_saas_settings

        s = get_saas_settings()
        self._api_key = s.resend_api_key.get_secret_value()
        self._from = f"{s.email_from_name} <{s.email_from}>"

    async def send_raw(self, *, to: str, subject: str, html: str, text: str) -> None:
        import httpx

        payload = {"from": self._from, "to": [to], "subject": subject, "html": html, "text": text}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10,
            )
            resp.raise_for_status()


_email_service: BaseEmailService | None = None


def get_email_service() -> BaseEmailService:
    global _email_service
    if _email_service is None:
        from langflow_saas.settings import get_saas_settings

        provider = get_saas_settings().email_provider.lower()
        _email_service = {
            "console": ConsoleEmailService,
            "smtp": SMTPEmailService,
            "sendgrid": SendGridEmailService,
            "resend": ResendEmailService,
        }.get(provider, ConsoleEmailService)()
    return _email_service


# ===========================================================================
# Billing Service  (Stripe)
# ===========================================================================


class BillingService:
    """Stripe billing operations.

    All Stripe calls are gated behind ``settings.billing_enabled`` so the
    plugin works without Stripe credentials in development.
    """

    def _stripe(self):
        """Return the configured stripe module or raise if not available."""
        import stripe as _stripe

        from langflow_saas.settings import get_saas_settings

        key = get_saas_settings().stripe_secret_key.get_secret_value()
        if not key:
            raise RuntimeError("SAAS_STRIPE_SECRET_KEY is not set.")
        _stripe.api_key = key
        return _stripe

    async def get_or_create_customer(self, *, org_id: UUID, org_name: str, email: str) -> str:
        """Return Stripe customer_id, creating one if absent."""
        import asyncio

        from langflow.services.deps import session_scope
        from sqlmodel import select

        from langflow_saas.models import Organization

        async with session_scope() as db:
            result = await db.exec(select(Organization).where(Organization.id == org_id))
            org = result.first()
            if org and org.stripe_customer_id:
                return org.stripe_customer_id

        # Create new Stripe customer.
        stripe = self._stripe()
        customer = await asyncio.to_thread(
            stripe.Customer.create,
            name=org_name,
            email=email,
            metadata={"langflow_org_id": str(org_id)},
        )
        customer_id: str = customer["id"]

        # Persist the customer_id.
        async with session_scope() as db:
            result = await db.exec(select(Organization).where(Organization.id == org_id))
            org = result.first()
            if org:
                org.stripe_customer_id = customer_id
                org.updated_at = datetime.now(timezone.utc)
                db.add(org)
                await db.commit()

        return customer_id

    async def create_checkout_session(
        self,
        *,
        org_id: UUID,
        org_name: str,
        owner_email: str,
        stripe_price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout Session and return the redirect URL."""
        import asyncio

        stripe = self._stripe()
        customer_id = await self.get_or_create_customer(org_id=org_id, org_name=org_name, email=owner_email)
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"langflow_org_id": str(org_id)},
        )
        return session["url"]

    async def handle_webhook(self, *, payload: bytes, sig_header: str) -> dict[str, Any]:
        """Verify and process a Stripe webhook event.

        Returns a dict describing what was processed (for logging).
        """
        import asyncio

        from langflow_saas.settings import get_saas_settings

        stripe = self._stripe()
        webhook_secret = get_saas_settings().stripe_webhook_secret.get_secret_value()

        event = await asyncio.to_thread(stripe.Webhook.construct_event, payload, sig_header, webhook_secret)

        event_type: str = event["type"]
        handlers = {
            "customer.subscription.created": self._on_subscription_created,
            "customer.subscription.updated": self._on_subscription_updated,
            "customer.subscription.deleted": self._on_subscription_deleted,
            "invoice.payment_failed": self._on_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(event["data"]["object"])
            return {"processed": True, "event_type": event_type}

        return {"processed": False, "event_type": event_type}

    async def _on_subscription_created(self, subscription: dict) -> None:
        await self._upsert_subscription(subscription, status_override=None)

    async def _on_subscription_updated(self, subscription: dict) -> None:
        await self._upsert_subscription(subscription, status_override=None)

    async def _on_subscription_deleted(self, subscription: dict) -> None:
        await self._upsert_subscription(subscription, status_override="canceled")

    async def _on_payment_failed(self, invoice: dict) -> None:
        sub_id = invoice.get("subscription")
        if not sub_id:
            return
        from langflow.services.deps import session_scope
        from sqlmodel import select

        from langflow_saas.models import Subscription, SubscriptionStatus

        async with session_scope() as db:
            result = await db.exec(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
            sub = result.first()
            if sub:
                sub.status = SubscriptionStatus.PAST_DUE
                sub.updated_at = datetime.now(timezone.utc)
                db.add(sub)
                await db.commit()

    async def _upsert_subscription(self, stripe_sub: dict, *, status_override: str | None) -> None:
        """Sync a Stripe subscription object into our DB."""
        from langflow.services.deps import session_scope
        from sqlmodel import select

        from langflow_saas.models import Organization, Plan, Subscription, SubscriptionStatus

        customer_id: str = stripe_sub["customer"]
        stripe_sub_id: str = stripe_sub["id"]
        stripe_price_id: str | None = stripe_sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
        raw_status = status_override or stripe_sub.get("status", "active")

        try:
            stripe_status = SubscriptionStatus(raw_status)
        except ValueError:
            stripe_status = SubscriptionStatus.ACTIVE

        period_start = stripe_sub.get("current_period_start")
        period_end = stripe_sub.get("current_period_end")
        trial_end = stripe_sub.get("trial_end")

        async with session_scope() as db:
            # Find org by Stripe customer_id.
            org_result = await db.exec(select(Organization).where(Organization.stripe_customer_id == customer_id))
            org = org_result.first()
            if not org:
                logger.warning("Stripe webhook: no org found for customer %s", customer_id)
                return

            # Match plan by Stripe price_id.
            plan: Plan | None = None
            if stripe_price_id:
                plan_result = await db.exec(
                    select(Plan).where(
                        (Plan.stripe_monthly_price_id == stripe_price_id)
                        | (Plan.stripe_yearly_price_id == stripe_price_id)
                    )
                )
                plan = plan_result.first()

            sub_result = await db.exec(select(Subscription).where(Subscription.org_id == org.id))
            sub = sub_result.first()

            now = datetime.now(timezone.utc)
            if sub is None:
                sub = Subscription(
                    org_id=org.id,
                    plan_id=plan.id if plan else org.plan_id,  # type: ignore[arg-type]
                )
                db.add(sub)

            sub.stripe_subscription_id = stripe_sub_id
            sub.stripe_price_id = stripe_price_id
            sub.status = stripe_status
            sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc) if period_start else None
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc) if period_end else None
            sub.trial_end = datetime.fromtimestamp(trial_end, tz=timezone.utc) if trial_end else None
            sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
            sub.updated_at = now

            if plan:
                org.plan_id = plan.id
            org.updated_at = now
            db.add(org)
            await db.commit()


_billing_service: BillingService | None = None


def get_billing_service() -> BillingService:
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service
