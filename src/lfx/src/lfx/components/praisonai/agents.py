"""PraisonAI Agents Component for Langflow.

Multi-agent orchestration component that coordinates multiple PraisonAI agents
with full memory, planning, guardrails, and workflow support.
"""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    HandleInput,
    MultilineInput,
    Output,
)
from lfx.schema.message import Message


class PraisonAIAgentsComponent(Component):
    """PraisonAI Agents component for multi-agent orchestration.

    Coordinates multiple agents to work together on complex tasks using
    sequential, hierarchical, or workflow-based execution patterns.
    Supports shared memory, guardrails, and comprehensive output options.
    """

    display_name: str = "PraisonAI Agents"
    description: str = "Orchestrate multiple PraisonAI agents with memory, guardrails, and workflow support."
    documentation: str = "https://docs.praison.ai/docs/integrations/langflow"
    icon: str = "PraisonAI"
    name: str = "PraisonAI Agents"

    inputs = [
        # ============================================================
        # IDENTITY
        # ============================================================
        MultilineInput(
            name="name",
            display_name="Name",
            info="Name for this agent collection.",
            value="AgentTeam",
        ),
        # ============================================================
        # AGENTS & TASKS
        # ============================================================
        HandleInput(
            name="agents",
            display_name="Agents",
            info="List of PraisonAI agents to orchestrate.",
            input_types=["Agent"],
            is_list=True,
        ),
        HandleInput(
            name="tasks",
            display_name="Tasks",
            info="List of tasks for the agents to execute. If empty, auto-generated from agents.",
            input_types=["Task"],
            is_list=True,
        ),
        # ============================================================
        # INPUT
        # ============================================================
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Initial input to start the multi-agent workflow.",
            input_types=["Message", "str"],
        ),
        # ============================================================
        # PROCESS TYPE
        # ============================================================
        DropdownInput(
            name="process",
            display_name="Process",
            info="How agents should collaborate.",
            options=["sequential", "hierarchical", "workflow"],
            value="sequential",
        ),
        # ============================================================
        # MANAGER (for hierarchical)
        # ============================================================
        HandleInput(
            name="manager_agent",
            display_name="Manager Agent",
            info="Manager agent for hierarchical process (optional).",
            input_types=["Agent"],
            advanced=True,
        ),
        MultilineInput(
            name="manager_llm",
            display_name="Manager LLM",
            info="LLM for auto-created manager in hierarchical mode.",
            value="openai/gpt-4o",
            advanced=True,
        ),
        # ============================================================
        # VARIABLES
        # ============================================================
        DictInput(
            name="variables",
            display_name="Variables",
            info="Global variables for substitution in all task descriptions.",
            advanced=True,
        ),
        # ============================================================
        # MEMORY
        # ============================================================
        BoolInput(
            name="memory",
            display_name="Shared Memory",
            info="Enable shared memory across all agents.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # GUARDRAILS
        # ============================================================
        BoolInput(
            name="guardrails",
            display_name="Guardrails",
            info="Enable output validation for all agents.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # EXECUTION OPTIONS
        # ============================================================
        BoolInput(
            name="verbose",
            display_name="Verbose",
            info="Show detailed execution logs.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="full_output",
            display_name="Full Output",
            info="Return full output including all task results.",
            value=False,
            advanced=True,
        ),
        # ============================================================
        # ADVANCED FEATURES
        # ============================================================
        BoolInput(
            name="planning",
            display_name="Planning",
            info="Enable planning mode for complex task decomposition.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="reflection",
            display_name="Reflection",
            info="Enable self-reflection for improved results.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="caching",
            display_name="Caching",
            info="Enable caching of agent responses.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Response",
            name="response",
            method="build_response",
        ),
        Output(
            display_name="Agents Instance",
            name="agents_instance",
            method="build_agents",
        ),
    ]

    def _import_agents(self):
        """Import Agents class with proper error handling."""
        try:
            from praisonaiagents import Agents
        except ImportError as e:
            msg = "PraisonAI Agents is not installed. Install with: pip install praisonaiagents"
            raise ImportError(msg) from e
        else:
            return Agents

    def build_agents(self) -> Any:
        """Build and return the PraisonAI Agents instance."""
        agents_class = self._import_agents()

        # Filter out None values
        agents = [a for a in (self.agents or []) if a is not None]
        tasks = [t for t in (self.tasks or []) if t is not None]

        if not agents:
            msg = "At least one agent is required."
            raise ValueError(msg)

        # Build kwargs
        kwargs = {
            "agents": agents,
            "process": self.process,
        }

        # Add output config (replaces verbose/full_output)
        if self.verbose or self.full_output:
            kwargs["output"] = "verbose" if self.verbose else "actions"

        # Add name if provided
        if self.name and self.name != "AgentTeam":
            kwargs["name"] = self.name

        # Add tasks if provided
        if tasks:
            kwargs["tasks"] = tasks

        # Add variables if provided
        if self.variables:
            kwargs["variables"] = self.variables

        # Add memory configuration
        if self.memory:
            kwargs["memory"] = True

        # Add manager for hierarchical
        if self.process == "hierarchical":
            if self.manager_agent:
                kwargs["manager_agent"] = self.manager_agent
            elif self.manager_llm:
                kwargs["manager_llm"] = self.manager_llm

        # Add advanced features
        if self.guardrails:
            kwargs["guardrails"] = True

        if self.planning:
            kwargs["planning"] = True

        if self.reflection:
            kwargs["reflection"] = True

        if self.caching:
            kwargs["caching"] = True

        # Build Agents
        agents_instance = agents_class(**kwargs)

        self.status = f"Agents orchestrator '{self.name}' created with {len(agents)} agents"
        return agents_instance

    def build_response(self) -> Message:
        """Execute the multi-agent workflow and return the response."""
        agents_instance = self.build_agents()

        # Get input value
        input_value = self.input_value
        if hasattr(input_value, "text"):
            input_value = input_value.text
        elif input_value is None:
            input_value = ""

        # Execute agents (sync)
        result = agents_instance.start(str(input_value))

        # Convert to Langflow Message
        output_text = result.get("final_output", str(result)) if isinstance(result, dict) else str(result)

        return Message(text=output_text)

    async def build_response_async(self) -> Message:
        """Execute the multi-agent workflow asynchronously."""
        # Run sync start() in thread pool to avoid blocking
        return await asyncio.to_thread(self.build_response)
