"""Send a PDF or DOCX document for e-signature with Firma."""

from __future__ import annotations

import base64
import binascii
from pathlib import PurePath
from typing import Any

from lfx.base.data.storage_utils import get_file_size, read_file_bytes
from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.utils.async_helpers import run_until_complete
from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access

from lfx_bundles.firma.firma_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    DOCX_TYPE,
    INLINE_DOCUMENT_MAX_BYTES,
    PDF_TYPE,
    UPLOAD_MAX_BYTES,
    FirmaAPIError,
    build_recipients,
    common_send_inputs,
    create_and_send,
    error_data,
    firma_request,
    json_list,
    optional_int,
    send_options,
    send_result,
    send_summary,
    text_value,
    upload_document,
)

# Default signature boxes, in percent of the page: three per row along the
# bottom of the chosen page, further rows stacked upward.
FIELD_WIDTH = 28
FIELD_HEIGHT = 8
FIELD_COLUMNS = (5, 36, 67)
FIELD_BOTTOM_Y = 86
FIELD_ROW_STEP = 10

FIELDS_INFO = (
    "A JSON array of fields that replaces the default signature boxes. Positions are percentages of the page, "
    'for example [{"type": "signature", "recipient_id": "temp_1", "page_number": 1, '
    '"position": {"x": 5, "y": 86, "width": 28, "height": 8}}]. Recipients are temp_1, temp_2, ... in list order.'
)
ANCHOR_TAGS_INFO = (
    "A JSON array of anchor tags that places fields on text found in the document, for example "
    '[{"anchor_string": "Sign here", "type": "signature", "recipient_id": "temp_1"}].'
)


def _content_type(data: bytes, file_name: str) -> str:
    """Return the content type of a PDF or DOCX document, from its name or its first bytes."""
    extension = PurePath(file_name).suffix.lower()
    if extension == ".pdf" or (not extension and data.startswith(b"%PDF")):
        return PDF_TYPE
    if extension == ".docx" or (not extension and data.startswith(b"PK\x03\x04")):
        return DOCX_TYPE
    msg = "The document must be a PDF or DOCX file."
    raise FirmaAPIError(msg)


def default_fields(signer_ids: list[str], page: int) -> list[dict[str, Any]]:
    """Place one signature box per signer along the bottom of the page."""
    fields = []
    for index, recipient_id in enumerate(signer_ids):
        row, column = divmod(index, len(FIELD_COLUMNS))
        y = FIELD_BOTTOM_Y - row * FIELD_ROW_STEP
        if y < 0:
            msg = "Too many signers for the default placement. Use Signature Anchor Text, Fields or Anchor Tags."
            raise FirmaAPIError(msg)
        fields.append(
            {
                "type": "signature",
                "recipient_id": recipient_id,
                "page_number": page,
                "position": {"x": FIELD_COLUMNS[column], "y": y, "width": FIELD_WIDTH, "height": FIELD_HEIGHT},
                "required": True,
            }
        )
    return fields


def anchor_fields(signer_ids: list[str], anchor: str) -> list[dict[str, Any]]:
    """Place one signature field per signer on the anchor text; ``{n}`` becomes the signer number."""
    if len(signer_ids) > 1 and "{n}" not in anchor:
        msg = (
            "With several signers the signature anchor text must contain {n}, which becomes the signer "
            "number (1, 2, ...), for example {{sign_{n}}}."
        )
        raise FirmaAPIError(msg)
    return [
        {"anchor_string": anchor.replace("{n}", str(number)), "type": "signature", "recipient_id": recipient_id}
        for number, recipient_id in enumerate(signer_ids, start=1)
    ]


