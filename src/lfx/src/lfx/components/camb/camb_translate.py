"""CAMB.AI Translation component for Langflow."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from ._helpers import get_async_client


class CambTranslateComponent(Component):
    display_name = "CAMB AI Translate"
    description = "Translate text between 140+ languages using CAMB.AI."
    icon = "camb-ai"
    name = "CambTranslate"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="CAMB API Key",
            info="Your CAMB.AI API key.",
            required=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Text",
            info="The text to translate.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="source_language",
            display_name="Source Language",
            info="Source language code (integer). 1=English, 2=Spanish, 3=French, etc.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="target_language",
            display_name="Target Language",
            info="Target language code (integer). 1=English, 2=Spanish, 3=French, etc.",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="formality",
            display_name="Formality",
            info="Optional formality level: 1=formal, 2=informal.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Translated Text", name="translated_output", method="translate_text"),
    ]

    def translate_text(self) -> Data:
        return asyncio.run(self._translate_async())

    async def _translate_async(self) -> Data:
        from camb.core.api_error import ApiError

        client = get_async_client(self.api_key)

        kwargs: dict[str, Any] = {
            "text": self.text,
            "source_language": self.source_language,
            "target_language": self.target_language,
        }
        if self.formality:
            kwargs["formality"] = self.formality

        try:
            result = await client.translation.translation_stream(**kwargs)
            translated = str(result) if result else ""
        except ApiError as e:
            # The CAMB SDK sometimes raises ApiError with status 200 when
            # the response body is the translated text itself (SDK quirk).
            if e.status_code == 200 and e.body:
                translated = str(e.body)
            else:
                raise

        if not translated:
            return Data(data={"error": "Translation returned empty result"})

        self.status = translated
        return Data(data={"translated_text": translated})
