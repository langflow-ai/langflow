"""PraisonAI Task Component for Langflow.

Defines a task to be executed by a PraisonAI Agent with full output,
guardrails, and workflow support.
"""

from __future__ import annotations

from typing import Any

from lfx.base.agents.praisonai import convert_tools
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FileInput,
    HandleInput,
    IntInput,
    MultilineInput,
    Output,
)


class PraisonAITaskComponent(Component):
    """PraisonAI Task component for Langflow workflows.

    Defines a task with description, expected output, structured output,
    and optional agent assignment. Supports workflow branching with
    decision and loop task types.
    """

    display_name: str = "PraisonAI Task"
    description: str = "Define a task with structured output, guardrails, and workflow support."
    documentation: str = "https://docs.praison.ai/docs/integrations/langflow"
    icon: str = "PraisonAI"
    name: str = "PraisonAI Task"

    inputs = [
        # ============================================================
        # TASK IDENTITY
        # ============================================================
        MultilineInput(
            name="name",
            display_name="Task Name",
            info="Name for identification.",
            value="Task",
        ),
        MultilineInput(
            name="description",
            display_name="Description",
            info="Detailed description of what the task should accomplish.",
            value="Complete the assigned task.",
        ),
        MultilineInput(
            name="expected_output",
            display_name="Expected Output",
            info="Description of the expected output format or content.",
            value="A comprehensive response.",
        ),
        # ============================================================
        # AGENT ASSIGNMENT
        # ============================================================
        HandleInput(
            name="agent",
            display_name="Agent",
            info="The agent responsible for executing this task.",
            input_types=["Agent"],
        ),
        # ============================================================
        # STRUCTURED OUTPUT
        # ============================================================
        MultilineInput(
            name="output_json",
            display_name="Output JSON Schema",
            info="JSON schema for structured output. Agent will return data matching this schema.",
            advanced=True,
        ),
        MultilineInput(
            name="output_file",
            display_name="Output File",
            info="File path to save task output.",
            advanced=True,
        ),
        BoolInput(
            name="create_directory",
            display_name="Create Directory",
            info="Create parent directories if output file path doesn't exist.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # FILE INPUT
        # ============================================================
        FileInput(
            name="input_file",
            display_name="Input File",
            info="Input file for the task to process.",
            file_types=["pdf", "txt", "md", "csv", "json", "docx", "xlsx"],
            advanced=True,
        ),
        HandleInput(
            name="images",
            display_name="Images",
            info="Images for multimodal task processing.",
            input_types=["Image", "str"],
            is_list=True,
            advanced=True,
        ),
        # ============================================================
        # CONTEXT
        # ============================================================
        HandleInput(
            name="context",
            display_name="Context Tasks",
            info="Other tasks whose outputs provide context for this task.",
            input_types=["Task"],
            is_list=True,
            advanced=True,
        ),
        BoolInput(
            name="retain_full_context",
            display_name="Retain Full Context",
            info="Use all previous task outputs, not just the immediate previous task.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # TOOLS
        # ============================================================
        HandleInput(
            name="tools",
            display_name="Tools",
            info="Tools available specifically for this task.",
            input_types=["Tool", "BaseTool"],
            is_list=True,
            advanced=True,
        ),
        # ============================================================
        # GUARDRAILS & VALIDATION
        # ============================================================
        BoolInput(
            name="guardrail",
            display_name="Guardrail",
            info="Enable output validation for this task.",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="Maximum retry attempts if task fails or validation fails.",
            value=3,
            advanced=True,
        ),
        BoolInput(
            name="quality_check",
            display_name="Quality Check",
            info="Enable quality metrics collection for task output.",
            value=True,
            advanced=True,
        ),
        # ============================================================
        # EXECUTION OPTIONS
        # ============================================================
        BoolInput(
            name="async_execution",
            display_name="Async Execution",
            info="Execute this task asynchronously.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="rerun",
            display_name="Rerun",
            info="Allow task to be re-executed.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # WORKFLOW (Decision/Loop)
        # ============================================================
        DropdownInput(
            name="task_type",
            display_name="Task Type",
            info="Type of task: regular task, decision point, or loop.",
            options=["task", "decision", "loop"],
            value="task",
            advanced=True,
        ),
        DictInput(
            name="condition",
            display_name="Condition",
            info="Branching conditions for decision tasks (e.g., {'approved': ['task_a'], 'rejected': ['task_b']}).",
            advanced=True,
        ),
        MultilineInput(
            name="next_tasks",
            display_name="Next Tasks",
            info="Task names to execute after this task (comma-separated for workflow routing).",
            advanced=True,
        ),
        BoolInput(
            name="is_start",
            display_name="Is Start Task",
            info="Mark this as the starting task in a workflow.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # VARIABLES
        # ============================================================
        DictInput(
            name="variables",
            display_name="Variables",
            info="Variables for substitution in description (e.g., {'topic': 'AI'} replaces {topic}).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Task",
            name="task",
            method="build_task",
        ),
    ]

    def _import_task(self):
        """Import Task class with proper error handling."""
        try:
            from praisonaiagents import Task
        except ImportError as e:
            msg = "PraisonAI Agents is not installed. Install with: pip install praisonaiagents"
            raise ImportError(msg) from e
        else:
            return Task

    def _parse_output_json(self):
        """Parse JSON schema string into a Pydantic model if provided."""
        if not self.output_json:
            return None

        try:
            import json
            from typing import Any

            from pydantic import create_model

            schema = json.loads(self.output_json)

            # Create a dynamic Pydantic model from the schema
            if isinstance(schema, dict):
                # Simple field definitions: {"field_name": "type"}
                field_definitions = {}
                type_mapping = {
                    "str": str,
                    "string": str,
                    "int": int,
                    "integer": int,
                    "float": float,
                    "number": float,
                    "bool": bool,
                    "boolean": bool,
                    "list": list,
                    "array": list,
                    "dict": dict,
                    "object": dict,
                }

                for field_name, field_type in schema.items():
                    if isinstance(field_type, str):
                        py_type = type_mapping.get(field_type.lower(), Any)
                        field_definitions[field_name] = (py_type, ...)
                    else:
                        field_definitions[field_name] = (Any, ...)

                if field_definitions:
                    return create_model("TaskOutputModel", **field_definitions)

        except json.JSONDecodeError:
            # If parsing fails, return None and let task use default
            return None

        return None

    def build_task(self) -> Any:
        """Build and return the PraisonAI Task instance."""
        task_class = self._import_task()

        # Convert tools if provided
        tools = convert_tools(self.tools) if self.tools else None

        # Build context from connected tasks
        context = None
        if self.context:
            context = [t for t in self.context if t is not None]
            if not context:
                context = None

        # Parse output JSON schema
        output_json = self._parse_output_json()

        # Parse next_tasks
        next_tasks = None
        if self.next_tasks:
            next_tasks = [t.strip() for t in self.next_tasks.split(",") if t.strip()]

        # Parse images
        images = None
        if self.images:
            images = [img for img in self.images if img is not None]
            if not images:
                images = None

        # Build task kwargs
        kwargs = {
            "name": self.name,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent": self.agent,
            "tools": tools if tools else [],
            "context": context if context else [],
            "async_execution": self.async_execution,
            "quality_check": self.quality_check,
            "max_retries": self.max_retries,
            "rerun": self.rerun,
            "retain_full_context": self.retain_full_context,
        }

        # Add optional parameters
        if output_json:
            kwargs["output_json"] = output_json

        if self.output_file:
            kwargs["output_file"] = self.output_file
            kwargs["create_directory"] = self.create_directory

        if self.input_file:
            kwargs["input_file"] = self.input_file

        if images:
            kwargs["images"] = images

        if self.guardrail:
            kwargs["guardrail"] = True

        if self.task_type and self.task_type != "task":
            kwargs["task_type"] = self.task_type

        if self.condition:
            kwargs["condition"] = self.condition

        if next_tasks:
            kwargs["next_tasks"] = next_tasks

        if self.is_start:
            kwargs["is_start"] = True

        if self.variables:
            kwargs["variables"] = self.variables

        # Build task
        task = task_class(**kwargs)

        self.status = f"Task '{self.name}' created"
        return task