class FirmaSendDocumentComponent(Component):
    """Upload a document to Firma and send it for signature in one flow step.

    Documents up to 4 MiB travel inline as base64; larger ones (up to 50 MB) go
    through the ``POST /documents`` pre-signed upload first, because the API
    refuses request bodies over 6 MiB.
    """

    display_name = "Firma Send Document for Signature"
    description = (
        "Send a PDF or DOCX document to recipients for e-signature with Firma, with signature fields placed "
        "on anchor text or in default boxes."
    )
    documentation = DOCUMENTATION_URL
    icon = "Firma"
    name = "FirmaSendDocument"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firma API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        FileInput(
            name="document_file",
            display_name="Document",
            info="The PDF or DOCX document to send, up to 50 MB.",
            file_types=["pdf", "docx"],
        ),
        MultilineInput(
            name="document_base64",
            display_name="Document (Base64)",
            info="The document as base64 text, used when no file is attached. A data: URL prefix is accepted.",
            advanced=True,
        ),
        MessageTextInput(
            name="document_file_name",
            display_name="Document File Name",
            info="The file name for a base64 document, such as contract.pdf. Its extension sets the file type.",
            advanced=True,
        ),
        *common_send_inputs(),
        MessageTextInput(
            name="signature_anchor",
            display_name="Signature Anchor Text",
            info=(
                "Text in the document where each signer's signature goes. With several signers, {n} becomes the "
                "signer number, for example {{sign_{n}}}. Empty places default boxes at the bottom of a page."
            ),
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="signature_page",
            display_name="Signature Page",
            info="The page that gets the default signature boxes when no anchor text is set.",
            value=1,
            advanced=True,
        ),
        MultilineInput(
            name="fields_json",
            display_name="Fields (JSON)",
            info=FIELDS_INFO,
            advanced=True,
        ),
        MultilineInput(
            name="anchor_tags_json",
            display_name="Anchor Tags (JSON)",
            info=ANCHOR_TAGS_INFO,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Signing Request", name="signing_request", method="send_document"),
    ]

    def _confine_local_path(self, path: str) -> str:
        """Confine a tenant-controlled local path to this component's storage scope."""
        return str(enforce_local_file_access(path, scope_ids=component_file_access_scopes(self)))

    def _read_document(self) -> tuple[bytes, str]:
        """Return the document bytes and file name from the attached file or the base64 input."""
        file_path = text_value(self.document_file)
        if file_path:
            try:
                # Check the size first, so a file over the limit is never read into memory.
                too_large = get_file_size(file_path) > UPLOAD_MAX_BYTES
                if not too_large:
                    data = run_until_complete(read_file_bytes(file_path, resolve_path=self._confine_local_path))
            except (OSError, ValueError, RuntimeError) as exc:
                msg = f"Could not read the document file: {exc}"
                raise FirmaAPIError(msg) from exc
            if too_large:
                msg = "The document is larger than the 50 MB limit."
                raise FirmaAPIError(msg)
            return data, PurePath(file_path).name

        encoded = text_value(self.document_base64)
        if not encoded:
            msg = "Attach a PDF or DOCX file, or enter the document as base64."
            raise FirmaAPIError(msg)
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        try:
            data = base64.b64decode("".join(encoded.split()), validate=True)
        except (binascii.Error, ValueError) as exc:
            msg = "Document (Base64) is not valid base64."
            raise FirmaAPIError(msg) from exc
        return data, text_value(self.document_file_name)

    def _placement(self, signer_ids: list[str]) -> dict[str, Any]:
        """Return the fields and anchor tags of the request body."""
        fields = json_list(self.fields_json, "Fields (JSON)")
        anchor_tags = json_list(self.anchor_tags_json, "Anchor Tags (JSON)")
        if fields is None and anchor_tags is None:
            anchor = text_value(self.signature_anchor)
            if anchor:
                anchor_tags = anchor_fields(signer_ids, anchor)
            else:
                page = optional_int(self.signature_page, "Signature Page", minimum=1) or 1
                fields = default_fields(signer_ids, page)
        placement: dict[str, Any] = {}
        if fields is not None:
            placement["fields"] = fields
        if anchor_tags is not None:
            placement["anchor_tags"] = anchor_tags
        return placement

    def send_document(self) -> Data:
        """Return the created request as one ``Data`` with its id and status.

        The first signer's signing link is included only with ``include_signing_link`` on, or when Firma
        emailed nobody.
        """
        timeout = float(self.timeout or DEFAULT_TIMEOUT_SECONDS)
        try:
            recipients = build_recipients(
                first_name=self.signer_first_name,
                last_name=self.signer_last_name,
                email=self.signer_email,
                recipients_json=self.recipients_json,
                required=True,
                temp_ids=True,
            )
            signer_ids = [item["id"] for item in recipients or [] if item["designation"] == "Signer"]
            placement = self._placement(signer_ids)
            options = send_options(self)

            data, file_name = self._read_document()
            if not data:
                msg = "The document is empty."
                raise FirmaAPIError(msg)
            if len(data) > UPLOAD_MAX_BYTES:
                msg = "The document is larger than the 50 MB limit."
                raise FirmaAPIError(msg)
            content_type = _content_type(data, file_name)
            if not PurePath(file_name).suffix:
                file_name = f"{file_name or 'document'}.{'pdf' if content_type == PDF_TYPE else 'docx'}"

            body: dict[str, Any] = {"name": text_value(self.request_name) or PurePath(file_name).stem}
            if len(data) <= INLINE_DOCUMENT_MAX_BYTES:
                body["document"] = base64.b64encode(data).decode("ascii")
            else:
                upload = firma_request(
                    "POST",
                    "/documents",
                    api_key=self.api_key,
                    timeout=timeout,
                    json={"file_name": file_name, "file_size": len(data), "content_type": content_type},
                )
                if not upload.get("upload_url") or not upload.get("document_id"):
                    msg = "Firma API did not return an upload URL for the document."
                    raise FirmaAPIError(msg)
                upload_document(str(upload["upload_url"]), data, content_type)
                body["document_id"] = upload["document_id"]
            body["recipients"] = recipients
            body.update(placement)
            body.update(options)

            response = create_and_send(self.api_key, timeout, body)
        except FirmaAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return error_data(exc)

        result = send_result(response, include_signing_link=bool(self.include_signing_link))
        request = Data(text=send_summary(result), data=result)
        self.status = request
        return request
