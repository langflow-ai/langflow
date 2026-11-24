"""Get a Firma signing request with its status and recipients."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.firma.firma_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    FirmaAPIError,
    derive_status,
    firma_request,
    path_id,
    text_value,
)


def _summary(signing_request: dict[str, Any], request_id: str, status: str, recipients: list[Any]) -> str:
    """Describe the request status and each recipient's progress."""
    actors = [item for item in recipients if isinstance(item, dict) and item.get("designation") != "CC"]
    done = [item for item in actors if item.get("finished_on")]
    lines = [
        f"Signing request {signing_request.get('name') or request_id} ({request_id}) is {status}. "
        f"{len(done)} of {len(actors)} signers and approvers have finished."
    ]
    for item in recipients:
        if not isinstance(item, dict):
            continue
        if item.get("designation") == "CC":
            state = "copy only"
        elif item.get("declined_on"):
            state = "declined"
        elif item.get("finished_on"):
            state = "finished"
        else:
            state = "pending"
        lines.append(
            f"- {item.get('name') or item.get('email')} <{item.get('email')}> {item.get('designation')} {state}"
        )
    return "\n".join(lines)


class FirmaGetSigningRequestComponent(Component):
    """Read one signing request and its recipients from Firma."""

    display_name = "Firma Get Signing Request"
    description = "Get a Firma signing request's status, settings and recipients, including who has signed."
    documentation = DOCUMENTATION_URL
    icon = "Firma"
    name = "FirmaGetSigningRequest"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firma API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="signing_request_id",
            display_name="Signing Request ID",
            info="The ID of the signing request.",
            required=True,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Firma to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Signing Request", name="signing_request", method="get_signing_request"),
    ]

    def get_signing_request(self) -> Data:
        """Return the request as one ``Data`` with a one-word ``status`` and the ``recipients`` list."""
        timeout = float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
        try:
            request_path = path_id(self.signing_request_id, "signing request ID")
            signing_request = firma_request(
                "GET", f"/signing-requests/{request_path}", api_key=self.api_key, timeout=timeout
            )
            users = firma_request(
                "GET", f"/signing-requests/{request_path}/users", api_key=self.api_key, timeout=timeout
            )
        except FirmaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        request_id = str(signing_request.get("id") or text_value(self.signing_request_id))
        recipients = users.get("results") if isinstance(users.get("results"), list) else []
        status = derive_status(signing_request)
        data = Data(
            text=_summary(signing_request, request_id, status, recipients),
            data={
                "signing_request_id": request_id,
                "status": status,
                "signing_request": signing_request,
                "recipients": recipients,
            },
        )
        self.status = data
        return data
