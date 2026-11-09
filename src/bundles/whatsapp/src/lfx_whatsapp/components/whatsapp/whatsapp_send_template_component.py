"""Configurable WhatsApp component."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from lfx.io import DropdownInput, Output, StrInput

from lfx_whatsapp._client import MAX_TEMPLATE_PARAMETERS, WhatsAppClient
from lfx_whatsapp._components import WhatsAppActionComponent, connection_input, recipient
from lfx_whatsapp._messages import (
    INVALID_BODY_PARAMETERS_MESSAGE,
    INVALID_TEMPLATE_LANGUAGE_MESSAGE,
    INVALID_TEMPLATE_NAME_MESSAGE,
)

if TYPE_CHECKING:
    from lfx.schema.data import Data


MAX_PARAMETER_LENGTH = 1024


class WhatsAppSendTemplateComponent(WhatsAppActionComponent):
    display_name = "WhatsApp: Send Template"
    description = (
        "Send an existing approved template with positional text body parameters. Obtain recipient consent first."
    )
    name = "WhatsAppSendTemplate"
    capability_id = "whatsapp.template.send"
    inputs = [
        connection_input(capability_id, real_time_refresh=True),
        StrInput(
            name="to",
            display_name="Recipient",
            required=True,
            tool_mode=True,
            info="Include the country code. A leading +, spaces, dashes, and parentheses are removed.",
        ),
        DropdownInput(
            name="template_name",
            display_name="Approved Template Name",
            required=True,
            options=[],
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
            tool_mode=True,
            info="Refresh approved templates from this connection's WABA, or enter a name supplied dynamically.",
        ),
        DropdownInput(
            name="language",
            display_name="Template Language",
            value="en_US",
            required=True,
            options=[],
            real_time_refresh=True,
            combobox=True,
            tool_mode=True,
            info="Use the selected template's language, such as en_US or pt_BR, rather than a country code.",
        ),
        StrInput(
            name="body_parameters",
            display_name="Positional Body Parameters",
            is_list=True,
            value=[],
            tool_mode=True,
            info="Enter positional text body parameters in their template order.",
        ),
    ]
    outputs = [Output(display_name="Accepted Message", name="message", method="build_message")]

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name not in {"connection", "template_name", "language"}:
            return build_config
        name = field_value if field_name == "template_name" else (self.template_name or "")
        language = field_value if field_name == "language" else (self.language or "")
        if field_name == "connection":
            self.connection = field_value
        if not self.connection:
            build_config["template_name"]["options"] = []
            build_config["template_name"]["options_metadata"] = []
            build_config["language"]["options"] = []
            return build_config

        metadata = build_config["template_name"].get("options_metadata", [])
        if field_name != "language":
            async with WhatsAppClient(self.resolve_connection("connection")) as client:
                templates = await client.approved_templates()
            grouped: dict[str, dict[str, int | None]] = {}
            for template in templates:
                grouped.setdefault(template.name, {})[template.language] = template.body_parameters
            names = sorted(grouped)
            metadata = [{"name": item, "languages": grouped[item]} for item in names]
            build_config["template_name"]["options"] = names
            build_config["template_name"]["options_metadata"] = metadata
            if not name and names:
                name = names[0]

        selected = next((item for item in metadata if item.get("name") == name), {})
        counts = selected.get("languages", {})
        languages = sorted(counts)
        if languages and language not in languages:
            language = languages[0]
        build_config["template_name"]["value"] = name
        build_config["language"]["options"] = languages
        build_config["language"]["value"] = language
        count = counts.get(language)
        info = "Enter positional text body parameters in their template order."
        if type(count) is int:
            info = f"This approved template expects {count} positional text body parameters, in template order."
        elif language in counts:
            info = "This template does not have a supported positional text body. Choose another approved template."
        build_config["body_parameters"]["info"] = info
        return build_config

    async def build_message(self) -> Data:
        if not re.fullmatch(r"[a-z0-9_]{1,512}", self.template_name or ""):
            raise ValueError(INVALID_TEMPLATE_NAME_MESSAGE)
        if not re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", self.language or ""):
            raise ValueError(INVALID_TEMPLATE_LANGUAGE_MESSAGE)
        values = self.body_parameters or []
        if (
            not isinstance(values, list)
            or len(values) > MAX_TEMPLATE_PARAMETERS
            or any(not isinstance(value, str) or not value or len(value) > MAX_PARAMETER_LENGTH for value in values)
        ):
            raise ValueError(INVALID_BODY_PARAMETERS_MESSAGE)
        template = {"name": self.template_name, "language": {"code": self.language}}
        if values:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": value} for value in values]}
            ]
        return await self.send(
            {"messaging_product": "whatsapp", "to": recipient(self.to), "type": "template", "template": template}
        )
