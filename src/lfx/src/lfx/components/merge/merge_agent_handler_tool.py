from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
from langchain_core.tools import StructuredTool, Tool

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.io import BoolInput, DropdownInput, Output, SecretStrInput

from .mcp_client import MergeAgentHandlerClient
from .schema_utils import create_dispatch_schema, json_schema_to_pydantic_model

if TYPE_CHECKING:
    from .types import McpTool, MergeRegisteredUser, MergeToolPack


class MergeAgentHandlerToolsComponent(LCToolComponent):
    display_name = "Merge Agent Handler Tools"
    description = "Connect an AI Agent to a Merge Agent Handler Tool Pack"
    name = "MergeAgentHandlerTools"
    icon = "Merge"
    documentation = "https://docs.langflow.org/bundles-merge"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            real_time_refresh=True,
            info="Merge Agent Handler API key.",
        ),
        DropdownInput(
            name="tool_pack_id",
            display_name="Tool Pack",
            required=True,
            options=[],
            value="",
            real_time_refresh=True,
            info="Select the Merge Tool Pack to expose to the agent.",
        ),
        DropdownInput(
            name="environment",
            display_name="Environment",
            required=True,
            options=["Production", "Test"],
            value="Production",
            real_time_refresh=True,
            info="Whether to use production or test registered users.",
        ),
        DropdownInput(
            name="registered_user_id",
            display_name="Registered User",
            required=True,
            options=[],
            value="",
            real_time_refresh=True,
            info="Registered user identity to execute tools as.",
        ),
        BoolInput(
            name="use_dispatch_mode",
            display_name="Use Dispatch Mode",
            advanced=True,
            value=False,
            info="Create a single dispatch tool instead of individual tools.",
        ),
    ]

    outputs = [Output(name="tools", display_name="Tools", method="build_tool")]

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        if field_name not in {"api_key", "environment", None}:
            return build_config

        api_key = self._resolve_api_key(
            field_value if field_name == "api_key" else self._config_value(build_config, "api_key", "")
        )
        if not api_key:
            api_key = self._resolve_api_key(getattr(self, "api_key", ""))

        if not api_key:
            self._set_dropdown_options(build_config, "tool_pack_id", {})
            self._set_dropdown_options(build_config, "registered_user_id", {})
            return build_config

        environment = str(self._config_value(build_config, "environment", "production")).lower()
        is_test = environment == "test"

        try:
            with MergeAgentHandlerClient(api_key=api_key) as client:
                if field_name in {"api_key", None}:
                    packs = client.get_tool_packs()
                    self._set_dropdown_options(
                        build_config,
                        "tool_pack_id",
                        self._tool_pack_option_map(packs),
                    )

                if field_name in {"api_key", "environment", None}:
                    users = client.get_registered_users(is_test=is_test)
                    self._set_dropdown_options(
                        build_config,
                        "registered_user_id",
                        self._registered_user_option_map(users),
                    )
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError) as exc:
            self.log(f"Failed to refresh Merge options: {exc}")
            if field_name in {"api_key", None}:
                self._set_dropdown_options(build_config, "tool_pack_id", {})
            if field_name in {"api_key", "environment", None}:
                self._set_dropdown_options(build_config, "registered_user_id", {})

        return build_config

    def build_tool(self) -> list[Tool]:
        api_key = self._resolve_api_key(self.api_key)
        if not api_key:
            msg = "An API key is required"
            raise ValueError(msg)

        selected_tool_pack = str(self.tool_pack_id or "").strip()
        selected_registered_user = str(self.registered_user_id or "").strip()
        if not selected_tool_pack or not selected_registered_user:
            msg = "Tool Pack and Registered User must be selected"
            raise ValueError(msg)

        environment = str(self.environment or "production").lower()
        is_test = environment == "test"

        with MergeAgentHandlerClient(api_key=api_key) as client:
            tool_pack_id = self._resolve_tool_pack_id(client, selected_tool_pack)
            registered_user_id = self._resolve_registered_user_id(
                client,
                selected_registered_user,
                is_test_environment=is_test,
            )

            mcp_tools = client.list_mcp_tools(tool_pack_id, registered_user_id)
            if not mcp_tools:
                msg = "No tools found in the selected Tool Pack"
                raise ValueError(msg)

            if bool(self.use_dispatch_mode):
                dispatch_tool = self._build_dispatch_tool(
                    api_key,
                    mcp_tools,
                    tool_pack_id,
                    registered_user_id,
                    selected_tool_pack,
                )
                return [dispatch_tool]

            return self._build_individual_tools(
                api_key,
                mcp_tools,
                tool_pack_id,
                registered_user_id,
            )

    def _build_dispatch_tool(
        self,
        api_key: str,
        mcp_tools: list[McpTool],
        tool_pack_id: str,
        registered_user_id: str,
        tool_pack_label: str,
    ) -> Tool:
        tool_names = [str(tool.get("name", "")) for tool in mcp_tools if tool.get("name")]
        dispatch_schema = create_dispatch_schema(tool_names)
        dispatch_name = self._safe_tool_name(tool_pack_label or "merge_tool_pack")

        description_lines = [
            "Execute tools from the selected Merge Tool Pack.",
            "Provide a tool_name and JSON arguments.",
            "Available tools:",
        ]
        for tool in mcp_tools:
            name = str(tool.get("name") or "unknown_tool")
            description = str(tool.get("description") or "No description")
            description_lines.append(f"- {name}: {description}")

        def _dispatch(tool_name: str, arguments: dict[str, Any] | None = None) -> str:
            return self._call_tool(
                api_key=api_key,
                tool_pack_id=tool_pack_id,
                registered_user_id=registered_user_id,
                tool_name=tool_name,
                args=arguments or {},
            )

        return StructuredTool.from_function(
            name=dispatch_name,
            description="\n".join(description_lines),
            func=_dispatch,
            args_schema=dispatch_schema,
            handle_validation_error=self._handle_tool_validation_error,
        )

    def _build_individual_tools(
        self,
        api_key: str,
        mcp_tools: list[McpTool],
        tool_pack_id: str,
        registered_user_id: str,
    ) -> list[Tool]:
        tools: list[Tool] = []
        used_names: set[str] = set()

        for index, mcp_tool in enumerate(mcp_tools, start=1):
            raw_name = str(mcp_tool.get("name") or f"merge_tool_{index}")
            safe_name = self._ensure_unique_name(self._safe_tool_name(raw_name), used_names)

            input_schema = mcp_tool.get("inputSchema") or {"type": "object", "properties": {}}
            args_schema = json_schema_to_pydantic_model(f"{safe_name}_Input", input_schema)
            description = str(mcp_tool.get("description") or f'Run Merge MCP tool "{raw_name}".')

            def _run(_tool_name: str = raw_name, **kwargs: Any) -> str:
                return self._call_tool(
                    api_key=api_key,
                    tool_pack_id=tool_pack_id,
                    registered_user_id=registered_user_id,
                    tool_name=_tool_name,
                    args=kwargs,
                )

            tools.append(
                StructuredTool.from_function(
                    name=safe_name,
                    description=description,
                    func=_run,
                    args_schema=args_schema,
                    handle_validation_error=self._handle_tool_validation_error,
                )
            )

        return tools

    def _resolve_tool_pack_id(self, client: MergeAgentHandlerClient, selected: str) -> str:
        if self._looks_like_id(selected):
            return selected

        option_map = getattr(self, "_tool_pack_label_to_id", {})
        if isinstance(option_map, dict) and selected in option_map:
            return str(option_map[selected])

        refreshed_map = self._tool_pack_option_map(client.get_tool_packs())
        self._tool_pack_label_to_id = refreshed_map
        if selected in refreshed_map:
            return refreshed_map[selected]

        valid = ", ".join(sorted(refreshed_map.keys()))
        msg = f"Unknown Tool Pack selection: {selected}. Valid options: {valid}"
        raise ValueError(msg)

    def _resolve_registered_user_id(
        self,
        client: MergeAgentHandlerClient,
        selected: str,
        *,
        is_test_environment: bool,
    ) -> str:
        if self._looks_like_id(selected):
            return selected

        option_map = getattr(self, "_registered_user_label_to_id", {})
        if isinstance(option_map, dict) and selected in option_map:
            return str(option_map[selected])

        refreshed_map = self._registered_user_option_map(client.get_registered_users(is_test=is_test_environment))
        self._registered_user_label_to_id = refreshed_map
        if selected in refreshed_map:
            return refreshed_map[selected]

        valid = ", ".join(sorted(refreshed_map.keys()))
        msg = f"Unknown Registered User selection: {selected}. Valid options: {valid}"
        raise ValueError(msg)

    def _set_dropdown_options(
        self,
        build_config: dict[str, Any],
        field_name: str,
        label_to_id: dict[str, str],
    ) -> None:
        labels = sorted(label_to_id.keys())

        if field_name in build_config:
            build_config[field_name]["options"] = labels
            current_value = self._config_value(build_config, field_name, "")
            if current_value not in labels:
                build_config[field_name]["value"] = labels[0] if labels else ""

        if field_name == "tool_pack_id":
            self._tool_pack_label_to_id = label_to_id
        elif field_name == "registered_user_id":
            self._registered_user_label_to_id = label_to_id

    @staticmethod
    def _handle_tool_validation_error(error: Any) -> str:
        missing_fields: list[str] = []
        errors_method = getattr(error, "errors", None)
        if callable(errors_method):
            try:
                errors = errors_method()
            except (TypeError, ValueError):
                errors = []

            for entry in errors:
                if not isinstance(entry, dict) or entry.get("type") != "missing":
                    continue
                location = entry.get("loc") or ()
                if isinstance(location, str):
                    field_name = location
                elif isinstance(location, (list, tuple)):
                    field_name = ".".join(str(part) for part in location)
                else:
                    field_name = str(location)
                if field_name:
                    missing_fields.append(field_name)

        if missing_fields:
            fields = ", ".join(sorted(set(missing_fields)))
            return f"Tool input validation failed. Missing required fields: {fields}. Retry with all required fields."
        return f"Tool input validation failed: {error!s}"

    @staticmethod
    def _tool_pack_option_map(tool_packs: list[MergeToolPack]) -> dict[str, str]:
        options: dict[str, str] = {}
        for tool_pack in tool_packs:
            tool_pack_id = str(tool_pack.get("id") or "").strip()
            if not tool_pack_id:
                continue

            name = str(tool_pack.get("name") or tool_pack_id)
            connector_names: list[str] = []
            connectors = tool_pack.get("connectors") or []
            if isinstance(connectors, list):
                for connector in connectors:
                    if isinstance(connector, dict):
                        connector_name = str(connector.get("name") or connector.get("slug") or "").strip()
                    else:
                        connector_name = str(connector).strip()
                    if connector_name:
                        connector_names.append(connector_name)

            connector_summary = MergeAgentHandlerToolsComponent._summarize_option_items(connector_names)
            label = f"{name} ({tool_pack_id[:8]}) | Apps: {connector_summary or 'none'}"
            MergeAgentHandlerToolsComponent._insert_unique_option(options, label, tool_pack_id)
        return options

    @staticmethod
    def _registered_user_option_map(users: list[MergeRegisteredUser]) -> dict[str, str]:
        options: dict[str, str] = {}
        for user in users:
            user_id = str(user.get("id") or "").strip()
            if not user_id:
                continue

            base_name = (
                str(user.get("origin_user_name") or "").strip()
                or str(user.get("origin_user_id") or "").strip()
                or user_id
            )
            connector_values = user.get("authenticated_connectors") or []
            connector_names = [str(value).strip() for value in connector_values if str(value).strip()]
            connector_summary = MergeAgentHandlerToolsComponent._summarize_option_items(connector_names)
            label = f"{base_name} ({user_id[:8]}) | Connected: {connector_summary or 'none'}"
            MergeAgentHandlerToolsComponent._insert_unique_option(options, label, user_id)

        return options

    @staticmethod
    def _insert_unique_option(options: dict[str, str], label: str, option_id: str) -> None:
        if label not in options:
            options[label] = option_id
            return

        if options[label] == option_id:
            return

        prefix, separator, suffix = label.partition(" | ")
        expanded_prefix = f"{prefix} [{option_id}]"
        expanded_label = f"{expanded_prefix}{separator}{suffix}" if separator else expanded_prefix
        if expanded_label not in options:
            options[expanded_label] = option_id
            return

        counter = 2
        while True:
            candidate = f"{expanded_label} ({counter})"
            if candidate not in options:
                options[candidate] = option_id
                return
            counter += 1

    @staticmethod
    def _summarize_option_items(values: list[str], limit: int = 3) -> str:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value).strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(cleaned)

        if not unique:
            return ""
        if len(unique) <= limit:
            return ", ".join(unique)

        return f"{', '.join(unique[:limit])} +{len(unique) - limit} more"

    @staticmethod
    def _safe_tool_name(name: str) -> str:
        safe = re.sub(r"[^0-9a-zA-Z_-]+", "_", name).strip("_")
        if not safe:
            safe = "merge_tool"
        if safe[0].isdigit():
            safe = f"tool_{safe}"
        return safe[:60]

    @staticmethod
    def _ensure_unique_name(name: str, used_names: set[str]) -> str:
        if name not in used_names:
            used_names.add(name)
            return name

        counter = 2
        while True:
            candidate = f"{name}_{counter}"
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate
            counter += 1

    @staticmethod
    def _looks_like_id(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]{12,}", value))

    @staticmethod
    def _extract_api_key(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "get_secret_value"):
            try:
                return str(value.get_secret_value())
            except Exception:  # noqa: BLE001
                return ""
        if isinstance(value, dict):
            for key in ("value", "api_key", "name"):
                maybe_value = value.get(key)
                if isinstance(maybe_value, str) and maybe_value.strip():
                    return maybe_value.strip()
            return ""
        return str(value)

    def _resolve_api_key(self, value: Any) -> str:
        candidate = self._extract_api_key(value).strip()
        if not candidate:
            return ""

        if hasattr(self, "user_id") and self.user_id:
            try:
                resolved = self.variables(candidate, "api_key")
            except (AttributeError, TypeError, ValueError):
                return candidate
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        return candidate

    @staticmethod
    def _config_value(build_config: dict[str, Any], field_name: str, default: Any) -> Any:
        field_config = build_config.get(field_name) if isinstance(build_config, dict) else None
        if isinstance(field_config, dict):
            return field_config.get("value", default)
        return default

    @staticmethod
    def _call_tool(
        api_key: str,
        tool_pack_id: str,
        registered_user_id: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> str:
        normalized_args = MergeAgentHandlerToolsComponent._normalize_tool_args(args)
        with MergeAgentHandlerClient(api_key=api_key) as client:
            return client.call_mcp_tool(
                tool_pack_id=tool_pack_id,
                user_id=registered_user_id,
                name=tool_name,
                args=normalized_args,
            )

    @staticmethod
    def _normalize_tool_args(value: Any) -> Any:
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            try:
                dumped_value = model_dump()
            except (TypeError, ValueError):
                dumped_value = None
            if dumped_value is not None:
                return MergeAgentHandlerToolsComponent._normalize_tool_args(dumped_value)

        to_dict = getattr(value, "dict", None)
        if callable(to_dict):
            try:
                dumped_value = to_dict()
            except (TypeError, ValueError):
                dumped_value = None
            if dumped_value is not None:
                return MergeAgentHandlerToolsComponent._normalize_tool_args(dumped_value)
        if isinstance(value, dict):
            return {str(key): MergeAgentHandlerToolsComponent._normalize_tool_args(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [MergeAgentHandlerToolsComponent._normalize_tool_args(item) for item in value]
        return value


# Backward-compatible aliases for existing saved flows/imports.
MergeAgentHandlerToolComponent = MergeAgentHandlerToolsComponent
Component = MergeAgentHandlerToolsComponent
