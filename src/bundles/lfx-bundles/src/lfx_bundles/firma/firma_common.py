"""Shared HTTP plumbing for the Firma components.

Firma is an electronic signature API. Every component calls the fixed host
``https://api.firma.dev`` with the API key in the ``Authorization`` header (the
raw key, without a ``Bearer`` prefix). Errors come back as
``{"error": "...", "code": "...", "errors": [...]}``. Document uploads and
downloads use pre-signed storage URLs returned by the API; those requests never
carry the Firma API key.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, MultilineInput
from lfx.schema.data import Data

API_BASE_URL = "https://api.firma.dev/functions/v1/signing-request-api"
DOCUMENTATION_URL = "https://docs.firma.dev"
DEFAULT_TIMEOUT_SECONDS = 60.0
UPLOAD_TIMEOUT_SECONDS = 300.0

API_KEY_INFO = "Your Firma API key. Find it in Firma under Workspace Settings > API."  # pragma: allowlist secret

# The API refuses request bodies over 6,291,456 bytes (413 REQUEST_TOO_LARGE).
# Base64 grows a file by a third, so files up to 4 MiB travel inline and larger
# ones use the POST /documents pre-signed upload.
INLINE_DOCUMENT_MAX_BYTES = 4 * 1024 * 1024
UPLOAD_MAX_BYTES = 50 * 1024 * 1024

PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

DESIGNATIONS = {"signer": "Signer", "approver": "Approver", "cc": "CC"}
DEFAULT_LANGUAGE = "Workspace default"
LANGUAGES = ["en", "es", "it", "pt", "fr", "de", "el", "ru", "pl", "cs", "sv", "nl", "ro", "nb", "ca"]
LANGUAGE_OPTIONS = [DEFAULT_LANGUAGE, *LANGUAGES]
REQUEST_STATUSES = ["not_sent", "in_progress", "finished", "cancelled", "declined", "expired", "deleted"]
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200

# Codes of failures that carry no HTTP answer from Firma.
NETWORK_ERROR = "NETWORK_ERROR"
INVALID_RESPONSE = "INVALID_RESPONSE"

# Upper bound on the response text echoed into an error message.
_ERROR_DETAIL_LIMIT = 300
_STATUS_LABELS = {
    401: "Firma rejected the API key (401)",
    403: "Firma refused the request (403)",
    404: "Firma could not find the resource (404)",
    429: "Firma rate limit exceeded (429)",
}


class FirmaAPIError(Exception):
    """A Firma request failed; the message is safe to show in the component output."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        has_firma_body: bool = False,
        signing_request_id: str | None = None,
        may_have_been_sent: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        # True when the body was Firma's own error shape ``{"error": ..., "code": ...}``. Gateway errors
        # (504, 546, ``{"code", "message"}``) do not have it.
        self.has_firma_body = has_firma_body
        # A create-and-send 409 names the signing request it kept (ALREADY_SENT, SEND_EFFECTS_EXIST).
        self.signing_request_id = signing_request_id
        # Set by ``send_failure`` when a create-and-send failure does not prove that nothing was sent.
        self.may_have_been_sent = may_have_been_sent


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def text_value(value: Any) -> str:
    """Return an input value as a stripped string (empty when unset)."""
    if value is None:
        return ""
    if hasattr(value, "text") and not isinstance(value, str):
        value = value.text
    return str(value).strip()


def path_id(value: Any, label: str) -> str:
    """Return a non-empty identifier, escaped for use as one URL path segment."""
    identifier = text_value(value)
    if not identifier:
        msg = f"Enter the {label}."
        raise FirmaAPIError(msg)
    return quote(identifier, safe="")


def optional_int(value: Any, label: str, *, minimum: int, maximum: int | None = None) -> int | None:
    """Return a whole number within bounds, or ``None`` when the input is empty or zero."""
    if value in (None, "", 0):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float("nan")
    if not number.is_integer():
        msg = f"{label} must be a whole number; got {value!r}."
        raise FirmaAPIError(msg)
    result = int(number)
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"from {minimum} to {maximum}" if maximum is not None else f"at least {minimum}"
        msg = f"{label} must be {bound}; got {result}."
        raise FirmaAPIError(msg)
    return result


