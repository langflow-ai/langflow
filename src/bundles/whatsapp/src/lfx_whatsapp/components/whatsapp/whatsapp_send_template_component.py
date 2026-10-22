"""Configurable WhatsApp component."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lfx.io import Output, StrInput

from lfx_whatsapp._components import WhatsAppActionComponent, connection_input, recipient

if TYPE_CHECKING:
    from lfx.schema.data import Data


MAX_PARAMETERS = 100
MAX_PARAMETER_LENGTH = 1024


class WhatsAppSendTemplateComponent(WhatsAppActionComponent):
    display_name = "WhatsApp Send Template"
    description = (
        "Send an existing approved template with positional text body parameters. Obtain recipient consent first."
    )
    name = "WhatsAppSendTemplate"
    capability_id = "whatsapp.template.send"
    inputs = [
        connection_input(capability_id),
        StrInput(name="to", display_name="Recipient", required=True),
        StrInput(name="template_name", display_name="Approved Template Name", required=True),
        StrInput(name="language", display_name="Language Code", value="en_US", required=True),
        StrInput(name="body_parameters", display_name="Positional Body Parameters", is_list=True, value=[]),
    ]
    outputs = [Output(display_name="Accepted Message", name="message", method="build_message")]

    async def build_message(self) -> Data:
        if not re.fullmatch(r"[a-z0-9_]{1,512}", self.template_name or "") or not re.fullmatch(
            r"[a-z]{2,3}(?:_[A-Z]{2})?", self.language or ""
        ):
            msg = "Use a valid approved template name and language code."
            raise ValueError(msg)
        values = self.body_parameters or []
        if (
            not isinstance(values, list)
            or len(values) > MAX_PARAMETERS
            or any(not isinstance(value, str) or not value or len(value) > MAX_PARAMETER_LENGTH for value in values)
        ):
            msg = "Provide at most 100 nonempty text body parameters of at most 1024 characters."
            raise ValueError(msg)
        template = {"name": self.template_name, "language": {"code": self.language}}
        if values:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": value} for value in values]}
            ]
        return await self.send(
            {"messaging_product": "whatsapp", "to": recipient(self.to), "type": "template", "template": template}
        )
