"""Conversation Controller Component for Agent Builder."""

import json
from typing import Dict, Any, Optional
from enum import Enum

from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, DropdownInput, BoolInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


class ConversationPhase(Enum):
    """Phases of the agent building conversation."""
    INITIAL = "initial"
    REQUIREMENTS = "requirements"
    CLARIFICATION = "clarification"
    RESEARCH = "research"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    VALIDATION = "validation"
    COMPLETE = "complete"


class ConversationController(Component):
    """Controls conversation flow and pacing for agent building."""

    display_name = "Conversation Controller"
    description = "Controls the flow and pacing of agent building conversations"
    icon = "settings"
    name = "ConversationController"
    category = "Helpers"

    inputs = [
        DropdownInput(
            name="current_phase",
            display_name="Current Phase",
            info="Current phase of the conversation",
            options=[phase.value for phase in ConversationPhase],
            value=ConversationPhase.INITIAL.value,
            tool_mode=True,
        ),
        MessageTextInput(
            name="user_input",
            display_name="User Input",
            info="Latest user input to analyze",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="tool_output",
            display_name="Tool Output",
            info="Raw output from a tool to format",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="tool_name",
            display_name="Tool Name",
            info="Name of the tool that produced the output",
            required=False,
            tool_mode=True,
        ),
        BoolInput(
            name="require_confirmation",
            display_name="Require Confirmation",
            info="Whether to require user confirmation before proceeding",
            value=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Flow Control", name="flow_control", method="control_flow"),
        Output(display_name="Formatted Output", name="formatted_output", method="format_output"),
    ]

    def control_flow(self) -> Data:
        """Determine if the agent should continue or wait for user input."""
        try:
            current_phase = ConversationPhase(self.current_phase)
            user_input = self.user_input or ""

            # Determine next action based on phase and user input
            should_continue = self._should_continue(current_phase, user_input)
            next_phase = self._get_next_phase(current_phase, user_input)

            # Check for confirmation keywords
            confirmation_needed = self._check_confirmation_needed(current_phase)
            user_confirmed = self._check_user_confirmation(user_input)

            # Build flow control response
            flow_control = {
                "current_phase": current_phase.value,
                "next_phase": next_phase.value,
                "should_continue": should_continue and (not confirmation_needed or user_confirmed),
                "wait_for_user": confirmation_needed and not user_confirmed,
                "phase_message": self._get_phase_message(current_phase, next_phase),
                "prompt_for_user": self._get_user_prompt(next_phase) if confirmation_needed else None
            }

            return Data(data=flow_control)

        except Exception as e:
            logger.error(f"Error in flow control: {e}")
            return Data(data={
                "error": str(e),
                "should_continue": False,
                "wait_for_user": True
            })

    def format_output(self) -> Data:
        """Format tool output for conversational presentation."""
        try:
            if not self.tool_output:
                return Data(data={"formatted": "No output to format"})

            tool_name = self.tool_name or "unknown_tool"

            # Parse tool output if it's JSON
            try:
                if isinstance(self.tool_output, str):
                    output_data = json.loads(self.tool_output)
                else:
                    output_data = self.tool_output
            except (json.JSONDecodeError, TypeError):
                output_data = {"raw": self.tool_output}

            # Format based on tool name
            formatted = self._format_tool_output(tool_name, output_data)

            return Data(data={
                "formatted": formatted,
                "tool_name": tool_name,
                "markdown": True
            })

        except Exception as e:
            logger.error(f"Error formatting output: {e}")
            return Data(data={
                "formatted": str(self.tool_output),
                "error": str(e)
            })

    def _should_continue(self, phase: ConversationPhase, user_input: str) -> bool:
        """Determine if the agent should continue processing."""
        # Don't continue automatically after certain phases
        stop_phases = [
            ConversationPhase.REQUIREMENTS,
            ConversationPhase.RESEARCH,
            ConversationPhase.DESIGN,
            ConversationPhase.VALIDATION
        ]

        if phase in stop_phases and self.require_confirmation:
            # Check if user provided explicit continuation
            continue_keywords = ["yes", "proceed", "continue", "go ahead", "sure", "ok", "okay", "confirm"]
            return any(keyword in user_input.lower() for keyword in continue_keywords)

        return True

    def _get_next_phase(self, current: ConversationPhase, user_input: str) -> ConversationPhase:
        """Determine the next conversation phase."""
        phase_flow = {
            ConversationPhase.INITIAL: ConversationPhase.REQUIREMENTS,
            ConversationPhase.REQUIREMENTS: ConversationPhase.CLARIFICATION,
            ConversationPhase.CLARIFICATION: ConversationPhase.RESEARCH,
            ConversationPhase.RESEARCH: ConversationPhase.DESIGN,
            ConversationPhase.DESIGN: ConversationPhase.IMPLEMENTATION,
            ConversationPhase.IMPLEMENTATION: ConversationPhase.VALIDATION,
            ConversationPhase.VALIDATION: ConversationPhase.COMPLETE,
            ConversationPhase.COMPLETE: ConversationPhase.COMPLETE,
        }

        # Check for phase skip requests
        if "skip" in user_input.lower():
            # Allow skipping clarification phase
            if current == ConversationPhase.CLARIFICATION:
                return ConversationPhase.RESEARCH

        return phase_flow.get(current, current)

    def _check_confirmation_needed(self, phase: ConversationPhase) -> bool:
        """Check if the current phase requires user confirmation."""
        confirmation_phases = [
            ConversationPhase.REQUIREMENTS,
            ConversationPhase.RESEARCH,
            ConversationPhase.DESIGN,
            ConversationPhase.IMPLEMENTATION
        ]
        return phase in confirmation_phases

    def _check_user_confirmation(self, user_input: str) -> bool:
        """Check if user input contains confirmation."""
        if not user_input:
            return False

        confirmation_words = [
            "yes", "yeah", "yep", "sure", "ok", "okay",
            "proceed", "continue", "go ahead", "confirm",
            "looks good", "perfect", "great", "approve"
        ]

        negative_words = ["no", "wait", "stop", "hold", "cancel", "not yet"]

        input_lower = user_input.lower()

        # Check for negative first
        if any(word in input_lower for word in negative_words):
            return False

        # Check for positive confirmation
        return any(word in input_lower for word in confirmation_words)

    def _get_phase_message(self, current: ConversationPhase, next: ConversationPhase) -> str:
        """Get transition message between phases."""
        messages = {
            (ConversationPhase.INITIAL, ConversationPhase.REQUIREMENTS):
                "Let me analyze your requirements...",
            (ConversationPhase.REQUIREMENTS, ConversationPhase.CLARIFICATION):
                "I need to clarify a few things to better understand your needs.",
            (ConversationPhase.CLARIFICATION, ConversationPhase.RESEARCH):
                "Thanks for the clarification! Let me search for similar agents...",
            (ConversationPhase.RESEARCH, ConversationPhase.DESIGN):
                "Based on my research, let me design the architecture...",
            (ConversationPhase.DESIGN, ConversationPhase.IMPLEMENTATION):
                "Great! I'll now generate the complete specification...",
            (ConversationPhase.IMPLEMENTATION, ConversationPhase.VALIDATION):
                "Let me validate the specification...",
            (ConversationPhase.VALIDATION, ConversationPhase.COMPLETE):
                "Your specification is ready!",
        }

        return messages.get((current, next), "Processing...")

    def _get_user_prompt(self, phase: ConversationPhase) -> str:
        """Get prompt to show user for the next phase."""
        prompts = {
            ConversationPhase.CLARIFICATION:
                "Please answer the questions above to help me better understand your needs.",
            ConversationPhase.RESEARCH:
                "Shall I search for similar agents and patterns? (yes/no)",
            ConversationPhase.DESIGN:
                "Would you like me to proceed with this design approach? (yes/no)",
            ConversationPhase.IMPLEMENTATION:
                "Should I generate the complete specification now? (yes/no)",
            ConversationPhase.VALIDATION:
                "Ready to validate the specification? (yes/no)",
        }

        return prompts.get(phase, "Ready to continue? (yes/no)")

    def _format_tool_output(self, tool_name: str, output_data: Any) -> str:
        """Format tool output based on the tool name."""
        formatters = {
            "requirements_analyst": self._format_requirements,
            "intent_classifier": self._format_intent,
            "research_agent": self._format_research,
            "pattern_matcher": self._format_pattern,
            "spec_builder": self._format_specification,
            "validation_agent": self._format_validation,
            "specification_search": self._format_search_results,
        }

        formatter = formatters.get(tool_name, self._format_generic)
        return formatter(output_data)

    def _format_requirements(self, data: Dict) -> str:
        """Format requirements analyst output."""
        if isinstance(data, str):
            return data  # Already formatted conversationally

        # Fallback formatting for structured data
        return f"""
**Key Requirements Found:**
{json.dumps(data.get('requirements', {}), indent=2)}

**Questions to Clarify:**
{chr(10).join('• ' + q for q in data.get('clarifying_questions', []))}
"""

    def _format_intent(self, data: Dict) -> str:
        """Format intent classifier output."""
        if isinstance(data, str):
            return data

        return f"""
**Agent Classification:**
• Type: {data.get('agent_type', 'Unknown')}
• Complexity: {data.get('complexity', 'Unknown')}
• Pattern: {data.get('suggested_pattern', 'Unknown')}
"""

    def _format_research(self, data: Dict) -> str:
        """Format research agent output."""
        if isinstance(data, str):
            return data

        agents = data.get('similar_agents', [])
        if not agents:
            return "No similar agents found in the library."

        formatted = "**Similar Agents Found:**\n"
        for agent in agents[:3]:
            formatted += f"• **{agent.get('name')}** ({agent.get('relevance_score', 0)*100:.0f}% match)\n"

        return formatted

    def _format_pattern(self, data: Dict) -> str:
        """Format pattern matcher output."""
        if isinstance(data, str):
            return data

        return f"""
**Recommended Pattern:** {data.get('primary_pattern', 'Unknown')}

**Required Components:**
{chr(10).join('• ' + c for c in data.get('components', {}).get('required', []))}
"""

    def _format_specification(self, data: Dict) -> str:
        """Format specification builder output."""
        if isinstance(data, str):
            return data

        return "```yaml\n" + json.dumps(data, indent=2) + "\n```"

    def _format_validation(self, data: Dict) -> str:
        """Format validation agent output."""
        if isinstance(data, str):
            return data

        if data.get('valid'):
            return "✅ **Specification validated successfully!**"
        else:
            errors = data.get('errors', [])
            return f"""
⚠️ **Validation Issues Found:**
{chr(10).join('• ' + e for e in errors)}
"""

    def _format_search_results(self, data: Dict) -> str:
        """Format specification search results."""
        results = data.get('results', [])
        if not results:
            return "No specifications found matching your search."

        formatted = f"Found {len(results)} matching specifications:\n\n"
        for result in results[:3]:
            formatted += f"• **{result.get('name')}** - {result.get('description', 'No description')}\n"

        return formatted

    def _format_generic(self, data: Any) -> str:
        """Generic formatter for unknown tools."""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            return json.dumps(data, indent=2)
        else:
            return str(data)