"""Langflow configuration, source validation, and one-shot execution."""

import json
from urllib.parse import urlsplit

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, MessageTextInput, MultilineInput, SecretStrInput
from lfx.schema.data import Data
from pydantic import BaseModel, SecretStr, ValidationError

from lfx_flashdata._client import Client, FlashDataError
from lfx_flashdata._storage import storage_config


def component_inputs(primary: str, model: type[BaseModel], *, action: str) -> list:
    labels = {
        "query": "Search Query",
        "video_id": "Video ID or URL",
        "handle": "Channel Handle",
        "job_id": "Saved Job ID",
    }
    fields = [
        SecretStrInput(
            name="api_key",
            display_name="FlashData API Key",
            required=True,
            password=True,
            info="Use a Credential global variable. Obtain a key at https://flashdata.dev. API calls use paid Credits.",
        ),
        MessageTextInput(
            name=primary,
            display_name=labels[primary],
            info=model.model_fields[primary].description,
            required=True,
            tool_mode=True,
        ),
    ]
    options = [name for name in model.model_fields if name != primary]
    if options:
        fields.append(
            MultilineInput(
                name="parameters",
                display_name="Advanced Parameters (JSON)",
                value="{}",
                advanced=True,
                info="Optional source settings: "
                + ", ".join(options)
                + ". Do not include credentials or the primary input.",
            )
        )
    if action == "submit":
        fields.extend(
            [
                SecretStrInput(
                    name="storage_json",
                    display_name="Customer Storage (secret JSON)",
                    required=True,
                    password=True,
                    info="A Credential global variable containing your destination and storage credentials.",
                ),
                BoolInput(
                    name="allow_submit",
                    display_name="Allow Paid Submission",
                    value=False,
                    info="Enable only after authorizing this paid job and customer-storage write. Save the job ID.",
                ),
            ]
        )
    return fields


def secret_value(value: str | SecretStr | None) -> str:
    return value.get_secret_value() if isinstance(value, SecretStr) else value or ""


class FlashDataBaseComponent(Component):
    icon = "Search"

    def client(self) -> Client:
        api_key = secret_value(self.api_key).strip()
        if not api_key or any(char < " " or char == "\x7f" for char in api_key):
            msg = "Set a valid FlashData API Key credential."
            raise FlashDataError(msg)
        return Client(api_key)

    def validated_inputs(self) -> dict:
        raw = getattr(self, "parameters", "{}") or "{}"
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or self.primary in data:
                raise ValueError
            data[self.primary] = getattr(self, self.primary)
            return self.input_model.model_validate(data).model_dump(exclude_none=True, by_alias=True)
        except (ValueError, TypeError, ValidationError):
            msg = "Invalid source inputs. Check the primary input and the source-specific Advanced Parameters JSON."
            raise FlashDataError(msg) from None

    def output_data(self, payload: dict) -> Data:
        result = Data(data=payload, text=json.dumps(payload, ensure_ascii=False))
        self.status = "Request completed. Inspect the JSON output."
        return result


class FlashDataQueryComponent(FlashDataBaseComponent):
    async def execute(self) -> Data:
        data = self.validated_inputs()
        payload = {"source": self.source, self.primary: data.pop(self.primary), "params": data}
        return self.output_data(await self.client().query(payload))


class FlashDataDownloadSubmitComponent(FlashDataBaseComponent):
    async def execute(self) -> Data:
        if self.allow_submit is not True:
            msg = "Enable Allow Paid Submission only after authorizing the job and customer-storage write."
            raise FlashDataError(msg)
        data = self.validated_inputs()
        storage = storage_config(secret_value(self.storage_json))
        if storage.get("endpoint_url"):
            try:
                url = urlsplit(storage["endpoint_url"])
                if (
                    url.scheme != "https"
                    or not url.hostname
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                ):
                    raise ValueError
                _ = url.port
            except ValueError:
                msg = "Storage endpoint must be an HTTPS URL without credentials."
                raise FlashDataError(msg) from None
        payload = {
            "source": "youtube_download",
            "video_id": data.pop("video_id"),
            "params": {**data, "storage": storage},
        }
        return self.output_data(await self.client().submit(payload))


class FlashDataJobComponent(FlashDataBaseComponent):
    async def execute(self) -> Data:
        data = self.validated_inputs()
        client = self.client()
        payload = (
            await client.status(data["job_id"]) if self.action == "status" else await client.result(data["job_id"])
        )
        return self.output_data(payload)
