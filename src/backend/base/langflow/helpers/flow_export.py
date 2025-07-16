# This file is auto-generated from a flow JSON file by generate_flow_vc.
# ruff: noqa

import asyncio
import os
import sys
from uuid import uuid4
import json
from langflow.custom.custom_component.component import Component
import argparse
from components.AzureOpenAIModel_FJjEQ import AzureChatOpenAIComponent as _AzureOpenAIModel_FJjEQ
from components.AzureOpenAIModel_T1QUR import AzureChatOpenAIComponent as _AzureOpenAIModel_T1QUR
from components.ChatInput_Gywma import ChatInput as _ChatInput_Gywma
from components.MCP_Connection_Agent_Platform_yenDh import (
    AgentPlatformMCPConnection as _MCP_Connection_Agent_Platform_yenDh,
)
from components.JSONCleaner_Yap5Q import JSONCleaner as _JSONCleaner_Yap5Q
from components.StructuredOutput_teP6p import StructuredOutputComponent as _StructuredOutput_teP6p
from components.CustomComponent_PIDyq import CustomComponent as _CustomComponent_PIDyq
from components.CustomComponent_ukXWb import CustomComponent as _CustomComponent_ukXWb
from components.CustomComponent_Uygmo import CustomComponent as _CustomComponent_Uygmo
from components.AzureOpenAIModel_pGIWl import AzureChatOpenAIComponent as _AzureOpenAIModel_pGIWl
from components.MCP_Connection_Agent_Platform_05d3E import (
    AgentPlatformMCPConnection as _MCP_Connection_Agent_Platform_05d3E,
)
from components.MCP_Connection_Agent_Platform_v2Dkx import (
    AgentPlatformMCPConnection as _MCP_Connection_Agent_Platform_v2Dkx,
)
from components.ChatOutput_vUTI9 import ChatOutput as _ChatOutput_vUTI9
from components.ConditionalRouter_wUszV import ConditionalRouterComponent as _ConditionalRouter_wUszV
from components.StructuredOutput_3eYS1 import StructuredOutputComponent as _StructuredOutput_3eYS1
from components.ChatOutput_XjvrW import ChatOutput as _ChatOutput_XjvrW
from components.ParserComponent_oMgqW import ParserComponent as _ParserComponent_oMgqW
from components.Agent_mFimM import AgentComponent as _Agent_mFimM
from components.CustomComponent_duEs3 import CustomComponent as _CustomComponent_duEs3
from components.ChatOutput_yjAvZ import ChatOutput as _ChatOutput_yjAvZ


async def set_component_inputs_and_run(component: Component, inputs: dict | None = None):
    if inputs:
        component.build(**inputs)
    await component.run()


