"""Shared plumbing for the Scavio bundle components.

Nothing in this module subclasses ``Component`` on purpose: the bundle loader
registers every ``Component`` subclass it finds, so a shared base class would
show up in the palette as a phantom component. The components mix this class in
alongside ``Component`` instead.

Every Scavio data endpoint is a POST with a JSON body and an
``Authorization: Bearer <key>`` header. Credit costs are per endpoint and are
carried on each :class:`Endpoint` so the UI can state them up front.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx
from lfx.inputs.inputs import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    MultiselectInput,
    SecretStrInput,
)
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

BASE_URL = "https://api.scavio.dev"
REQUEST_TIMEOUT = 90.0
DOCUMENTATION = "https://scavio.dev/docs/langflow"

# Google is the one product that does not wrap its payload: the provider body is
# spread at the top level and response_time / credits_used / credits_remaining
# are appended next to it. Every other product answers
# {data, response_time, credits_used, credits_remaining}.
FLAT_ENVELOPE_PREFIX = "/api/v2/google"

# Keys tried, in order, when picking the human-readable text for a result row.
TEXT_KEYS = ("title", "text", "snippet", "name", "full_name", "query", "description")

# Re-exported so the component modules never import ``lfx`` directly. See the note in
# ``lfx_scavio._component``: reaching into ``lfx.inputs`` or ``lfx.template`` before
# ``lfx.custom.custom_component.component`` trips a circular import inside lfx itself.
__all__ = [
    "BASE_URL",
    "DOCUMENTATION",
    "BoolInput",
    "Data",
    "DataFrame",
    "DropdownInput",
    "Endpoint",
    "IntInput",
    "MessageTextInput",
    "MultiselectInput",
    "ScavioAPIMixin",
    "api_key_input",
    "choice_input",
    "cursor_input",
    "decimal_input",
    "default_visibility",
    "endpoint_input",
    "flag_input",
    "managed_fields",
    "max_results_input",
    "number_input",
    "text_input",
]


@dataclass(frozen=True)
class Endpoint:
    """One Scavio API endpoint, as offered by a component's Endpoint dropdown.

    Attributes:
        path: Public API path, e.g. ``/api/v2/google/maps/search``.
        credits: Credits a successful call costs.
        fields: Input names this endpoint accepts, in UI order.
        required: Subset of ``fields`` the API refuses to run without.
        result_keys: Payload keys tried, in order, to find the row list for the
            table output. Dotted keys walk nested objects. Empty (or no match)
            renders the whole payload as a single row.
        wire: Input name -> API field name, for the few inputs whose UI name has
            to differ from the wire name because two endpoints in the same
            component reuse one wire name with different types.
        send_false: Boolean inputs whose ``False`` is meaningful and must be
            transmitted instead of omitted.
        csv_fields: Text inputs the API wants as a JSON array of strings. The
            user types a comma-separated list; the payload builder splits it.
        csv_int_fields: The same, for arrays of integers.
        credit_note: Set only where the credit cost is a function of the request
            body rather than of the path, in which case it replaces ``credits``
            everywhere a cost is shown. ``credits`` then carries the floor.
    """

    path: str
    credits: int
    fields: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    result_keys: tuple[str, ...] = ()
    wire: dict[str, str] = field(default_factory=dict)
    send_false: tuple[str, ...] = ()
    csv_fields: tuple[str, ...] = ()
    csv_int_fields: tuple[str, ...] = ()
    credit_note: str = ""

    def cost_text(self) -> str:
        """Return the human-readable cost of one call to this endpoint."""
        if self.credit_note:
            return self.credit_note
        return f"{self.credits} credit" if self.credits == 1 else f"{self.credits} credits"


def managed_fields(endpoints: dict[str, Endpoint]) -> tuple[str, ...]:
    """Return every input name any endpoint in the map can show."""
    names: set[str] = set()
    for endpoint in endpoints.values():
        names.update(endpoint.fields)
    return tuple(sorted(names))


def default_visibility(inputs: list, endpoints: dict[str, Endpoint], default_label: str) -> list:
    """Set the initial ``show``/``required`` of every managed input from the default endpoint.

    ``update_build_config`` handles this once the user picks an endpoint, but it only
    fires on interaction - without this the node would open showing the fields of no
    endpoint at all.
    """
    managed = set(managed_fields(endpoints))
    endpoint = endpoints[default_label]
    for item in inputs:
        if item.name in managed:
            item.show = item.name in endpoint.fields
            item.required = item.name in endpoint.required
    return inputs


def api_key_input() -> SecretStrInput:
    """Return the Scavio API key input shared by every component."""
    return SecretStrInput(
        name="api_key",
        display_name="Scavio API Key",
        required=True,
        info="Your Scavio API key. Get one at https://dashboard.scavio.dev - the free plan ships 50 one-time credits.",
    )


def endpoint_input(endpoints: dict[str, Endpoint], value: str) -> DropdownInput:
    """Return the Endpoint dropdown for a multi-endpoint component."""
    options = list(endpoints)
    return DropdownInput(
        name="endpoint",
        display_name="Endpoint",
        info="Which Scavio endpoint to call. The fields below change with this selection.",
        options=options,
        value=value,
        real_time_refresh=True,
        required=True,
    )


def max_results_input() -> IntInput:
    """Return the client-side row cap input."""
    return IntInput(
        name="max_results",
        display_name="Max Results",
        info="Client-side cap on the rows returned. 0 keeps everything the API sent.",
        value=0,
        advanced=True,
    )


def cursor_input(info: str = "Pagination cursor echoed from a previous response.") -> MessageTextInput:
    """Return a pagination cursor input."""
    return MessageTextInput(name="cursor", display_name="Cursor", info=info, advanced=True, dynamic=True, show=False)


def text_input(
    name: str,
    display_name: str,
    info: str,
    *,
    tool_mode: bool = False,
    advanced: bool = False,
) -> MessageTextInput:
    """Return a dynamic free-text input managed by ``update_build_config``."""
    return MessageTextInput(
        name=name,
        display_name=display_name,
        info=info,
        tool_mode=tool_mode,
        advanced=advanced,
        dynamic=True,
        show=False,
    )


def choice_input(
    name: str,
    display_name: str,
    info: str,
    options: list[str],
    *,
    advanced: bool = False,
) -> DropdownInput:
    """Return a dynamic dropdown whose empty first option means "let the API decide"."""
    return DropdownInput(
        name=name,
        display_name=display_name,
        info=info,
        options=options,
        value="",
        advanced=advanced,
        dynamic=True,
        show=False,
    )


def number_input(
    name: str,
    display_name: str,
    info: str,
    value: int = 0,
    *,
    advanced: bool = True,
) -> IntInput:
    """Return a dynamic integer input. Zero always means "not set"."""
    return IntInput(
        name=name,
        display_name=display_name,
        info=info,
        value=value,
        advanced=advanced,
        dynamic=True,
        show=False,
    )


def decimal_input(
    name: str,
    display_name: str,
    info: str,
    *,
    advanced: bool = True,
) -> FloatInput:
    """Return a dynamic float input. Zero always means "not set"."""
    return FloatInput(
        name=name,
        display_name=display_name,
        info=info,
        value=0.0,
        advanced=advanced,
        dynamic=True,
        show=False,
    )


def flag_input(
    name: str,
    display_name: str,
    info: str,
    *,
    advanced: bool = True,
) -> BoolInput:
    """Return a dynamic boolean input.

    These are filters, so ``False`` means "do not filter" and is omitted from the
    payload rather than sent. An endpoint that needs a literal ``false`` on the
    wire lists the input in :attr:`Endpoint.send_false`.
    """
    return BoolInput(
        name=name,
        display_name=display_name,
        info=info,
        value=False,
        advanced=advanced,
        dynamic=True,
        show=False,
    )


class ScavioAPIMixin:
    """Call one Scavio endpoint and shape the answer into ``Data`` / ``DataFrame``."""

    ENDPOINTS: dict[str, Endpoint] = {}
    MANAGED_FIELDS: tuple[str, ...] = ()
    DEFAULT_ENDPOINT: str = ""

    def _endpoint(self) -> Endpoint:
        label = getattr(self, "endpoint", None) or self.DEFAULT_ENDPOINT
        endpoint = self.ENDPOINTS.get(label)
        if endpoint is None:
            msg = f"Unknown Scavio endpoint '{label}'. Pick one of: {', '.join(self.ENDPOINTS)}."
            raise ValueError(msg)
        return endpoint

    @staticmethod
    def _clean(value: Any) -> Any:
        """Drop empty values so optional params are omitted rather than sent blank."""
        if isinstance(value, bool):
            return value or None
        if isinstance(value, int | float):
            return value or None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, list | tuple):
            items = [item for item in value if item not in (None, "")]
            return items or None
        return value or None

    @staticmethod
    def _split_csv(value: Any, *, as_int: bool) -> list | None:
        """Turn a comma-separated string into the JSON array these endpoints expect."""
        if isinstance(value, list | tuple):
            items: list[Any] = list(value)
        else:
            items = [part.strip() for part in str(value).split(",")]
        items = [item for item in items if item not in (None, "")]
        if as_int:
            numbers = []
            for item in items:
                try:
                    numbers.append(int(item))
                except (TypeError, ValueError):
                    continue
            items = numbers
        return items or None

    def _payload(self, endpoint: Endpoint) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        missing: list[str] = []
        for name in endpoint.fields:
            raw = getattr(self, name, None)
            wire_name = endpoint.wire.get(name, name)
            if isinstance(raw, bool) and name in endpoint.send_false:
                payload[wire_name] = raw
                continue
            cleaned = self._clean(raw)
            if cleaned is None:
                if name in endpoint.required:
                    missing.append(name)
                continue
            if name in endpoint.csv_fields or name in endpoint.csv_int_fields:
                cleaned = self._split_csv(cleaned, as_int=name in endpoint.csv_int_fields)
                if cleaned is None:
                    continue
            payload[wire_name] = cleaned
        if missing:
            verb = "is" if len(missing) == 1 else "are"
            msg = f"{', '.join(missing)} {verb} required for {endpoint.path}."
            raise ValueError(msg)
        return payload

    def _request(self, endpoint: Endpoint, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
        }
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.post(f"{BASE_URL}{endpoint.path}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def _safe_call(self) -> tuple[Endpoint | None, dict[str, Any] | None, str | None]:
        """Run the request, converting every failure into a message instead of raising."""
        try:
            endpoint = self._endpoint()
            body = self._request(endpoint, self._payload(endpoint))
        except httpx.TimeoutException:
            message = f"Request timed out after {int(REQUEST_TIMEOUT)}s. Try again or narrow the request."
        except httpx.HTTPStatusError as exc:
            message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
        except httpx.RequestError as exc:
            message = f"Request error occurred: {exc}"
        except ValueError as exc:
            message = str(exc)
        else:
            return endpoint, body, None
        logger.error(message)
        return None, None, message

    @staticmethod
    def _unwrap(body: dict[str, Any], endpoint: Endpoint) -> Any:
        """Return the payload inside the response envelope."""
        if endpoint.path.startswith(FLAT_ENVELOPE_PREFIX):
            return body
        return body.get("data", body)

    @staticmethod
    def _lookup(payload: Any, dotted: str) -> Any:
        current = payload
        for part in dotted.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _rows(self, payload: Any, endpoint: Endpoint) -> list[dict[str, Any]]:
        for key in endpoint.result_keys:
            found = self._lookup(payload, key)
            if isinstance(found, list):
                return [item if isinstance(item, dict) else {"value": item} for item in found]
            if isinstance(found, dict):
                return [found]
        if isinstance(payload, list):
            return [item if isinstance(item, dict) else {"value": item} for item in payload]
        if isinstance(payload, dict):
            return [payload]
        return [{"value": payload}]

    @staticmethod
    def _row_text(row: dict[str, Any]) -> str:
        for key in TEXT_KEYS:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return json.dumps(row, ensure_ascii=False, default=str)

    def fetch_content(self) -> list[Data]:
        """Return one ``Data`` per result row, or a single error row."""
        endpoint, body, error = self._safe_call()
        if error is not None or endpoint is None or body is None:
            message = error or "Scavio request failed."
            return [Data(text=message, data={"error": message})]
        rows = self._rows(self._unwrap(body, endpoint), endpoint)
        limit = getattr(self, "max_results", 0) or 0
        if limit > 0:
            rows = rows[:limit]
        results = [Data(text=self._row_text(row), data=row) for row in rows]
        self.status = results
        return results

    def fetch_content_dataframe(self) -> DataFrame:
        """Return the result rows as a table."""
        return DataFrame(self.fetch_content())

    def fetch_raw(self) -> Data:
        """Return the untouched response body, including the credit counters."""
        _endpoint, body, error = self._safe_call()
        if error is not None or body is None:
            message = error or "Scavio request failed."
            return Data(text=message, data={"error": message})
        self.status = body
        return Data(data=body)

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Show only the fields the selected endpoint accepts."""
        if field_name not in {"endpoint", None}:
            return build_config
        label = field_value if field_name == "endpoint" else build_config.get("endpoint", {}).get("value")
        endpoint = self.ENDPOINTS.get(label) or self.ENDPOINTS.get(self.DEFAULT_ENDPOINT)
        if endpoint is None:
            return build_config
        for name in self.MANAGED_FIELDS:
            if name in build_config:
                build_config[name]["show"] = name in endpoint.fields
                build_config[name]["required"] = name in endpoint.required
        return build_config
