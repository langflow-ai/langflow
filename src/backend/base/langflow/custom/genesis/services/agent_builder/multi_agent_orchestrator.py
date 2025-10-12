"""
Multi-Agent Orchestrator - Coordinates Master Planning and Builder agents
"""

import logging
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime

from langflow.api.v1.schemas import StreamData

from .langflow_client import LangflowClient
from .settings import AgentBuilderSettings

logger = logging.getLogger(__name__)


class ConversationState:
    """Tracks the conversation state across multiple turns"""

    def __init__(self, history: List[Dict[str, str]] = None):
        self.history: List[Dict[str, str]] = history or []
        self.implementation_plan: str = ""
        self.user_preferences: List[str] = []
        self.phase: str = "understanding"  # understanding, research, planning, building

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    def add_agent_message(self, message: str):
        self.history.append({"role": "agent", "content": message})

    def get_history_text(self) -> str:
        """Format conversation history as text"""
        if not self.history:
            return "No previous conversation."

        formatted = []
        for msg in self.history:
            role = "User" if msg["role"] == "user" else "Agent"
            formatted.append(f"{role}: {msg['content']}")

        return "\n".join(formatted)

    def extract_implementation_plan(self):
        """Extract implementation plan from history if it exists"""
        for msg in reversed(self.history):
            if msg["role"] == "agent":
                content = msg["content"].lower()
                if any(indicator in content for indicator in ["implementation plan", "components:", "architecture:", "next steps:"]):
                    self.implementation_plan = msg["content"]
                    self.phase = "planning"
                    break