async def run(
    flow_input: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    flow_name: str | None = None,
    flow_id: str | None = None,
    env_values: dict | None = None,
):
    env_values = env_values or os.environ.copy()
    global_state = {
        "_session_id": session_id or str(uuid4()),
        "_user_id": user_id,
        "_flow_name": flow_name or "ticket_enrichment",
        "_flow_id": flow_id or "11d0bf95-a370-47ff-bb0e-9214c10c3051",
    }
    components: dict[str, Component] = {}
    results = {
        "outputs": {},
        "components": {},
        "global_state": global_state,
    }

    # Initialize all components
    components["AzureOpenAIModel_FJjEQ"] = _AzureOpenAIModel_FJjEQ(**global_state)
    components["AzureOpenAIModel_T1QUR"] = _AzureOpenAIModel_T1QUR(**global_state)
    components["ChatInput_Gywma"] = _ChatInput_Gywma(**global_state)
    components["MCP_Connection_Agent_Platform_yenDh"] = _MCP_Connection_Agent_Platform_yenDh(**global_state)
    components["JSONCleaner_Yap5Q"] = _JSONCleaner_Yap5Q(**global_state)
    components["StructuredOutput_teP6p"] = _StructuredOutput_teP6p(**global_state)
    components["CustomComponent_PIDyq"] = _CustomComponent_PIDyq(**global_state)
    components["CustomComponent_ukXWb"] = _CustomComponent_ukXWb(**global_state)
    components["CustomComponent_Uygmo"] = _CustomComponent_Uygmo(**global_state)
    components["AzureOpenAIModel_pGIWl"] = _AzureOpenAIModel_pGIWl(**global_state)
    components["MCP_Connection_Agent_Platform_05d3E"] = _MCP_Connection_Agent_Platform_05d3E(**global_state)
    components["MCP_Connection_Agent_Platform_v2Dkx"] = _MCP_Connection_Agent_Platform_v2Dkx(**global_state)
    components["ChatOutput_vUTI9"] = _ChatOutput_vUTI9(**global_state)
    components["ConditionalRouter_wUszV"] = _ConditionalRouter_wUszV(**global_state)
    components["StructuredOutput_3eYS1"] = _StructuredOutput_3eYS1(**global_state)
    components["ChatOutput_XjvrW"] = _ChatOutput_XjvrW(**global_state)
    components["ParserComponent_oMgqW"] = _ParserComponent_oMgqW(**global_state)
    components["Agent_mFimM"] = _Agent_mFimM(**global_state)
    components["CustomComponent_duEs3"] = _CustomComponent_duEs3(**global_state)
    components["ChatOutput_yjAvZ"] = _ChatOutput_yjAvZ(**global_state)

    # Set inputs and run components in topological order
    await set_component_inputs_and_run(
        components["AzureOpenAIModel_FJjEQ"],
        {
            "api_key": "",
            "api_version": "2024-10-01-preview",
            "azure_deployment": "gpt-4o-2024-08-06",
            "azure_endpoint": env_values.get("AZURE_OPENAI_ENDPOINT", ""),
            "input_value": flow_input or "",
            "max_tokens": "",
            "stream": False,
            "system_message": "",
            "temperature": 0,
        },
    )
    await set_component_inputs_and_run(
        components["AzureOpenAIModel_T1QUR"],
        {
            "api_key": "",
            "api_version": "2024-10-01-preview",
            "azure_deployment": "gpt-4o-2024-08-06",
            "azure_endpoint": env_values.get("AZURE_OPENAI_ENDPOINT", ""),
            "input_value": flow_input or "",
            "max_tokens": "",
            "stream": False,
            "system_message": "",
            "temperature": 0,
        },
    )
    await set_component_inputs_and_run(
        components["ChatInput_Gywma"],
        {
            "background_color": "",
            "chat_icon": "",
            "files": "",
            "input_value": flow_input or "",
            "sender": "User",
            "sender_name": "User",
            "session_id": "",
            "should_store_message": True,
            "text_color": "",
        },
    )
    await set_component_inputs_and_run(
        components["MCP_Connection_Agent_Platform_yenDh"],
        {
            "command": "utils-mcp",
            "env": [],
            "headers_input": "{}",
            "mode": "Stdio",
            "sse_url": "MCP_SSE",
            "tool": "",
            "tool_placeholder": "",
            "tools_metadata": [
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read and return the contents of a text file.",
                    "display_description": "Read and return the contents of a text file.",
                    "display_name": "read_file",
                    "name": "read_file",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_file"],
                },
                {
                    "args": {
                        "dest": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": ".", "title": "Dest"},
                        "path": {"title": "Path", "type": "string"},
                    },
                    "description": "Extract a ZIP archive.",
                    "display_description": "Extract a ZIP archive.",
                    "display_name": "extract_zip",
                    "name": "extract_zip",
                    "readonly": False,
                    "status": False,
                    "tags": ["extract_zip"],
                },
                {
                    "args": {
                        "dest": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": ".", "title": "Dest"},
                        "path": {"title": "Path", "type": "string"},
                    },
                    "description": "Extract a TAR archive.",
                    "display_description": "Extract a TAR archive.",
                    "display_name": "extract_tar",
                    "name": "extract_tar",
                    "readonly": False,
                    "status": False,
                    "tags": ["extract_tar"],
                },
                {
                    "args": {
                        "dest": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": ".", "title": "Dest"},
                        "path": {"title": "Path", "type": "string"},
                    },
                    "description": "Extract a RAR archive.",
                    "display_description": "Extract a RAR archive.",
                    "display_name": "extract_rar",
                    "name": "extract_rar",
                    "readonly": False,
                    "status": False,
                    "tags": ["extract_rar"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read and return text from a PDF file.",
                    "display_description": "Read and return text from a PDF file.",
                    "display_name": "read_pdf",
                    "name": "read_pdf",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_pdf"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read and return text from a Word (.docx) file.",
                    "display_description": "Read and return text from a Word (.docx) file.",
                    "display_name": "read_docx",
                    "name": "read_docx",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_docx"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read a CSV file and return its contents as a list of dictionaries.",
                    "display_description": "Read a CSV file and return its contents as a list of dictionaries.",
                    "display_name": "read_csv",
                    "name": "read_csv",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_csv"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read an Excel file and return its contents as a list of dictionaries.",
                    "display_description": "Read an Excel file and return its contents as a list of dictionaries.",
                    "display_name": "read_excel",
                    "name": "read_excel",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_excel"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read a JSON file and return its contents.",
                    "display_description": "Read a JSON file and return its contents.",
                    "display_name": "read_json",
                    "name": "read_json",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_json"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read a YAML file and return its contents.",
                    "display_description": "Read a YAML file and return its contents.",
                    "display_name": "read_yaml",
                    "name": "read_yaml",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_yaml"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read an INI file and return its contents.",
                    "display_description": "Read an INI file and return its contents.",
                    "display_name": "read_ini",
                    "name": "read_ini",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_ini"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read an XML file and return its contents.",
                    "display_description": "Read an XML file and return its contents.",
                    "display_name": "read_xml",
                    "name": "read_xml",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_xml"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read a Markdown file and return its contents.",
                    "display_description": "Read a Markdown file and return its contents.",
                    "display_name": "read_markdown",
                    "name": "read_markdown",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_markdown"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read an HTML file and return its contents.",
                    "display_description": "Read an HTML file and return its contents.",
                    "display_name": "read_html",
                    "name": "read_html",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_html"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read an audio file and return its metadata.",
                    "display_description": "Read an audio file and return its metadata.",
                    "display_name": "read_audio_metadata",
                    "name": "read_audio_metadata",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_audio_metadata"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Read a video file and return its metadata.",
                    "display_description": "Read a video file and return its metadata.",
                    "display_name": "read_video_metadata",
                    "name": "read_video_metadata",
                    "readonly": False,
                    "status": False,
                    "tags": ["read_video_metadata"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "Return basic information about a file.",
                    "display_description": "Return basic information about a file.",
                    "display_name": "file_info",
                    "name": "file_info",
                    "readonly": False,
                    "status": False,
                    "tags": ["file_info"],
                },
                {
                    "args": {"path": {"title": "Path", "type": "string"}},
                    "description": "List the contents of a directory.",
                    "display_description": "List the contents of a directory.",
                    "display_name": "list_directory",
                    "name": "list_directory",
                    "readonly": False,
                    "status": False,
                    "tags": ["list_directory"],
                },
                {
                    "args": {},
                    "description": "Create And Get the temporary directory.",
                    "display_description": "Create And Get the temporary directory.",
                    "display_name": "get_tmp_dir",
                    "name": "get_tmp_dir",
                    "readonly": False,
                    "status": False,
                    "tags": ["get_tmp_dir"],
                },
                {
                    "args": {
                        "local_tz_override": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": None,
                            "title": "Local Tz Override",
                        }
                    },
                    "description": "",
                    "display_description": "",
                    "display_name": "get_local_tz",
                    "name": "get_local_tz",
                    "readonly": False,
                    "status": False,
                    "tags": ["get_local_tz"],
                },
                {
                    "args": {"timezone_name": {"title": "Timezone Name", "type": "string"}},
                    "description": "",
                    "display_description": "",
                    "display_name": "get_zoneinfo",
                    "name": "get_zoneinfo",
                    "readonly": False,
                    "status": False,
                    "tags": ["get_zoneinfo"],
                },
                {
                    "args": {"timezone_name": {"title": "Timezone Name", "type": "string"}},
                    "description": "",
                    "display_description": "",
                    "display_name": "get_current_time_by_tz",
                    "name": "get_current_time_by_tz",
                    "readonly": False,
                    "status": False,
                    "tags": ["get_current_time_by_tz"],
                },
                {
                    "args": {"timezone_name": {"title": "Timezone Name", "type": "string"}},
                    "description": '\nGet the current time in a specified timezone.\n\nThis function retrieves the current date and time for a given timezone using\nthe `ZoneInfo` module. It also determines whether the current time is in\ndaylight saving time (DST).\n\nArgs:\n    timezone_name (str): The name of the timezone (e.g., "UTC", "America/New_York").\n\nReturns:\n    TimeResult: An object containing:\n        - timezone (str): The name of the timezone.\n        - datetime (str): The current date and time in ISO 8601 format (to seconds).\n        - is_dst (bool): Whether the current time is in daylight saving time (DST).\n',
                    "display_description": '\nGet the current time in a specified timezone.\n\nThis function retrieves the current date and time for a given timezone using\nthe `ZoneInfo` module. It also determines whether the current time is in\ndaylight saving time (DST).\n\nArgs:\n    timezone_name (str): The name of the timezone (e.g., "UTC", "America/New_York").\n\nReturns:\n    TimeResult: An object containing:\n        - timezone (str): The name of the timezone.\n        - datetime (str): The current date and time in ISO 8601 format (to seconds).\n        - is_dst (bool): Whether the current time is in daylight saving time (DST).\n',
                    "display_name": "get_current_time",
                    "name": "get_current_time",
                    "readonly": False,
                    "status": True,
                    "tags": ["get_current_time"],
                },
                {
                    "args": {
                        "source_tz": {"title": "Source Tz", "type": "string"},
                        "target_tz": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": "UTC",
                            "title": "Target Tz",
                        },
                        "time_str": {"title": "Time Str", "type": "string"},
                    },
                    "description": '\nConverts a given datetime string from a source timezone to a target timezone.\n\nArgs:\n    source_tz (str): The IANA name of the source timezone (e.g., "Asia/Jerusalem").\n    time_str (str): The time string in "%Y-%m-%dT%H:%M:%S" format (e.g., "2025-04-16T15:00:00").\n    target_tz (str, optional): The IANA name of the target timezone. Defaults to "UTC".\n\nReturns:\n    TimeConversionResult: A structured object containing the converted time in both source and target timezones,\n                          DST info, and the time difference between them.\n',
                    "display_description": '\nConverts a given datetime string from a source timezone to a target timezone.\n\nArgs:\n    source_tz (str): The IANA name of the source timezone (e.g., "Asia/Jerusalem").\n    time_str (str): The time string in "%Y-%m-%dT%H:%M:%S" format (e.g., "2025-04-16T15:00:00").\n    target_tz (str, optional): The IANA name of the target timezone. Defaults to "UTC".\n\nReturns:\n    TimeConversionResult: A structured object containing the converted time in both source and target timezones,\n                          DST info, and the time difference between them.\n',
                    "display_name": "convert_time_between_timezones",
                    "name": "convert_time_between_timezones",
                    "readonly": False,
                    "status": True,
                    "tags": ["convert_time_between_timezones"],
                },
                {
                    "args": {
                        "delta_seconds": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "default": 7200,
                            "title": "Delta Seconds",
                        },
                        "time_format": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": "%Y-%m-%dT%H:%M:%S%z",
                            "title": "Time Format",
                        },
                        "time_str": {"title": "Time Str", "type": "string"},
                    },
                    "description": '\nGenerates a time window around a given timestamp.\n\nArgs:\n    time_str (str): The base timestamp as a string in time_format format (e.g., "2025-04-16T15:00:00+0000").\n    delta_seconds (int | str, optional): The number of seconds before and after the timestamp to include.\n                                           Default to 7200 (2 hours).\n    time_format (str, optional): The format of the input and output datetime strings.\n                                 Defaults to "%Y-%m-%dT%H:%M:%S%z".\n\nReturns:\n    Tuple[str, str]: A tuple of (start_time, end_time), both formatted according to time_format.\n',
                    "display_description": '\nGenerates a time window around a given timestamp.\n\nArgs:\n    time_str (str): The base timestamp as a string in time_format format (e.g., "2025-04-16T15:00:00+0000").\n    delta_seconds (int | str, optional): The number of seconds before and after the timestamp to include.\n                                           Default to 7200 (2 hours).\n    time_format (str, optional): The format of the input and output datetime strings.\n                                 Defaults to "%Y-%m-%dT%H:%M:%S%z".\n\nReturns:\n    Tuple[str, str]: A tuple of (start_time, end_time), both formatted according to time_format.\n',
                    "display_name": "get_time_range_around_timestamp",
                    "name": "get_time_range_around_timestamp",
                    "readonly": False,
                    "status": True,
                    "tags": ["get_time_range_around_timestamp"],
                },
                {
                    "args": {
                        "date_str": {"title": "Date Str", "type": "string"},
                        "output_format": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": "%Y-%m-%dT%H:%M:%S%z",
                            "title": "Output Format",
                        },
                        "timezone": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "default": "UTC",
                            "title": "Timezone",
                        },
                    },
                    "description": '\nConverts a date string into a full-day time range (00:00:00 to 23:59:59) in the specified timezone.\n\nArgs:\n    date_str (str): The date string in "%Y-%m-%d" format (e.g., "2025-04-16").\n    timezone (str, optional): The IANA timezone name. Defaults to "UTC".\n    output_format (str, optional): The format of the returned datetime strings.\n                                   Defaults to "%Y-%m-%dT%H:%M:%S%z".\n\nReturns:\n    Tuple[str, str]: A tuple of (start_of_day, end_of_day) in the specified timezone and format.\n',
                    "display_description": '\nConverts a date string into a full-day time range (00:00:00 to 23:59:59) in the specified timezone.\n\nArgs:\n    date_str (str): The date string in "%Y-%m-%d" format (e.g., "2025-04-16").\n    timezone (str, optional): The IANA timezone name. Defaults to "UTC".\n    output_format (str, optional): The format of the returned datetime strings.\n                                   Defaults to "%Y-%m-%dT%H:%M:%S%z".\n\nReturns:\n    Tuple[str, str]: A tuple of (start_of_day, end_of_day) in the specified timezone and format.\n',
                    "display_name": "get_full_day_time_range_from_date",
                    "name": "get_full_day_time_range_from_date",
                    "readonly": False,
                    "status": True,
                    "tags": ["get_full_day_time_range_from_date"],
                },
                {
                    "args": {"text": {"title": "Text", "type": "string"}},
                    "description": "Detect the language of a given text.",
                    "display_description": "Detect the language of a given text.",
                    "display_name": "detect_language",
                    "name": "detect_language",
                    "readonly": False,
                    "status": True,
                    "tags": ["detect_language"],
                },
                {
                    "args": {"app_name": {"title": "App Name", "type": "string"}},
                    "description": "\nCheck if the given name is a valid application.\n",
                    "display_description": "\nCheck if the given name is a valid application.\n",
                    "display_name": "check_if_valid_application",
                    "name": "check_if_valid_application",
                    "readonly": False,
                    "status": True,
                    "tags": ["check_if_valid_application"],
                },
            ],
            "input_value": flow_input or "",
        },
    )
    await set_component_inputs_and_run(
        components["JSONCleaner_Yap5Q"],
        {
            "json_str": components["ChatInput_Gywma"].message.value,
            "normalize_unicode": True,
            "remove_control_chars": True,
            "validate_json": True,
        },
    )
    await set_component_inputs_and_run(
        components["StructuredOutput_teP6p"],
        {
            "llm": components["AzureOpenAIModel_FJjEQ"].model_output.value,
            "input_value": "",
            "multiple": True,
            "output_schema": [
                {
                    "description": "The EXACT & FULL comment argument from the input message",
                    "multiple": "False",
                    "name": "comment",
                    "type": "str",
                },
                {
                    "description": "The EXACT & FULL is_missing argument from the input message. If it is not provided, determine whether the comment indicates that the user is requesting missing data. ",
                    "name": "is_missing",
                    "type": "bool",
                },
                {"description": '"MISSING_DATA" if is_missing is True, else "RESULT"', "name": "status", "type": "str"},
            ],
            "schema_name": "",
            "system_prompt": "You are an AI system designed to extract structured information from unstructured text, and format a json represents final response of an agent. Given the input_text, return a JSON object with predefined keys based on the expected structure. Extract values accurately and format them according to the specified type (e.g., string, integer, float, date).If a value is missing or cannot be determined, return a default (e.g., null, 0, or 'N/A'). If multiple instances of the expected structure exist within the input_text, stream each as a separate JSON object.",
        },
    )
    await set_component_inputs_and_run(
        components["CustomComponent_PIDyq"],
        {
            "input_value": components["JSONCleaner_Yap5Q"].output.value,
        },
    )
    await set_component_inputs_and_run(
        components["CustomComponent_ukXWb"],
        {
            "input_value": components["JSONCleaner_Yap5Q"].output.value,
        },
    )
    await set_component_inputs_and_run(
        components["CustomComponent_Uygmo"],
        {
            "structured_data": components["StructuredOutput_teP6p"].structured_output.value,
            "agent_output": "",
            "sep": "\n",
        },
    )
    await set_component_inputs_and_run(
        components["AzureOpenAIModel_pGIWl"],
        {
            "input_value": components["CustomComponent_PIDyq"].output.value,
            "api_key": "",
            "api_version": "2024-10-01-preview",
            "azure_deployment": "gpt-4o-2024-08-06",
            "azure_endpoint": env_values.get("AZURE_OPENAI_ENDPOINT", ""),
            "max_tokens": "",
            "stream": False,
            "system_message": 'You are a ticket router responsible for analyzing support tickets and determining if they should be processed. Your task is to classify the ticket category and decide whether processing is needed.\n\n## Your Output Format\nReturn a JSON object with exactly these fields:\n```json\n{\n  "category": "string - the ticket category or \'NOT_SUPPORTED\'",\n  "should_process": true/false,\n}\n```\n\n## Step 1: Classify the Ticket Category\n\n### Supported Categories:\n- **"ACCESS_CONNECTIVITY"** - Any network or connectivity issues, access permissions, authentication/login failures, VPN or remote access issues, etc.\n\n### Classification Rules:\n- If the ticket matches a supported category → Use the category name\n- If the ticket doesn\'t match any supported category → Use "NOT_SUPPORTED" and set should_process to false\n\n## Step 2: Analyze Comments and Decide Processing\n**Only proceed with this step if you assigned a supported category in Step 1.**\n\n### Comment Analysis Guidelines:\n- Comments are listed **NEWEST FIRST** (most recent at the top)\n- Read chronologically to understand the conversation flow\n- Identify who wrote each comment (user, AI agent, admin, etc.)\n- Track what information has been requested and provided\n\n### Processing Decision Rules:\n\n**✅ SET should_process to TRUE when:**\n- This appears to be a new ticket with no previous AI investigation\n- User provided new technical information after AI requested it\n- User gave specific technical details (IP addresses, timestamps, error messages, logs, etc.)\n- AI asked for information and user provided a substantive response\n\n**❌ SET should_process to FALSE when:**\n- AI already investigated AND provided recommendations AND the most recent update is just administrative follow-up\n- The most recent user comment contains only:\n  - File attachments without explanatory text\n  - Generic phrases like "thanks", "please check", "any updates?", "check again"\n  - Administrative acknowledgments without technical content\n  - Information that duplicates what was already addressed\n\n### Key Decision Points:\n- **When in doubt, choose to process** - it\'s better to over-process than miss important tickets\n\n## Examples:\n\n**Example 1 - Should Process:**\n```json\n{\n  "category": "ACCESS_CONNECTIVITY",\n  "should_process": true\n}\n```\n\n**Example 2 - Should Not Process:**\n```json\n{\n  "category": "ACCESS_CONNECTIVITY", \n  "should_process": false\n}\n```\n\n**Example 3 - Not Supported:**\n```json\n{\n  "category": "NOT_SUPPORTED",\n  "should_process": false\n}\n```',
            "temperature": 0,
        },
    )
    await set_component_inputs_and_run(
        components["MCP_Connection_Agent_Platform_05d3E"],
        {
            "headers_input": components["CustomComponent_ukXWb"].output.value,
            "command": "uvx mcp-server-fetch",
            "env": [],
            "mode": "SSE",
            "sse_url": env_values.get("S1C_KQL_MCP_SSE", ""),
            "tool": "",
            "tool_placeholder": "",
            "tools_metadata": [
                {
                    "args": {
                        "end_time": {"title": "End Time", "type": "string"},
                        "start_time": {"title": "Start Time", "type": "string"},
                        "user_name": {"title": "User Name", "type": "string"},
                    },
                    "description": "Fetch user Active Directory (AD) groups information based on its last login event from logs.\n   This tool is useful for determining which Active Directory (AD) groups a user belongs to, helping assess whether specific rules apply to them. Use it only when the rulebase output includes references to AD groups.\n\nArgs:\n    user_name (str): The name of the user whose group information is being queried.\n    start_time (str): The start time for the query in ISO 8601 format (UTC time).\n    end_time (str): The end time for the query in ISO 8601 format (UTC time).\n\nReturns:\n    dict: A dictionary containing the user's active directory groups information and metadata.\n",
                    "display_description": "Fetch user Active Directory (AD) groups information based on its last login event from logs.\n   This tool is useful for determining which Active Directory (AD) groups a user belongs to, helping assess whether specific rules apply to them. Use it only when the rulebase output includes references to AD groups.\n\nArgs:\n    user_name (str): The name of the user whose group information is being queried.\n    start_time (str): The start time for the query in ISO 8601 format (UTC time).\n    end_time (str): The end time for the query in ISO 8601 format (UTC time).\n\nReturns:\n    dict: A dictionary containing the user's active directory groups information and metadata.\n",
                    "display_name": "fetch_user_active_directory_groups_information",
                    "name": "fetch_user_active_directory_groups_information",
                    "readonly": False,
                    "status": True,
                    "tags": ["fetch_user_active_directory_groups_information"],
                },
                {
                    "args": {
                        "destination_ip": {"title": "Destination Ip", "type": "string"},
                        "end_time": {"title": "End Time", "type": "string"},
                        "service": {"title": "Service", "type": "string"},
                        "source_ip": {"title": "Source Ip", "type": "string"},
                        "start_time": {"title": "Start Time", "type": "string"},
                        "user_name": {"title": "User Name", "type": "string"},
                    },
                    "description": "\nFetch user block event details from firewall logs, including policy name, rule name, rule number, machine name, and rulebase name.\n\nArgs:\n    user_name (str): The name of the user to query block events for.\n    source_ip (IPvAnyAddress): The source IP address involved in the block event.\n    destination_ip (IPvAnyAddress): The destination IP address involved in the block event.\n    start_time (str): The start time of the issue query window, in ISO 8601 format (UTC time).\n    end_time (str): The end time of the issue query window, in ISO 8601 format (UTC time).\n    service (str | int): The service (name or port number) to filter block events by. only one of them is needed!\n\nReturns:\n    dict: A dictionary containing block event information matching the specified criteria.\n",
                    "display_description": "\nFetch user block event details from firewall logs, including policy name, rule name, rule number, machine name, and rulebase name.\n\nArgs:\n    user_name (str): The name of the user to query block events for.\n    source_ip (IPvAnyAddress): The source IP address involved in the block event.\n    destination_ip (IPvAnyAddress): The destination IP address involved in the block event.\n    start_time (str): The start time of the issue query window, in ISO 8601 format (UTC time).\n    end_time (str): The end time of the issue query window, in ISO 8601 format (UTC time).\n    service (str | int): The service (name or port number) to filter block events by. only one of them is needed!\n\nReturns:\n    dict: A dictionary containing block event information matching the specified criteria.\n",
                    "display_name": "fetch_block_event",
                    "name": "fetch_block_event",
                    "readonly": False,
                    "status": True,
                    "tags": ["fetch_block_event"],
                },
            ],
        },
    )
    await set_component_inputs_and_run(
        components["MCP_Connection_Agent_Platform_v2Dkx"],
        {
            "headers_input": components["CustomComponent_ukXWb"].output.value,
            "command": "uvx mcp-server-fetch",
            "env": [],
            "mode": "SSE",
            "sse_url": env_values.get("S1C_API_MCP_SSE", ""),
            "tool": "",
            "tool_placeholder": "",
            "tools_metadata": [
                {
                    "args": {
                        "destination_ip": {"title": "Destination Ip", "type": "string"},
                        "rulebase_name": {"title": "Rulebase Name", "type": "string"},
                    },
                    "description": "\nAnalyzes a specified firewall rulebase to identify all users, groups, and access roles that are permitted to access a given destination IP address.\nThe function scans relevant rules where the destination IP appears and extracts the associated entities defined in the source criteria of those rules.\nUseful for access validation, troubleshooting, and rulebase auditing.\n\nArgs:\n    ip_address (IPvAnyAddress): The destination IP address to evaluate.\n    rulebase_name (str): The name of the rulebase to search within.\n\nReturns:\n    dict: A dictionary containing detailed information about matching rules, access roles, groups, and users.\n",
                    "display_description": "\nAnalyzes a specified firewall rulebase to identify all users, groups, and access roles that are permitted to access a given destination IP address.\nThe function scans relevant rules where the destination IP appears and extracts the associated entities defined in the source criteria of those rules.\nUseful for access validation, troubleshooting, and rulebase auditing.\n\nArgs:\n    ip_address (IPvAnyAddress): The destination IP address to evaluate.\n    rulebase_name (str): The name of the rulebase to search within.\n\nReturns:\n    dict: A dictionary containing detailed information about matching rules, access roles, groups, and users.\n",
                    "display_name": "get_entities_with_access_to_dest_ip_in_rulebase",
                    "name": "get_entities_with_access_to_dest_ip_in_rulebase",
                    "readonly": False,
                    "status": True,
                    "tags": ["get_entities_with_access_to_dest_ip_in_rulebase"],
                }
            ],
        },
    )
    await set_component_inputs_and_run(
        components["ChatOutput_vUTI9"],
        {
            "input_value": components["CustomComponent_Uygmo"].output.value,
            "background_color": "",
            "chat_icon": "",
            "clean_data": True,
            "data_template": "{text}",
            "sender": "Machine",
            "sender_name": "AI",
            "session_id": "",
            "should_store_message": True,
            "text_color": "",
        },
    )
    await set_component_inputs_and_run(
        components["ConditionalRouter_wUszV"],
        {
            "input_text": components["AzureOpenAIModel_pGIWl"].text_output.value,
            "message": components["CustomComponent_PIDyq"].output.value,
            "case_sensitive": False,
            "default_route": "false_result",
            "match_text": '"should_process": true',
            "max_iterations": 10,
            "operator": "contains",
        },
    )
    await set_component_inputs_and_run(
        components["StructuredOutput_3eYS1"],
        {
            "input_value": components["ConditionalRouter_wUszV"].true_result.value,
            "llm": components["AzureOpenAIModel_T1QUR"].model_output.value,
            "multiple": True,
            "output_schema": [
                {
                    "description": "The name of the user who reported the issue",
                    "multiple": "False",
                    "name": "reporter_user",
                    "type": "str",
                },
                {
                    "description": "The IP address from which the connection was initiated",
                    "name": "source_ip",
                    "type": "str",
                },
                {
                    "description": "The target resource the user attempted to reach (url / ip address / application)",
                    "name": "target_resource",
                    "type": "str",
                },
                {
                    "description": "The service name (e.g., HTTPS, SSH, FTP) OR the corresponding port number (e.g., 443, 22, 21) that the USER is trying to access",
                    "name": "service",
                    "type": "str",
                },
                {
                    "description": "The time or time range when the user-reported issue occurred (latest provided), NOT the ticket creation time.",
                    "name": "time_issue_happened",
                    "type": "str",
                },
                {
                    "description": 'The timezone of the user who created the ticket, if not provided, set as "UNKNOWN"',
                    "name": "timezone",
                    "type": "str",
                },
                {
                    "description": "Any error output the user received during the failed connection attempt",
                    "name": "error_message",
                    "type": "str",
                },
                {
                    "description": "Detect the user’s language from the ticket comments. If unclear, set English",
                    "name": "user_language",
                    "type": "str",
                },
                {
                    "description": "The name of the user who experienced the issue",
                    "name": "user_experienced_issue",
                    "type": "str",
                },
                {"description": "comments part from the input ticket details", "name": "comments", "type": "str"},
            ],
            "schema_name": "",
            "system_prompt": 'You are an AI system designed to extract structured information from unstructured text, especially an expert for HelpDesk tickets.\nGiven the input_text, return a JSON object with predefined keys based on the expected structure.Extract values accurately and format them according to the specified type (e.g., string, integer, float, date).If a value is missing or cannot be determined, return "UNKNOWN". If multiple instances of the expected structure exist within the input_text, stream each as a separate JSON object.\n\n1. Analyze the ticket details and the comments chronologically:\n- Read the comments section carefully (Note: Comments are ordered with NEWEST FIRST)\n- For each comment, identify: Who wrote it (user, AI agent, admin, etc.), What they said/asked/provided, When it was written\n- Understand the conversation flow and what has already happened\n\nNote that each comment follows one of the following patterns:\nA. [comment timestamp in format  YYYY-MM-DD HH:MM:SS] - [username] ([optional label]) [COMMENT TEXT]\nFor example:\n2025-06-05 08:59:20 - alex w (Additional comments)\\n This is my comment\n\nOR\n\nB. comment in a json format:\n{\n  "$schema": "http://json-schema.org/draft-07/schema#",\n  "title": "CommentUpdate",\n  "type": "object",\n  "properties": {\n    "updateAuthor": {\n      "type": "object",\n      "properties": {\n        "displayName": { "type": "string" },\n        "accountId": { "type": "string" },\n        "emailAddress": { "type": "string", "format": "email" }\n      },\n      "required": ["displayName", "accountId", "emailAddress"]\n    },\n    "comment": {\n      "type": "object",\n      "properties": {\n        "type": { "type": "string", "enum": ["doc"] },\n        "version": { "type": "integer" },\n        "content": {\n          "type": "array",\n          "items": {\n            "type": "object",\n            "properties": {\n              "type": { "type": "string" },\n              "content": {\n                "type": "array",\n                "items": {\n                  "type": "object",\n                  "properties": {\n                    "type": { "type": "string" },\n                    "text": { "type": "string" },\n                    "marks": {\n                      "type": "array",\n                      "items": {\n                        "type": "object",\n                        "properties": {\n                          "type": { "type": "string" }\n                        },\n                        "required": ["type"]\n                      },\n                      "nullable": true\n                    }\n                  },\n                  "required": ["type"],\n                  "additionalProperties": false\n                }\n              }\n            },\n            "required": ["type", "content"],\n            "additionalProperties": false\n          }\n        }\n      },\n      "required": ["type", "version", "content"]\n    },\n    "updated": {\n      "type": "string",\n      "format": "date-time"\n    }\n  },\n  "required": ["updateAuthor", "comment", "updated"]\n}\n\n**Pay attention to the difference between the ticket/comment timestamp and the actual time the reported issue happened.**\n\n2. Extract relevant information from the ticket:\n•\tExtract values accurately and format them according to the specified type (e.g., string, integer, float, date).\n•\tIf a value is missing or cannot be determined, do NOT return it.\n•\tUse both the general ticket fields and the comment section (Note: Comments are ordered with NEWEST FIRST).\n•\tIn case of multiple inputs for the same argument are available—always proceed with the most RECENT provided.\n\n',
        },
    )
    await set_component_inputs_and_run(
        components["ChatOutput_XjvrW"],
        {
            "input_value": components["ConditionalRouter_wUszV"].false_result.value,
            "background_color": "",
            "chat_icon": "",
            "clean_data": True,
            "data_template": "{text}",
            "sender": "Machine",
            "sender_name": "AI",
            "session_id": "",
            "should_store_message": True,
            "text_color": "",
        },
    )
    await set_component_inputs_and_run(
        components["ParserComponent_oMgqW"],
        {
            "input_data": components["StructuredOutput_3eYS1"].structured_output.value,
            "mode": "Parser",
            "pattern": "{results[0]}",
            "sep": "\n",
        },
    )
    await set_component_inputs_and_run(
        components["Agent_mFimM"],
        {
            "input_value": components["ParserComponent_oMgqW"].parsed_text.value,
            "tools": components["MCP_Connection_Agent_Platform_yenDh"].component_as_tool.value,
            "add_current_date_tool": True,
            "agent_description": "A helpful assistant with access to the following tools:",
            "agent_llm": "Azure OpenAI",
            "api_key": "",
            "api_version": "2024-10-01-preview",
            "azure_deployment": "gpt-4o-2024-08-06",
            "azure_endpoint": env_values.get("AZURE_OPENAI_ENDPOINT", ""),
            "handle_parsing_errors": True,
            "max_iterations": 15,
            "max_tokens": "",
            "memory": "",
            "n_messages": 100,
            "order": "Ascending",
            "sender": "Machine and User",
            "sender_name": "",
            "session_id": "",
            "system_prompt": 'You are a Network Troubleshooting AI Agent designed to assist with Help Desk tickets related to network connectivity and access issues.\nYou will receive an Help Desk ticket details, including comments section. \nYour our task is to analyze the ticket data using the following steps, and return the result:\n\n1. Analyze the ticket details and the comments chronologically (Note: Comments are ordered with NEWEST FIRST).\n\n2.\tReview Available Tools and Plan the Investigation:\n\t•\tBegin by examining your available tools, their expected inputs, and their expected output arguments.\n\t•\tBased on the ticket information and potential information collecting from your tools, plan how you will use the tools to collect the necessary data for the investigation.\n\t•\tNote that the output of one tool can serve as the input for another tool.\n\n3. Input Validation and Time Handling:\nBased on your plan, check if you have ALL the relevant data you need for executing the tools, for example source ip, destination resource, service, time connection issue happened, user experienced the issue, etc.\nIn case of multiple inputs for the same argument are available—always proceed with the most recent provided.\n\nTarget resource:\nTry to understand whether the target_resource represents an application name, a resource URL, or an IP address. To verify a potential application name, use the check_if_valid_application tool.\n\nTime Handling:\nThe time_issue_happened argument is CRITICAL for querying logs. If not provided EXPLICIT in comments, you should ask this data from the user. If provided handle it as follows:\n\t•\tIf timezone is "UNKNOWN", assume the time_issue_happened is in UTC (+00:00), then calculate a ±1-day time range around it.\n\t•\tElse, if timezone is provided, first CONVERT time issue happened to UTC, then calculate a ±2-hour time range.\n⚠️ **timezone** argument is OPTIONAL! If not provided, handle it as described below.\n\nIf you have ALL the needed data, continue to the next steps. NO NEED CONFIRMATION FOR PARAMS.\nElse, If any required data is MISSING, respond with the following JSON string structure. The list of missing keys should be dynamically generated. Again, only for missing data, DO NOT ask thee user to confirm data!\nAnswer in the user\'s language, if language is not provided, use the detect_language tool to identify it. If tool result is ambiguous or uncertain, default to responding in English.\nResponse JSON string structure in case of missing required data, again - ONLY if these are needed parameters and you cannot proceed without them:\n```json\n{\n"comment" : "To proceed with the investigation, we’ll need the following details:\n\n* [missing key 1]\n* [missing key 2]\n* [missing key 3]\n(continue for any additional missing keys)\n\nWould you like assistance in gathering this information?",\n"is_missing" : True,\n}\n```\n\n4. Investigate the ticket USING AVAILABLE TOOLS:\n\t•\tStart by using log analysis tools to examine traffic activity. Extract key details such as drop reason, matched rule, traffic direction, action taken, and rulebase information.\n\t•\tThen, based on logs output findings (rulebase name & number), use firewall rulebase analysis tools to investigate the rulebase configuration. Determine why the traffic was blocked or denied, considering factors such as missing or incorrect rules, missing user in relevant source group or network.\n\t•\tBased on the rulebase output findings,  and if rulebase contains reference to AD groups - use a log analysis tool to identify the user\'s Active Directory (AD) groups and correlate this information with the data defined in the rulebase.\n\n5. Summarize Findings and Provide a Recommendations:\nBriefly explain the key findings from your investigation—what was checked, and the outcomes (e.g., the matched rule and its number, missing permissions, user-group mismatches), provide the full log record that was detected (drop/accept).\nThen, based on these findings, clearly state the specific rule or configuration causing the issue (if identified), and recommend concise actions to resolve it—such as adding the user to an existing rule, adding a new rule if needed, etc.\n\n6. Ask for confirmation:\nEnd with a polite and short question asking if the recommendation resolves the issue and if further assistance is needed.\nAnswer in the user\'s language, if language is not provided, use the detect_language tool to identify it. If tool result is ambiguous or uncertain, default to responding in English.\n\nReturn an answer with a JSON string structure similar to the example below:\n```json\n{ \n"comment" : {investigation findings and recommendations (only!)},\n"is_missing": False,\n}\n```\n\n7. Return JSON string response\n\n**Guidelines**:\n \t•  Make sure you followed ALL the steps before responding!\n\t•  Do not fabricate results! If data is missing or unclear, mention it explicitly and suggest next steps for further investigation. Answer concisely and directly.\n\t•  Keep your responses natural, clear and concise.\n\t•  DO NOT ask the user to confirm information!\n\t•  Respond in JSON string format, check yourself before responding.',
            "temperature": 0,
            "template": "{sender_name}: {text}",
            "verbose": True,
        },
    )
    await set_component_inputs_and_run(
        components["CustomComponent_duEs3"],
        {
            "input_value": components["Agent_mFimM"].response.value,
        },
    )
    await set_component_inputs_and_run(
        components["ChatOutput_yjAvZ"],
        {
            "input_value": components["CustomComponent_duEs3"].output.value,
            "background_color": "",
            "chat_icon": "",
            "clean_data": True,
            "data_template": "{text}",
            "sender": "Machine",
            "sender_name": "AI",
            "session_id": "",
            "should_store_message": True,
            "text_color": "",
        },
    )

    # Collect results from output nodes
    results["outputs"]["ChatOutput_XjvrW.message"] = components["ChatOutput_XjvrW"].message
    results["outputs"]["ChatOutput_vUTI9.message"] = components["ChatOutput_vUTI9"].message
    results["outputs"]["ChatOutput_yjAvZ.message"] = components["ChatOutput_yjAvZ"].message
    results["components"] = {
        node_id: {
            "id": component._id,
            "description": component.description,
            "display_name": component.display_name,
            "name": component.name,
            "trace_name": component.trace_name,
            "trace_type": component.trace_type,
            "outputs": component.outputs,
            "inputs": component.inputs,
        }
        for node_id, component in components.items()
    }
    return results


def print_results_as_json(results):
    def convert_data_to_dict(data):
        if isinstance(data, dict):
            return {k: convert_data_to_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [convert_data_to_dict(item) for item in data]
        elif hasattr(data, "dict"):
            return data.dict()
        elif hasattr(data, "to_dict"):
            return data.to_dict()
        elif hasattr(data, "to_json"):
            return json.loads(data.to_json())
        else:
            return data

    results = convert_data_to_dict(results)
    print(json.dumps(results, default=str, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the ticket_enrichment flow")
    parser.add_argument("--flow-input", type=str, default="", help="Input for the flow")
    parser.add_argument("--session-id", type=str, default=str(uuid4()), help="Session ID for the flow")
    parser.add_argument("--user-id", type=str, default=None, help="User ID for the flow")
    parser.add_argument("--flow-name", type=str, default=None, help="Flow name")
    parser.add_argument("--flow-id", type=str, default=None, help="Flow ID")
    args = parser.parse_args()
    result = asyncio.run(run(**vars(args)))
