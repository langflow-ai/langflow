"""Create and send a Firma signing request from a template."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.firma.firma_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    FirmaAPIError,
    build_recipients,
    common_send_inputs,
    create_and_send,
    error_data,
    firma_request,
    fit_recipients_to_template,
    path_id,
    send_options,
    send_result,
    send_summary,
    text_value,
)


class FirmaSendTemplateComponent(Component):
    """Create a signing request from a Firma template and send it in one call."""

    display_name = "Firma Send Template for Signature"
    description = "Create a signing request from a Firma template and send it to the recipients for e-signature."
    documentation = DOCUMENTATION_URL
    icon = "Firma"
    name = "FirmaSendTemplate"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firma API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="template_id",
            display_name="Template ID",
            info="The ID of the Firma template to send.",
            required=True,
            tool_mode=True,
        ),
        *common_send_inputs(template=True),
    ]

    outputs = [
        Output(display_name="Signing Request", name="signing_request", method="send_request"),
    ]

    def send_request(self) -> Data:
        """Return the created request as one ``Data`` with its id and status.

        The first signer's signing link is included only with ``include_signing_link`` on, or when Firma
        emailed nobody.
        """
        timeout = float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
        try:
            template_id = text_value(self.template_id)
            template_path = path_id(template_id, "template ID")
            recipients = build_recipients(
                first_name=self.signer_first_name,
                last_name=self.signer_last_name,
                email=self.signer_email,
                recipients_json=self.recipients_json,
                required=False,
                default_order=False,
                require_signer=False,
            )
            options = send_options(self)
            name = text_value(self.request_name)
            if recipients or not name:
                # One read gives the default name (the API requires one) and the template users the
                # recipients must cover: create-and-send needs a recipient for every one of them.
                template = firma_request("GET", f"/templates/{template_path}", api_key=self.api_key, timeout=timeout)
                name = name or text_value(template.get("name")) or "Signing request"
                if recipients:
                    single_signer = bool(text_value(self.signer_first_name) or text_value(self.signer_email))
                    recipients = fit_recipients_to_template(template, recipients, single_signer=single_signer)
            body: dict[str, Any] = {"template_id": template_id, "name": name}
            if recipients:
                body["recipients"] = recipients
            body.update(options)
            response = create_and_send(self.api_key, timeout, body)
        except FirmaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return error_data(exc)

        result = send_result(response, include_signing_link=bool(self.include_signing_link))
        data = Data(text=send_summary(result), data=result)
        self.status = data
        return data
