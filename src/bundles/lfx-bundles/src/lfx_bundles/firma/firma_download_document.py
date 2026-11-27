"""Get the download link of a Firma signing request's signed document."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.firma.firma_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    FirmaAPIError,
    firma_request,
    path_id,
    text_value,
)

HTTP_CONFLICT = 409
NOT_READY_HINT = (
    "There is no document yet: the request was never sent, or it has just finished and its completion "
    "certificate is still being generated. In the second case, retry in a minute."
)


class FirmaDownloadSignedDocumentComponent(Component):
    """Return a temporary download link for the signed PDF of a signing request."""

    display_name = "Firma Download Signed Document"
    description = (
        "Get a temporary download link for a Firma signing request's signed PDF with its completion certificate."
    )
    documentation = DOCUMENTATION_URL
    icon = "Firma"
    name = "FirmaDownloadSignedDocument"

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
        Output(display_name="Download", name="download", method="get_download"),
    ]

    def get_download(self) -> Data:
        """Return one ``Data`` with the ``download_url`` as ``text`` and its expiry."""
        try:
            request_path = path_id(self.signing_request_id, "signing request ID")
            try:
                body = firma_request(
                    "GET",
                    f"/signing-requests/{request_path}/download",
                    api_key=self.api_key,
                    timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                )
            except FirmaAPIError as exc:
                if exc.status == HTTP_CONFLICT:
                    msg = f"{exc} {NOT_READY_HINT}"
                    raise FirmaAPIError(msg, status=exc.status, code=exc.code) from exc
                raise
        except FirmaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        download = Data(
            text=str(body.get("download_url") or ""),
            data={"signing_request_id": text_value(self.signing_request_id), **body},
        )
        self.status = download
        return download
