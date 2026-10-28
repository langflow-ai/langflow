from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import IntInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_famulor.components.famulor._client import (
    MAX_PAGE_SIZE,
    api_key_input,
    clamp_page,
    error_message,
    guard,
    page_total,
    request_json,
    unwrap_data,
)

_ASSISTANT_FIELDS = ("id", "name", "mode", "is_active", "stt_language", "greeting_mode", "updated_at")


class FamulorListAssistantsComponent(Component):
    """List Famulor assistants in the workspace."""

    display_name = "Famulor List Assistants"
    description = "List Famulor assistants, newest first."
    documentation = "https://docs.famulor.io/api-reference/assistants/list-assistants"
    icon = "Famulor"

    inputs = [
        api_key_input(),
        IntInput(
            name="limit",
            display_name="Limit",
            value=50,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=1, max=MAX_PAGE_SIZE, step=1, step_type="int"),
            info="Page size, from 1 to 200. Default: 50.",
            tool_mode=True,
        ),
        IntInput(
            name="offset",
            display_name="Offset",
            value=0,
            required=False,
            advanced=True,
            range_spec=RangeSpec(min=0, max=100000, step=1, step_type="int"),
            info="Number of assistants to skip. Default: 0.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Assistants", name="assistants", method="famulor_list_assistants"),
        Output(display_name="Table", name="dataframe", method="famulor_list_assistants_table", tool_mode=False),
        Output(display_name="Message", name="message", method="famulor_list_assistants_message", tool_mode=False),
    ]

    def _load_page(self) -> Data:
        limit, offset = clamp_page(self.limit, self.offset)
        payload = request_json(
            "GET",
            "/assistants",
            self.famulor_api_key,
            params={"limit": limit, "offset": offset},
        )
        rows, meta = unwrap_data(payload)
        if not isinstance(rows, list):
            msg = "Famulor API returned an unexpected response (expected a list of assistants)."
            raise TypeError(msg)
        items = [_assistant_row(row) for row in rows if isinstance(row, dict)]
        total = page_total(meta, len(items))
        text = f"Showing {len(items)} assistants (total {total})."
        return Data(text=text, data={"items": items, "limit": limit, "offset": offset, "total": total})

    def famulor_list_assistants(self) -> Data:
        """List assistants and return the page, including the total count."""
        result = guard(self._load_page)
        self.status = result
        return result

    def famulor_list_assistants_table(self) -> DataFrame:
        """List assistants and return one table row per assistant."""
        result = self.famulor_list_assistants()
        if isinstance(result.data, dict) and "error" in result.data:
            return DataFrame([result])
        items = result.data.get("items", []) if isinstance(result.data, dict) else []
        return DataFrame(items)

    def famulor_list_assistants_message(self) -> Message:
        """List assistants and return a one-line count."""
        return error_message(self.famulor_list_assistants())


def _assistant_row(row: dict) -> dict:
    return {field: row.get(field) for field in _ASSISTANT_FIELDS}