def json_list(value: Any, label: str) -> list[Any] | None:
    """Parse a JSON array input; ``None`` when the input is empty."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    raw = text_value(value)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    if not isinstance(parsed, list):
        msg = f"{label} must be a JSON array."
        raise FirmaAPIError(msg)
    return parsed


def language_value(value: Any) -> str | None:
    """Return a supported language code, or ``None`` for the workspace default."""
    language = text_value(value).lower()
    if not language or language == DEFAULT_LANGUAGE.lower():
        return None
    if language not in LANGUAGES:
        msg = f"Choose a language from: {', '.join(LANGUAGES)}; got {language!r}."
        raise FirmaAPIError(msg)
    return language


def build_recipients(
    *,
    first_name: Any,
    last_name: Any,
    email: Any,
    recipients_json: Any,
    required: bool,
    temp_ids: bool = False,
) -> list[dict[str, Any]] | None:
    """Build the recipients list from the single signer inputs or the JSON array.

    Each recipient gets a designation (default Signer) and an order (default its
    position, starting at 1). Document-based requests also get temporary ids
    (``temp_1``, ``temp_2``, ...) that fields and anchor tags refer to.
    """
    has_simple = bool(text_value(first_name) or text_value(email))
    entries = json_list(recipients_json, "Recipients (JSON)")
    if has_simple and entries is not None:
        msg = "Use either the signer inputs or Recipients (JSON), not both."
        raise FirmaAPIError(msg)

    if has_simple:
        if not text_value(first_name) or not text_value(email):
            msg = "Enter the signer's first name and email."
            raise FirmaAPIError(msg)
        recipient: dict[str, Any] = {"first_name": text_value(first_name), "email": text_value(email)}
        if text_value(last_name):
            recipient["last_name"] = text_value(last_name)
        entries = [recipient]
    elif entries is None or not entries:
        if required or entries is not None:
            msg = "Enter the signer's first name and email, or a Recipients (JSON) array."
            raise FirmaAPIError(msg)
        return None

    recipients: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            msg = f"Recipient {index} must be a JSON object."
            raise FirmaAPIError(msg)
        item = dict(entry)
        if not text_value(item.get("first_name")) or not text_value(item.get("email")):
            msg = f"Recipient {index} needs first_name and email."
            raise FirmaAPIError(msg)
        designation = text_value(item.get("designation")) or "Signer"
        if designation.lower() not in DESIGNATIONS:
            msg = f"Recipient {index}: designation must be Signer, Approver or CC."
            raise FirmaAPIError(msg)
        item["designation"] = DESIGNATIONS[designation.lower()]
        if item.get("order") in (None, ""):
            item["order"] = index
        if temp_ids and not item.get("id"):
            item["id"] = f"temp_{index}"
        recipients.append(item)

    if not any(item["designation"] == "Signer" for item in recipients):
        msg = "At least one recipient must be a Signer."
        raise FirmaAPIError(msg)
    return recipients


def derive_status(signing_request: dict[str, Any]) -> str:
    """Return the status of a signing request as one word.

    List results carry it as a string; a single request carries flags
    (``sent``, ``finished``, ``cancelled``, ``declined``, ``expired``).
    """
    status = signing_request.get("status")
    if isinstance(status, str):
        return status
    if isinstance(status, dict):
        for name in ("finished", "cancelled", "declined", "expired"):
            if status.get(name):
                return name
        return "in_progress" if status.get("sent") else "not_sent"
    return "unknown"


def send_result(response: dict[str, Any]) -> dict[str, Any]:
    """Flatten a create-and-send response into the fields a flow usually needs."""
    signer = response.get("first_signer") if isinstance(response.get("first_signer"), dict) else {}
    return {
        "signing_request_id": response.get("id"),
        "name": response.get("name"),
        "status": response.get("status"),
        "signing_link": signer.get("signing_link"),
        "first_signer": signer or None,
        "warnings": response.get("warnings") or [],
        "signing_request": response,
    }


RECIPIENTS_INFO = (
    "A JSON array of recipients, used instead of the signer inputs. Each item has first_name and email, and "
    "optionally last_name, designation (Signer, Approver or CC) and order. Example: "
    '[{"first_name": "Ada", "email": "ada@example.com"}].'
)
TEMPLATE_RECIPIENTS_INFO = (
    f"{RECIPIENTS_INFO} With a template, an item can also carry template_user_id. Every role of the template "
    "(each user who signs or approves) needs one recipient, matched by template_user_id, then by order, and "
    "keeps its own designation and order; a list that misses a role is refused before anything is created. "
    "Empty, with empty signer inputs, uses the template's own recipients."
)
SIGNER_FIRST_NAME_INFO = "First name of the single signer. Leave empty when Recipients (JSON) is used."
TEMPLATE_SIGNER_FIRST_NAME_INFO = (
    "First name of the single signer, who takes the template's one role that signs or approves (its "
    "template_user_id, order and designation). A template with several such roles is refused before anything "
    "is created; Recipients (JSON) covers those. Leave empty when Recipients (JSON) is used."
)


def send_summary(result: dict[str, Any]) -> str:
    """Describe a created signing request in a few sentences.

    The first signer is said to be notified only when the request's ``send_signing_email`` setting is on.
    """
    parts = [f"Signing request {result['signing_request_id']} was created with status {result['status']}."]
    signer = result.get("first_signer") or {}
    settings = (result.get("signing_request") or {}).get("settings") or {}
    if signer.get("email"):
        who = f"{signer.get('name') or signer['email']} ({signer['email']})"
        if settings.get("send_signing_email") is False:
            parts.append(
                "No invitation email was sent (the request's send_signing_email setting is off); "
                f"the first signer, {who}, signs through the signing link."
            )
        else:
            parts.append(f"The first signer, {who}, was notified.")
    if result.get("signing_link"):
        parts.append(f"First signer's signing link: {result['signing_link']}")
    if result.get("warnings"):
        parts.append("Warnings: " + "; ".join(str(warning) for warning in result["warnings"]))
    return " ".join(parts)


def common_send_inputs(*, template: bool = False) -> list:
    """Inputs shared by the two send components, after their document or template input."""
    return [
        MessageTextInput(
            name="request_name",
            display_name="Request Name",
            info="The signing request name shown to recipients.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="signer_first_name",
            display_name="Signer First Name",
            info=TEMPLATE_SIGNER_FIRST_NAME_INFO if template else SIGNER_FIRST_NAME_INFO,
            tool_mode=True,
        ),
        MessageTextInput(
            name="signer_last_name",
            display_name="Signer Last Name",
            info="Last name of the single signer.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="signer_email",
            display_name="Signer Email",
            info="Email address of the single signer. Firma sends the signing invitation to it.",
            tool_mode=True,
        ),
        MultilineInput(
            name="recipients_json",
            display_name="Recipients (JSON)",
            info=TEMPLATE_RECIPIENTS_INFO if template else RECIPIENTS_INFO,
            advanced=True,
        ),
        MultilineInput(
            name="message",
            display_name="Message to Recipients",
            info="The signing request description, shown to recipients.",
            advanced=True,
            tool_mode=True,
        ),
        IntInput(
            name="expiration_hours",
            display_name="Expiration (hours)",
            info="Hours until the request expires. 0 keeps the workspace or template default.",
            value=0,
            advanced=True,
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            info="The language of the signing page and emails.",
            options=LANGUAGE_OPTIONS,
            value=DEFAULT_LANGUAGE,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Firma to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]


def send_options(component: Any) -> dict[str, Any]:
    """Return the optional description, expiration and language of a create-and-send body."""
    body: dict[str, Any] = {}
    expiration = optional_int(component.expiration_hours, "Expiration (hours)", minimum=1)
    if expiration is not None:
        body["expiration_hours"] = expiration
    message = text_value(component.message)
    if message:
        body["description"] = message
    language = language_value(component.language)
    if language:
        body["language"] = language
    return body


def list_page(component: Any, path: str, filters: dict[str, Any]) -> list[Data]:
    """GET one page of a list endpoint, newest first, and return one ``Data`` per result."""
    params: dict[str, Any] = {
        "page": max(int(component.page or 1), 1),
        "page_size": min(max(int(component.page_size or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE),
        "sort_by": "created_on",
        "sort_order": "desc",
        **filters,
    }
    body = firma_request(
        "GET",
        path,
        api_key=component.api_key,
        timeout=float(component.timeout or DEFAULT_TIMEOUT_SECONDS),
        params=params,
    )
    results = body.get("results")
    if not isinstance(results, list):
        msg = "Firma API returned a list response without a results list."
        raise FirmaAPIError(msg)
    return [
        Data(text=str(item.get("name") or item.get("id") or ""), data=item)
        for item in results
        if isinstance(item, dict)
    ]


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_detail(body: Any) -> tuple[str, str | None]:
    """Pull the message and code out of a Firma error body."""
    if not isinstance(body, dict):
        return "", None
    message = str(body.get("error") or body.get("message") or "")
    extra = [
        str(item.get("message"))
        for item in body.get("errors") or []
        if isinstance(item, dict) and item.get("message") and item.get("message") != message
    ]
    # Some routes answer {"error": "<code>", "message": "<text>"}: keep the text too.
    if body.get("error") and body.get("message") and str(body["message"]) != message:
        extra.insert(0, str(body["message"]))
    if extra:
        message = "; ".join(part for part in [message, *extra] if part)
    code = body.get("code")
    return message, str(code) if code else None


def _error(response: httpx.Response, api_key: str) -> FirmaAPIError:
    """Build a short, key-free error from a failed API response."""
    code = None
    body: Any = None
    try:
        body = response.json()
        detail, code = _error_detail(body)
    except ValueError:
        detail = response.text.strip()
    has_firma_body = isinstance(body, dict) and isinstance(body.get("error"), str) and isinstance(body.get("code"), str)
    kept_id = body.get("signing_request_id") if isinstance(body, dict) else None
    signing_request_id = kept_id.strip() if isinstance(kept_id, str) and kept_id.strip() else None
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:_ERROR_DETAIL_LIMIT]
    status = response.status_code
    label = _STATUS_LABELS.get(status, f"Firma API error ({status})")
    if code:
        label = f"{label} {code}"
    message = f"{label}: {detail}" if detail else label
    retry_after = response.headers.get("Retry-After")
    if retry_after and status in {429, 503}:
        message = f"{message} Retry after {retry_after} seconds."
    return FirmaAPIError(
        message, status=status, code=code, has_firma_body=has_firma_body, signing_request_id=signing_request_id
    )


def firma_request(
    method: str,
    path: str,
    *,
    api_key: Any,
    timeout: float,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the Firma API and return the JSON body.

    Raises:
        FirmaAPIError: On a missing key, a transport error, a non-2xx status, or a body that is not a JSON object.
    """
    key = secret_value(api_key)
    if not key:
        msg = "Enter a Firma API key. Find it in Firma under Workspace Settings > API."
        raise FirmaAPIError(msg)
    headers = {"Authorization": key, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, f"{API_BASE_URL}{path}", params=params, json=json, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Firma request timed out after {timeout:g} seconds."
        raise FirmaAPIError(msg, code=NETWORK_ERROR) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Firma API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise FirmaAPIError(msg, code=NETWORK_ERROR) from exc
    if not response.is_success:
        raise _error(response, key)
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Firma API returned a response that is not JSON."
        raise FirmaAPIError(msg, status=response.status_code, code=INVALID_RESPONSE) from exc
    if not isinstance(body, dict):
        msg = "Firma API returned an unexpected response shape."
        raise FirmaAPIError(msg, status=response.status_code, code=INVALID_RESPONSE)
    return body


def upload_document(upload_url: str, data: bytes, content_type: str) -> None:
    """PUT file bytes to a pre-signed storage URL returned by ``POST /documents``.

    The URL carries its own token, so the request has no Firma API key.
    """
    try:
        with httpx.Client(timeout=UPLOAD_TIMEOUT_SECONDS) as client:
            response = client.request("PUT", upload_url, content=data, headers={"Content-Type": content_type})
    except httpx.RequestError as exc:
        msg = f"Uploading the document to Firma storage failed: {type(exc).__name__}."
        raise FirmaAPIError(msg) from exc
    if not response.is_success:
        msg = f"Uploading the document to Firma storage failed with HTTP {response.status_code}."
        raise FirmaAPIError(msg, status=response.status_code)


# Create-and-send safety

CREATE_AND_SEND_PATH = "/signing-requests/create-and-send"
OUTCOME_UNKNOWN = (
    "Firma did not confirm the result, so the document may have been sent. "
    "Check the signing requests in the Firma dashboard before sending again."
)
# 503 codes the create-and-send contract lists: Firma refused before creating anything.
_REFUSED_503_CODES = {"ANCHOR_DISABLED_EDGE", "SEALS_DISABLED"}
# 409 codes whose request was kept (create-and-send 409 contract, send-bridge.ts).
_KEPT_409_CODES = {"ALREADY_SENT", "SEND_EFFECTS_EXIST", "SEND_IN_PROGRESS"}
_SERVER_ERROR = 500
_CONFLICT = 409
_UNAVAILABLE = 503


def _sentence(message: str) -> str:
    message = message.strip()
    return message if not message or message.endswith((".", "!", "?")) else f"{message}."


def send_failure(error: FirmaAPIError) -> FirmaAPIError:
    """Rewrite a failed create-and-send so the text says what may have been left behind.

    - 409 ALREADY_SENT / SEND_EFFECTS_EXIST / SEND_IN_PROGRESS with ``signing_request_id``: that request
      was kept (and, for ALREADY_SENT, sent). The text names it.
    - No proof that nothing was created: a network error or timeout, an unreadable 2xx, Firma's own 500
      (its rollback can fail), 502 PROXY_ERROR from the edge forwarder, 504, 546, any 5xx without a Firma
      body, and any 503 other than ANCHOR_DISABLED_EDGE / SEALS_DISABLED. The text says the document may
      have been sent.
    - Everything else (4xx, 429, the two 503 refusals, input errors) keeps its normal text.

    Nothing retries: a second create-and-send would create a second signing request.
    """
    status = error.status
    if error.code in (NETWORK_ERROR, INVALID_RESPONSE):
        extra = OUTCOME_UNKNOWN
    elif status == _CONFLICT and error.code in _KEPT_409_CODES:
        if error.signing_request_id:
            state = "was sent" if error.code == "ALREADY_SENT" else "was kept and may have been sent"
            extra = (
                f"The signing request {error.signing_request_id} {state}; check it in Firma instead of sending again."
            )
        elif error.code == "SEND_IN_PROGRESS":
            extra = (
                "Another send of this signing request is in progress and the request was kept. "
                "Check the signing requests in the Firma dashboard before sending again."
            )
        else:
            return error
    elif (
        status is None
        or status < _SERVER_ERROR
        or (status == _UNAVAILABLE and error.has_firma_body and error.code in _REFUSED_503_CODES)
    ):
        return error
    else:
        extra = OUTCOME_UNKNOWN
    return FirmaAPIError(
        f"{_sentence(str(error))} {extra}",
        status=status,
        code=error.code,
        has_firma_body=error.has_firma_body,
        signing_request_id=error.signing_request_id,
        may_have_been_sent=True,
    )


def create_and_send(api_key: Any, timeout: float, body: dict[str, Any]) -> dict[str, Any]:
    """POST /signing-requests/create-and-send once; never retried. Failures go through ``send_failure``."""
    try:
        response = firma_request("POST", CREATE_AND_SEND_PATH, api_key=api_key, timeout=timeout, json=body)
    except FirmaAPIError as exc:
        raise send_failure(exc) from exc
    if not response.get("id"):
        msg = "Firma API answered without a signing request id."
        raise send_failure(FirmaAPIError(msg, code=INVALID_RESPONSE))
    return response


def error_data(error: FirmaAPIError) -> Data:
    """The ``Data`` a send component returns for a failure."""
    data: dict[str, Any] = {"error": str(error)}
    if error.may_have_been_sent:
        data["may_have_been_sent"] = True
    if error.signing_request_id:
        data["signing_request_id"] = error.signing_request_id
    return Data(text=str(error), data=data)


# Template roles


def _order_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def template_users(template: dict[str, Any]) -> list[dict[str, Any]]:
    """The template users of ``GET /templates/{id}``: its non-CC recipients, by order."""
    users = [
        item
        for item in template.get("recipients") or []
        if isinstance(item, dict) and item.get("id") and str(item.get("designation") or "").upper() != "CC"
    ]
    return sorted(users, key=lambda item: _order_number(item.get("order")) or 0)


def _covers(recipient: dict[str, Any], user: dict[str, Any], user_ids: set[str]) -> bool:
    """The create-and-send handler's match of a provided recipient to a template user."""
    if recipient.get("template_user_id") and recipient["template_user_id"] == user["id"]:
        return True
    if recipient.get("id") and recipient["id"] in user_ids and recipient["id"] == user["id"]:
        return True
    if not recipient.get("template_user_id"):
        order = _order_number(recipient.get("order"))
        if order is not None and order == _order_number(user.get("order")):
            return not recipient.get("id") or recipient["id"] not in user_ids
    return False


def _role(user: dict[str, Any]) -> str:
    order = _order_number(user.get("order"))
    shown = int(order) if order is not None and order.is_integer() else user.get("order")
    return f"{user.get('designation') or 'Signer'} at order {shown} (template_user_id {user['id']})"


def _check_duplicate_orders(name: str, users: list[dict[str, Any]], recipients: list[dict[str, Any]]) -> None:
    """Refuse the two duplicate-order cases create-and-send refuses (after creating nothing).

    A template with two users at one order needs ``template_user_id`` on every recipient who signs or
    approves; two such recipients at one order each need a ``template_user_id``.
    """
    template_orders = [_order_number(user.get("order")) or 1 for user in users]
    if len(set(template_orders)) < len(template_orders):
        for index, item in enumerate(recipients, start=1):
            if item.get("designation") != "CC" and not item.get("template_user_id"):
                msg = (
                    f'The Firma template "{name}" has more than one role at the same order, so every recipient '
                    f"who signs or approves needs a template_user_id. Recipient {index} has none."
                )
                raise FirmaAPIError(msg)
    shared: dict[float, list[dict[str, Any]]] = {}
    for index, item in enumerate(recipients, start=1):
        if item.get("designation") == "CC":
            continue
        order = _order_number(item.get("order")) or float(index)
        shared.setdefault(order, []).append(item)
    for order, items in shared.items():
        if len(items) > 1 and not all(item.get("template_user_id") for item in items):
            shown = int(order) if order.is_integer() else order
            msg = (
                f"Multiple recipients have order {shown}. With a template, recipients who share an order "
                "must each have a template_user_id."
            )
            raise FirmaAPIError(msg)


def fit_recipients_to_template(
    template: dict[str, Any], recipients: list[dict[str, Any]], *, single_signer: bool
) -> list[dict[str, Any]]:
    """Match the given recipients to the template's users, as create-and-send requires.

    Create-and-send needs a recipient for every template user and keeps each user's designation and order.
    The single signer inputs fill a template with at most one user (by its ``template_user_id``); a
    Recipients (JSON) array passes through when it covers every user. Anything else is refused here,
    before a request is created.
    """
    users = template_users(template)
    if not users:
        return recipients
    name = text_value(template.get("name"))
    if single_signer:
        if len(users) > 1:
            msg = (
                f'The Firma template "{name}" has {len(users)} recipients who sign or approve '
                f"({'; '.join(_role(user) for user in users)}). The signer inputs fill one of them; "
                "Recipients (JSON) with one recipient per role covers all of them."
            )
            raise FirmaAPIError(msg)
        user = users[0]
        recipient = dict(recipients[0])
        recipient["template_user_id"] = user["id"]
        recipient["designation"] = DESIGNATIONS.get(str(user.get("designation") or "").lower(), "Signer")
        recipient["order"] = user.get("order")
        return [recipient]

    user_ids = {user["id"] for user in users}
    by_id = {user["id"]: user for user in users}
    fitted: list[dict[str, Any]] = []
    for entry in recipients:
        user = by_id.get(entry.get("template_user_id")) if entry.get("designation") != "CC" else None
        if user is None:
            fitted.append(entry)
            continue
        # The handler keeps the template user's designation and order for this recipient.
        designation = DESIGNATIONS.get(str(user.get("designation") or "").lower(), "Signer")
        fitted.append({**entry, "designation": designation, "order": user.get("order")})
    recipients = fitted
    providers = [item for item in recipients if item.get("designation") != "CC"]
    _check_duplicate_orders(name, users, recipients)
    missing = [user for user in users if not any(_covers(item, user, user_ids) for item in providers)]
    if missing:
        msg = (
            f'The recipients do not cover every role of the Firma template "{name}". Missing: '
            f"{'; '.join(_role(user) for user in missing)}. Recipients match a role by template_user_id, "
            "then by order."
        )
        raise FirmaAPIError(msg)
    return recipients