class MultiAgentOrchestrator:
    """Orchestrates Master Planning Agent and Builder Agent"""

    def __init__(self, conversation_history: List[Dict[str, str]] = None):
        self.logger = logging.getLogger(__name__)
        self.settings = AgentBuilderSettings()

        # Langflow Flow IDs
        self.master_planning_agent_id = "1aa3f113-55f7-49e7-a24f-e1c33e1e87f4"
        self.builder_agent_id = "df9e0855-2b75-4fd6-b372-dd12ce441d58"

        # Client for calling Langflow agents
        self.langflow_client = LangflowClient()

        # Conversation state (initialized with provided history)
        self.conversation_state = ConversationState(conversation_history)
        # Extract any implementation plan from existing history
        self.conversation_state.extract_implementation_plan()

    async def build_streaming(self, user_input: str) -> AsyncGenerator[StreamData, None]:
        """
        Main orchestration method - handles user input and routes to appropriate agent

        Args:
            user_input: User's message

        Yields:
            StreamData events for frontend
        """
        try:
            self.logger.info(f"Orchestrator received input: {user_input[:100]}...")

            # Add user message to history
            self.conversation_state.add_user_message(user_input)

            # Determine if we should call Builder Agent
            if self._should_call_builder(user_input):
                # User approved plan, call Builder Agent
                async for event in self._call_builder_agent():
                    yield event

            else:
                # Call Master Planning Agent for understanding/research/planning
                async for event in self._call_master_planning_agent(user_input):
                    yield event

        except Exception as e:
            self.logger.exception(f"Error in orchestrator: {e}")
            yield StreamData(
                event="error",
                data={
                    "error": str(e),
                    "message": "An error occurred while processing your request."
                }
            )

    async def _call_master_planning_agent(self, user_input: str) -> AsyncGenerator[StreamData, None]:
        """Call Master Planning Agent with knowledge base and conversation history"""
        try:
            # Load knowledge base data
            knowledge_base_text = await self._load_knowledge_base()

            # Prepare inputs for Master Planning Agent
            inputs = {
                "user_input": user_input,
                "conversation_history": self.conversation_state.get_history_text(),
                "knowledge_base": knowledge_base_text
            }

            # DEBUG: Log Master Planning Agent inputs
            self.logger.info("=" * 80)
            self.logger.info("MASTER PLANNING AGENT (Agent 1) - INPUTS:")
            self.logger.info("-" * 80)
            self.logger.info(f"User Input: {inputs['user_input'][:200]}..." if len(inputs['user_input']) > 200 else f"User Input: {inputs['user_input']}")
            self.logger.info(f"Conversation History: {inputs['conversation_history'][:200]}..." if len(inputs['conversation_history']) > 200 else f"Conversation History: {inputs['conversation_history']}")
            self.logger.info(f"Knowledge Base (first 500 chars): {inputs['knowledge_base'][:500]}...")
            self.logger.info("=" * 80)

            # Call Master Planning Agent via Langflow
            agent_response = await self.langflow_client.run_flow(
                flow_id=self.master_planning_agent_id,
                inputs=inputs
            )

            # DEBUG: Log Master Planning Agent output
            self.logger.info("=" * 80)
            self.logger.info("MASTER PLANNING AGENT (Agent 1) - OUTPUT:")
            self.logger.info("-" * 80)
            self.logger.info(f"Response: {agent_response[:500]}..." if len(agent_response) > 500 else f"Response: {agent_response}")
            self.logger.info("=" * 80)

            # Add agent response to history
            self.conversation_state.add_agent_message(agent_response)

            # Parse agent response
            parsed = self._parse_master_planning_response(agent_response)

            # Update conversation state
            if parsed.get("implementation_plan"):
                self.conversation_state.implementation_plan = parsed["implementation_plan"]
                self.conversation_state.phase = "planning"

            # Stream the response back to frontend
            if parsed.get("phase") == "plan_ready":
                # Show the implementation plan with workflow data
                yield StreamData(event="complete", data={
                    "workflow": {
                        "name": parsed.get("agent_name", "Custom Agent"),
                        "description": parsed.get("description", ""),
                        "components": parsed.get("components", []),
                        "workflow_diagram": parsed.get("workflow", "")
                    },
                    "reasoning": agent_response,
                    "agents_count": 1
                })
            else:
                # Send agent response directly (greeting, clarification, or general response)
                yield StreamData(event="message", data={
                    "message": agent_response,
                    "phase": parsed.get("phase", self.conversation_state.phase)
                })

        except Exception as e:
            self.logger.exception(f"Error calling Master Planning Agent: {e}")
            raise

    async def _call_builder_agent(self) -> AsyncGenerator[StreamData, None]:
        """Call Builder Agent to generate YAML specification"""
        try:
            # Prepare inputs for Builder Agent
            inputs = {
                "implementation_plan": self.conversation_state.implementation_plan,
                "user_preferences": "\n".join(self.conversation_state.user_preferences) or "None specified"
            }

            # DEBUG: Log Builder Agent inputs
            self.logger.info("=" * 80)
            self.logger.info("BUILDER AGENT (Agent 2) - INPUTS:")
            self.logger.info("-" * 80)
            self.logger.info(f"Implementation Plan: {inputs['implementation_plan'][:500]}..." if len(inputs['implementation_plan']) > 500 else f"Implementation Plan: {inputs['implementation_plan']}")
            self.logger.info(f"User Preferences: {inputs['user_preferences']}")
            self.logger.info("=" * 80)

            # Call Builder Agent via Langflow
            yaml_output = await self.langflow_client.run_flow(
                flow_id=self.builder_agent_id,
                inputs=inputs
            )

            # DEBUG: Log Builder Agent output
            self.logger.info("=" * 80)
            self.logger.info("BUILDER AGENT (Agent 2) - OUTPUT:")
            self.logger.info("-" * 80)
            self.logger.info(f"YAML Output: {yaml_output[:500]}..." if len(yaml_output) > 500 else f"YAML Output: {yaml_output}")
            self.logger.info("=" * 80)

            # Parse YAML from response
            yaml_content = self._extract_yaml(yaml_output)

            # Complete with YAML workflow
            yield StreamData(event="complete", data={
                "workflow": {
                    "yaml_config": yaml_content,
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "agent_type": "multi_agent_orchestrated"
                    }
                },
                "reasoning": "Generated complete YAML specification for your agent.",
                "agents_count": 1
            })

            # Update phase
            self.conversation_state.phase = "complete"

        except Exception as e:
            self.logger.exception(f"Error calling Builder Agent: {e}")
            raise

    async def _load_knowledge_base(self) -> str:
        """Load and format knowledge base data from kb_data JSON files"""
        try:
            import json
            from pathlib import Path

            # Load agent_kb.json from kb_data directory
            kb_path = Path(__file__).parent / "kb_data" / "agent_kb.json"

            if not kb_path.exists():
                self.logger.warning(f"Knowledge base file not found: {kb_path}")
                return "Knowledge base not available."

            with open(kb_path, 'r', encoding='utf-8') as f:
                agents_data = json.load(f)

            # Format as text for LLM
            formatted_agents = []
            agent_count = 0

            for _, agent in agents_data.items():
                if agent_count >= 15:  # Limit to top 15 to avoid token limits
                    break

                # Extract key information
                name = agent.get('name', 'Unknown Agent')
                description = agent.get('description', 'No description')
                goal = agent.get('agent_goal', '')
                components = agent.get('components', [])

                # Get component types
                component_types = list(set([comp.get('component_type', '') for comp in components if comp.get('component_type')]))

                # Format agent entry
                agent_entry = f"Agent: {name}\n"
                agent_entry += f"Description: {description}\n"
                if goal:
                    agent_entry += f"Goal: {goal}\n"
                if component_types:
                    agent_entry += f"Components: {', '.join(component_types[:5])}\n"  # Limit component types
                agent_entry += "---"

                formatted_agents.append(agent_entry)
                agent_count += 1

            if not formatted_agents:
                return "No agents in knowledge base."

            return "\n".join(formatted_agents)

        except Exception as e:
            self.logger.exception(f"Error loading knowledge base: {e}")
            return "Knowledge base temporarily unavailable."

    def _should_call_builder(self, user_input: str) -> bool:
        """Determine if user wants to proceed to building"""
        user_input_lower = user_input.lower().strip()

        # Check for approval keywords
        approval_keywords = [
            "proceed", "build", "yes", "confirm", "go ahead",
            "looks good", "perfect", "let's do it", "build agent"
        ]

        # Check if we have a plan and user is approving
        has_plan = bool(self.conversation_state.implementation_plan)
        user_approving = any(keyword in user_input_lower for keyword in approval_keywords)

        return has_plan and user_approving

    def _parse_master_planning_response(self, response: str) -> Dict[str, Any]:
        """Parse Master Planning Agent response to extract structured data"""
        try:
            parsed = {
                "phase": "general",
                "implementation_plan": "",
                "agent_name": "",
                "description": "",
                "components": []
            }

            response_lower = response.lower()

            # Detect greeting - look for greeting phrases
            greeting_phrases = [
                "i'm the autonomize ai agent builder",
                "what kind of agent would you like to build",
                "ready to build an ai agent",
                "i help you create smart ai agents"
            ]
            if any(phrase in response_lower for phrase in greeting_phrases):
                parsed["phase"] = "greeting"
                return parsed

            # Detect clarification questions - look for "To design" or "I need to know"
            clarification_phrases = [
                "to design the best agent, i need to know",
                "i need to know:",
                "what is the primary goal",
                "what inputs and outputs"
            ]
            if any(phrase in response_lower for phrase in clarification_phrases):
                parsed["phase"] = "clarification"
                return parsed

            # Detect implementation plan - need MULTIPLE indicators or explicit plan signal
            plan_indicators = [
                "implementation plan",
                "components:",
                "workflow:",
                "architecture:",
                "next steps:",
                "research findings:"
            ]

            # Strong plan signals that alone indicate a plan
            # These should ONLY appear when presenting the FINAL plan
            strong_plan_signals = [
                "say 'proceed' to create",
                "say 'proceed' to build",
                "click 'build agent'",
                "does this plan look good",
                "what would you like to do next",
                "continue with creating flow or build your agent",
                "build your agent now"
                # Note: Removed "ready to build" - too ambiguous, appears in questions too
            ]

            # Count how many plan indicators are present
            indicator_count = sum(1 for indicator in plan_indicators if indicator in response_lower)
            has_strong_signal = any(signal in response_lower for signal in strong_plan_signals)

            # Only treat as plan if:
            # - Has strong signal (explicit plan presentation) OR
            # - Has 2+ indicators (comprehensive plan structure)
            if has_strong_signal or indicator_count >= 2:
                parsed["phase"] = "plan_ready"
                parsed["implementation_plan"] = response

                # Try to extract agent name from the response
                import re
                if "build a" in response_lower or "building a" in response_lower:
                    # Extract agent type from phrases like "build a Benefit Check agent"
                    match = re.search(r'build(?:ing)? a ([\w\s]+) agent', response, re.IGNORECASE)
                    if match:
                        parsed["agent_name"] = match.group(1).strip().title() + " Agent"
                elif "here's your" in response_lower or "here is your" in response_lower:
                    # Extract from phrases like "Here's your Benefit Check Agent:"
                    match = re.search(r"here.?s your ([\w\s]+?):", response, re.IGNORECASE)
                    if match:
                        parsed["agent_name"] = match.group(1).strip().title()

                # Try to extract components list from numbered list or "Components:"
                components = []
                workflow_description = ""

                # Method 1: Look for "Components:" section
                if "components:" in response_lower:
                    # Find the line with "Components:" and extract following lines
                    lines = response.split('\n')
                    in_components_section = False
                    for line in lines:
                        if 'components:' in line.lower():
                            in_components_section = True
                            continue
                        if in_components_section:
                            # Stop at empty line or next section (like "Workflow:")
                            if line.strip() == '' or (line.strip().endswith(':') and line.strip().lower() != 'components:'):
                                break
                            # Extract component name and description (handle both numbered and bullet lists)
                            comp_match = re.match(r'^\s*[\d\-\*\•]+\.?\s*([^:]+):\s*(.+)', line)
                            if comp_match:
                                components.append({
                                    "name": comp_match.group(1).strip(),
                                    "description": comp_match.group(2).strip()
                                })

                # Method 2: Extract workflow description
                if "workflow:" in response_lower:
                    lines = response.split('\n')
                    for i, line in enumerate(lines):
                        if 'workflow:' in line.lower():
                            # Get the next non-empty line after "Workflow:"
                            if i + 1 < len(lines):
                                workflow_description = lines[i + 1].strip()
                            break

                parsed["components"] = components
                parsed["workflow"] = workflow_description
                parsed["description"] = f"Agent with {len(components)} components" if components else ""

            return parsed

        except Exception as e:
            self.logger.warning(f"Error parsing master planning response: {e}")
            return {"phase": "general"}

    def _extract_yaml(self, response: str) -> str:
        """Extract YAML content from Builder Agent response"""
        try:
            # If response starts with YAML, return directly
            if response.strip().startswith("agent:") or response.strip().startswith("name:"):
                return response.strip()

            # Try to find YAML block
            if "```yaml" in response:
                yaml_start = response.find("```yaml") + 7
                yaml_end = response.find("```", yaml_start)
                return response[yaml_start:yaml_end].strip()

            if "```" in response:
                yaml_start = response.find("```") + 3
                yaml_end = response.find("```", yaml_start)
                return response[yaml_start:yaml_end].strip()

            # Return as-is if no blocks found
            return response.strip()

        except Exception as e:
            self.logger.warning(f"Error extracting YAML: {e}")
            return response
