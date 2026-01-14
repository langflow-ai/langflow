"""PraisonAI Agent Component for Langflow.

Creates and executes a PraisonAI Agent with full tool, memory, handoffs,
knowledge, and guardrails support.
"""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.base.agents.praisonai import build_memory_config, convert_llm, convert_tools
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
    SecretStrInput,
)
from lfx.schema.message import Message


class PraisonAIAgentComponent(Component):
    """PraisonAI Agent component for Langflow workflows.

    Creates and executes a PraisonAI Agent with full tool, memory, handoffs,
    knowledge, and guardrails support. Supports both sync and async execution.
    """

    display_name: str = "PraisonAI Agent"
    description: str = "Create a PraisonAI agent with tools, memory, handoffs, knowledge, and guardrails."
    documentation: str = "https://docs.praison.ai/docs/integrations/langflow"
    icon: str = "PraisonAI"
    name: str = "PraisonAI Agent"

    inputs = [
        # ============================================================
        # CORE IDENTITY
        # ============================================================
        MultilineInput(
            name="name",
            display_name="Agent Name",
            info="Name for identification and logging.",
            value="Agent",
        ),
        MultilineInput(
            name="role",
            display_name="Role",
            info="Role/job title defining the agent's expertise (e.g., 'Data Analyst').",
            advanced=True,
        ),
        MultilineInput(
            name="goal",
            display_name="Goal",
            info="Primary objective the agent aims to achieve.",
            advanced=True,
        ),
        MultilineInput(
            name="backstory",
            display_name="Backstory",
            info="Background context shaping personality and decisions.",
            advanced=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="Instructions",
            info="System prompt/instructions for the agent. Recommended for simple agents.",
            value="You are a helpful assistant.",
        ),
        # ============================================================
        # INPUT
        # ============================================================
        HandleInput(
            name="input_value",
            display_name="Input",
            info="User input to process.",
            input_types=["Message", "str"],
        ),
        # ============================================================
        # LLM CONFIGURATION
        # ============================================================
        DropdownInput(
            name="llm",
            display_name="Model",
            info="LLM model to use (provider/model-name format).",
            options=[
                "openai/gpt-4o-mini",
                "openai/gpt-4o",
                "openai/gpt-4-turbo",
                "openai/o1-mini",
                "openai/o1-preview",
                "anthropic/claude-3-5-sonnet-20241022",
                "anthropic/claude-3-opus-20240229",
                "anthropic/claude-3-haiku-20240307",
                "google/gemini-1.5-pro",
                "google/gemini-1.5-flash",
                "google/gemini-2.0-flash",
                "deepseek/deepseek-chat",
                "deepseek/deepseek-reasoner",
                "groq/llama-3.3-70b-versatile",
                "groq/mixtral-8x7b-32768",
                "ollama/llama3.2",
                "ollama/mistral",
            ],
            value="openai/gpt-4o-mini",
        ),
        HandleInput(
            name="llm_handle",
            display_name="Language Model",
            info="External LLM from Langflow model components (overrides dropdown).",
            input_types=["LanguageModel"],
            advanced=True,
        ),
        MultilineInput(
            name="base_url",
            display_name="Base URL",
            info="Custom LLM endpoint URL (e.g., for Ollama: http://localhost:11434).",
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for LLM provider (overrides environment variable).",
            advanced=True,
        ),
        # ============================================================
        # TOOLS
        # ============================================================
        HandleInput(
            name="tools",
            display_name="Tools",
            info="Tools available to the agent.",
            input_types=["Tool", "BaseTool"],
            is_list=True,
        ),
        BoolInput(
            name="allow_delegation",
            display_name="Allow Delegation",
            info="Allow task delegation to other agents.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="allow_code_execution",
            display_name="Allow Code Execution",
            info="Enable code execution during tasks (use with caution).",
            value=False,
            advanced=True,
        ),
        DropdownInput(
            name="code_execution_mode",
            display_name="Code Execution Mode",
            info="'safe' restricts access, 'unsafe' allows full system access.",
            options=["safe", "unsafe"],
            value="safe",
            advanced=True,
        ),
        # ============================================================
        # HANDOFFS (Agent Collaboration)
        # ============================================================
        HandleInput(
            name="handoffs",
            display_name="Handoffs",
            info="Other agents this agent can hand off conversations to.",
            input_types=["Agent"],
            is_list=True,
            advanced=True,
        ),
        # ============================================================
        # MEMORY
        # ============================================================
        BoolInput(
            name="memory",
            display_name="Memory",
            info="Enable agent memory for context retention across conversations.",
            value=False,
        ),
        DropdownInput(
            name="memory_provider",
            display_name="Memory Provider",
            info="Memory storage provider.",
            options=["", "rag", "mem0"],
            value="",
            advanced=True,
        ),
        DictInput(
            name="memory_config",
            display_name="Memory Config",
            info="Full MemoryConfig as dictionary (e.g., {'provider': 'rag', 'collection': 'my_collection'}).",
            advanced=True,
            is_list=True,
        ),
        # ============================================================
        # KNOWLEDGE (RAG)
        # ============================================================
        FileInput(
            name="knowledge_files",
            display_name="Knowledge Files",
            info="Files to use as knowledge sources (PDF, TXT, MD, etc.).",
            file_types=["pdf", "txt", "md", "csv", "json", "docx"],
            advanced=True,
        ),
        MultilineInput(
            name="knowledge_urls",
            display_name="Knowledge URLs",
            info="URLs to use as knowledge sources (one per line).",
            advanced=True,
        ),
        # ============================================================
        # GUARDRAILS
        # ============================================================
        BoolInput(
            name="guardrails",
            display_name="Guardrails",
            info="Enable output validation guardrails.",
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
            name="markdown",
            display_name="Markdown Output",
            info="Format output as markdown.",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="self_reflect",
            display_name="Self Reflect",
            info="Enable self-reflection for improved responses.",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="max_iter",
            display_name="Max Iterations",
            info="Maximum number of iterations for the agent loop.",
            value=20,
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
            display_name="Agent",
            name="agent",
            method="build_agent",
        ),
    ]

    def _import_agent(self):
        """Import Agent class with proper error handling."""
        try:
            from praisonaiagents import Agent
        except ImportError as e:
            msg = (
                "PraisonAI Agents is not installed. "
                "Install with: pip install praisonaiagents"
            )
            raise ImportError(msg) from e
        else:
            return Agent

    def _build_knowledge_config(self) -> list | bool | None:
        """Build knowledge configuration from file and URL inputs."""
        sources = []

        # Add files
        if self.knowledge_files:
            if isinstance(self.knowledge_files, list):
                sources.extend(self.knowledge_files)
            else:
                sources.append(self.knowledge_files)

        # Add URLs (split by newlines)
        if self.knowledge_urls:
            urls = [url.strip() for url in self.knowledge_urls.split("\n") if url.strip()]
            sources.extend(urls)

        if sources:
            return sources
        return None

    def build_agent(self) -> Any:
        """Build and return the PraisonAI Agent instance."""
        agent_class = self._import_agent()

        # Convert tools if provided
        tools = convert_tools(self.tools) if self.tools else None

        # Get LLM - prefer handle input, fallback to dropdown
        llm = self._get_llm()

        # Build memory configuration
        memory_cfg = build_memory_config(
            memory=self.memory,
            memory_provider=self.memory_provider or None,
            memory_config_dict=self.memory_config or None,
        )

        # Build knowledge configuration
        knowledge = self._build_knowledge_config()

        # Build handoffs list (filter None)
        handoffs = None
        if self.handoffs:
            handoffs = [h for h in self.handoffs if h is not None]
            if not handoffs:
                handoffs = None

        # Build agent kwargs
        kwargs = {
            "name": self.name,
            "role": self.role or None,
            "goal": self.goal or None,
            "backstory": self.backstory or None,
            "instructions": self.instructions,
            "llm": llm,
            "tools": tools,
            "memory": memory_cfg,
            "allow_delegation": self.allow_delegation,
            "allow_code_execution": self.allow_code_execution,
        }

        # Add output config (replaces verbose/markdown)
        if self.verbose or self.markdown:
            kwargs["output"] = "verbose" if self.verbose else {"markdown": self.markdown}

        # Add reflection config (replaces self_reflect)
        if self.self_reflect:
            kwargs["reflection"] = True

        # Add optional parameters
        if self.base_url:
            kwargs["base_url"] = self.base_url

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if handoffs:
            kwargs["handoffs"] = handoffs

        if knowledge:
            kwargs["knowledge"] = knowledge

        if self.guardrails:
            kwargs["guardrails"] = True

        if self.code_execution_mode and self.allow_code_execution:
            kwargs["code_execution_mode"] = self.code_execution_mode

        # Add execution config (replaces max_iter)
        default_max_iter = 20
        if self.max_iter and self.max_iter != default_max_iter:
            kwargs["execution"] = {"max_iter": self.max_iter}

        # Build agent
        agent = agent_class(**kwargs)

        self.status = f"Agent '{self.name}' created"
        return agent

    def build_response(self) -> Message:
        """Execute the agent and return the response as a Message."""
        agent = self.build_agent()

        # Get input value
        input_value = self.input_value
        if hasattr(input_value, "text"):
            input_value = input_value.text
        elif input_value is None:
            input_value = ""

        # Execute agent (sync)
        result = agent.start(str(input_value))

        # Convert to Langflow Message
        return Message(text=str(result))

    async def build_response_async(self) -> Message:
        """Execute the agent asynchronously and return the response."""
        # Run sync agent.start() in thread pool to avoid blocking
        return await asyncio.to_thread(self.build_response)

    def _get_llm(self) -> str:
        """Get LLM configuration from dropdown or handle input."""
        if self.llm_handle:
            # Convert LangChain model to PraisonAI format
            converted = convert_llm(self.llm_handle)
            if converted:
                return converted
        return self.llm
