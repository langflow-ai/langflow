"""Binary screenshots stored through Langflow's configured file service."""

import asyncio
from uuid import uuid4

from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, IntInput
from lfx.schema.data import Data
from lfx.services.deps import get_storage_service
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, FastAFError, integer_option, public_url
from lfx_fastaf._inputs import api_key_input, choice_input, optional_int, url_input


class FastAFScreenshotComponent(FastAFBaseComponent):
    display_name = "FastAF Capture Screenshot"
    description = "Capture a public page for 5 credits and save the image through Langflow's file service."
    name = "FastAFScreenshot"
    endpoint = "screenshot"
    inputs = [
        api_key_input(),
        url_input(),
        BoolInput(
            name="full_page",
            display_name="Full Page",
            value=False,
            info="Capture the full scrollable page rather than the viewport; no surcharge.",
        ),
        optional_int("width", "Viewport Width (px)", "Width in CSS pixels, at least 1."),
        optional_int("height", "Viewport Height (px)", "Height in CSS pixels, at least 1."),
        choice_input("format", "Image Format", ["png", "jpg", "webp"], "png", "Image encoding."),
        IntInput(
            name="quality",
            display_name="Quality",
            value=80,
            advanced=True,
            range_spec=RangeSpec(min=0, max=100, step=1, step_type="int"),
            info="JPG/WebP quality, 0-100. PNG is lossless.",
        ),
        choice_input(
            "wait_until",
            "Capture Readiness",
            ["domcontentloaded", "load", "networkidle"],
            "domcontentloaded",
            "Capture after DOM parsing, load or network idle.",
            advanced=True,
        ),
    ]
    outputs = [Output(display_name="Image File", name="data", method="fastaf_screenshot")]

    def request_body(self) -> dict:
        if self.format not in {"png", "jpg", "webp"}:
            msg = "Unsupported screenshot image format."
            raise FastAFError(msg)
        if self.wait_until not in {"domcontentloaded", "load", "networkidle"}:
            msg = "Unsupported capture readiness."
            raise FastAFError(msg)
        width = integer_option(self.width, "Viewport Width", 1)
        height = integer_option(self.height, "Viewport Height", 1)
        return {
            "url": public_url(self.url),
            "fullPage": self.full_page,
            "width": str(width) if width is not None else None,
            "height": str(height) if height is not None else None,
            "format": self.format,
            "quality": integer_option(self.quality, "Quality", 0, 100),
            "wait_until": self.wait_until,
        }

    async def fastaf_screenshot(self) -> Data:
        try:
            storage = get_storage_service()
            content, content_type = await asyncio.to_thread(self._request, binary=True)
            signatures = {
                "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
                "jpg": content.startswith(b"\xff\xd8\xff"),
                "webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
            }
            expected_type = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[self.format]
            if not signatures[self.format] or content_type != expected_type:
                msg = "FastAF returned an unexpected screenshot response instead of the requested image."
                raise FastAFError(msg)
            namespace = str(self.graph.flow_id) if self.graph and self.graph.flow_id else str(uuid4())
            filename = f"fastaf-{uuid4()}.{self.format}"
            await storage.save_file(namespace, filename, content)
            file_path = storage.resolve_component_path(f"{namespace}/{filename}")
            result = Data(
                data={
                    "file_path": file_path,
                    "content_type": content_type,
                    "bytes": len(content),
                    **self.last_request,
                }
            )
        except FastAFError as error:
            return self.error_data(str(error))
        except (OSError, ValueError):
            return self.error_data("Screenshot storage failed; the API call may already have consumed credits.")
        self.status = result
        return result
