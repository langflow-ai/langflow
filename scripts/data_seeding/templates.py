"""Flow template factory for creating agent flows."""

import json
import logging
from typing import Dict, Any
from uuid import uuid4

from .models import AgentData, AgentDomain


logger = logging.getLogger(__name__)


class FlowTemplateFactory:
    """Factory for creating flow templates based on agent types."""

    def create_complex_agent_template(self, agent_data: AgentData) -> dict:
        """Create a Complex Agent template similar to complex_agent.py starter project."""

        # Generate unique IDs for all components
        chat_input_id = str(uuid4())
        role_prompt_id = str(uuid4())
        goal_prompt_id = str(uuid4())
        backstory_prompt_id = str(uuid4())
        response_prompt_id = str(uuid4())
        llm_id = str(uuid4())
        manager_llm_id = str(uuid4())
        search_api_id = str(uuid4())
        yahoo_tool_id = str(uuid4())
        dynamic_agent_id = str(uuid4())
        manager_agent_id = str(uuid4())
        task_id = str(uuid4())
        crew_id = str(uuid4())
        chat_output_id = str(uuid4())

        nodes = [
            # Chat Input
            {
                "id": chat_input_id,
                "type": "customNode",
                "position": {"x": 100, "y": 200},
                "data": {
                    "type": "ChatInput",
                    "node": {
                        "template": {
                            "input_value": {"value": ""},
                            "sender": {"value": "User"},
                            "sender_name": {"value": "User"},
                            "session_id": {"value": ""},
                            "should_store_message": {"value": True}
                        },
                        "description": "A chat input component.",
                        "display_name": "Chat Input"
                    }
                }
            },
            # Role Prompt
            {
                "id": role_prompt_id,
                "type": "customNode",
                "position": {"x": 300, "y": 100},
                "data": {
                    "type": "Prompt",
                    "node": {
                        "template": {
                            "template": {
                                "value": f"""You are {agent_data.agent_name}.

{agent_data.description}

Define a specific role that could execute or answer the user's query effectively.

User's query: {{query}}

Role should be concise, something like "Healthcare Analyst" or "Claims Specialist"."""
                            },
                            "query": {"value": ""}
                        },
                        "description": "Role definition prompt",
                        "display_name": "Role Prompt"
                    }
                }
            },
            # Goal Prompt
            {
                "id": goal_prompt_id,
                "type": "customNode",
                "position": {"x": 300, "y": 250},
                "data": {
                    "type": "Prompt",
                    "node": {
                        "template": {
                            "template": {
                                "value": f"""Based on the user's query and your role as {agent_data.agent_name}, define a specific goal.

User's query: {{query}}
Role: {{role}}

Your goals include: {agent_data.goals}

The goal should be concise and actionable."""
                            },
                            "query": {"value": ""},
                            "role": {"value": ""}
                        },
                        "description": "Goal definition prompt",
                        "display_name": "Goal Prompt"
                    }
                }
            },
            # Backstory Prompt
            {
                "id": backstory_prompt_id,
                "type": "customNode",
                "position": {"x": 300, "y": 400},
                "data": {
                    "type": "Prompt",
                    "node": {
                        "template": {
                            "template": {
                                "value": f"""Create a professional backstory for this role and goal.

User's query: {{query}}
Role: {{role}}
Goal: {{goal}}

Context: You work in {agent_data.domain_area} and use tools like: {agent_data.tools}

The backstory should be professional and relevant to healthcare operations."""
                            },
                            "query": {"value": ""},
                            "role": {"value": ""},
                            "goal": {"value": ""}
                        },
                        "description": "Backstory definition prompt",
                        "display_name": "Backstory Prompt"
                    }
                }
            },
            # Response Prompt
            {
                "id": response_prompt_id,
                "type": "customNode",
                "position": {"x": 300, "y": 550},
                "data": {
                    "type": "Prompt",
                    "node": {
                        "template": {
                            "template": {
                                "value": f"""User's query: {{query}}

As {agent_data.agent_name}, provide a comprehensive response using your expertise in {agent_data.domain_area}.

Key performance indicators to consider: {agent_data.kpis}

Provide detailed, actionable information relevant to the user's query."""
                            },
                            "query": {"value": ""}
                        },
                        "description": "Response generation prompt",
                        "display_name": "Response Prompt"
                    }
                }
            },
            # Main LLM
            {
                "id": llm_id,
                "type": "customNode",
                "position": {"x": 500, "y": 300},
                "data": {
                    "type": "OpenAIModel",
                    "node": {
                        "template": {
                            "model_name": {"value": "gpt-4o-mini"},
                            "api_key": {"value": ""},
                            "input_value": {"value": ""},
                            "max_tokens": {"value": None},
                            "temperature": {"value": 0.7}
                        },
                        "description": "OpenAI language model",
                        "display_name": "OpenAI Model"
                    }
                }
            },
            # Manager LLM
            {
                "id": manager_llm_id,
                "type": "customNode",
                "position": {"x": 500, "y": 450},
                "data": {
                    "type": "OpenAIModel",
                    "node": {
                        "template": {
                            "model_name": {"value": "gpt-4o"},
                            "api_key": {"value": ""},
                            "input_value": {"value": ""},
                            "max_tokens": {"value": None},
                            "temperature": {"value": 0.3}
                        },
                        "description": "Manager OpenAI model",
                        "display_name": "Manager LLM"
                    }
                }
            },
            # Chat Output
            {
                "id": chat_output_id,
                "type": "customNode",
                "position": {"x": 1100, "y": 300},
                "data": {
                    "type": "ChatOutput",
                    "node": {
                        "template": {
                            "input_value": {"value": ""},
                            "sender": {"value": "AI"},
                            "sender_name": {"value": agent_data.agent_name},
                            "session_id": {"value": ""},
                            "should_store_message": {"value": True}
                        },
                        "description": "A chat output component.",
                        "display_name": "Chat Output"
                    }
                }
            }
        ]

        edges = [
            # Chat Input to Role Prompt
            {
                "source": chat_input_id,
                "sourceHandle": f"{chat_input_id}-output-message",
                "target": role_prompt_id,
                "targetHandle": f"{role_prompt_id}-input-query",
                "id": f"reactflow__edge-{chat_input_id}-{role_prompt_id}"
            },
            # Chat Input to Goal Prompt
            {
                "source": chat_input_id,
                "sourceHandle": f"{chat_input_id}-output-message",
                "target": goal_prompt_id,
                "targetHandle": f"{goal_prompt_id}-input-query",
                "id": f"reactflow__edge-{chat_input_id}-{goal_prompt_id}"
            },
            # Role Prompt to Goal Prompt
            {
                "source": role_prompt_id,
                "sourceHandle": f"{role_prompt_id}-output-prompt",
                "target": goal_prompt_id,
                "targetHandle": f"{goal_prompt_id}-input-role",
                "id": f"reactflow__edge-{role_prompt_id}-{goal_prompt_id}"
            },
            # Chat Input to Backstory Prompt
            {
                "source": chat_input_id,
                "sourceHandle": f"{chat_input_id}-output-message",
                "target": backstory_prompt_id,
                "targetHandle": f"{backstory_prompt_id}-input-query",
                "id": f"reactflow__edge-{chat_input_id}-{backstory_prompt_id}"
            },
            # Role to Backstory
            {
                "source": role_prompt_id,
                "sourceHandle": f"{role_prompt_id}-output-prompt",
                "target": backstory_prompt_id,
                "targetHandle": f"{backstory_prompt_id}-input-role",
                "id": f"reactflow__edge-{role_prompt_id}-{backstory_prompt_id}"
            },
            # Goal to Backstory
            {
                "source": goal_prompt_id,
                "sourceHandle": f"{goal_prompt_id}-output-prompt",
                "target": backstory_prompt_id,
                "targetHandle": f"{backstory_prompt_id}-input-goal",
                "id": f"reactflow__edge-{goal_prompt_id}-{backstory_prompt_id}"
            },
            # Chat Input to Response Prompt
            {
                "source": chat_input_id,
                "sourceHandle": f"{chat_input_id}-output-message",
                "target": response_prompt_id,
                "targetHandle": f"{response_prompt_id}-input-query",
                "id": f"reactflow__edge-{chat_input_id}-{response_prompt_id}"
            },
            # Response Prompt to LLM
            {
                "source": response_prompt_id,
                "sourceHandle": f"{response_prompt_id}-output-prompt",
                "target": llm_id,
                "targetHandle": f"{llm_id}-input-input_value",
                "id": f"reactflow__edge-{response_prompt_id}-{llm_id}"
            },
            # LLM to Chat Output
            {
                "source": llm_id,
                "sourceHandle": f"{llm_id}-output-text",
                "target": chat_output_id,
                "targetHandle": f"{chat_output_id}-input-input_value",
                "id": f"reactflow__edge-{llm_id}-{chat_output_id}"
            }
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 1}
        }

    # Domain-specific template mapping
    DOMAIN_TEMPLATES = {
        AgentDomain.PATIENT_EXPERIENCE: "conversational_agent",
        AgentDomain.PROVIDER_ENABLEMENT: "data_processing_agent",
        AgentDomain.UTILIZATION_MANAGEMENT: "workflow_agent",
        AgentDomain.UTILIZATION_MANAGEMENT_SPACE: "workflow_agent",
        AgentDomain.UTILIZATION_MANAGEMENT_MULTI_1: "workflow_agent",
        AgentDomain.UTILIZATION_MANAGEMENT_MULTI_2: "workflow_agent",
        AgentDomain.UTILIZATION_MANAGEMENT_MULTI_3: "workflow_agent",
        AgentDomain.CARE_MANAGEMENT: "multi_tool_agent",
        AgentDomain.RISK_ADJUSTMENT: "data_processing_agent",
        AgentDomain.CLAIMS_OPERATIONS: "workflow_agent",
        AgentDomain.POPULATION_HEALTH: "data_processing_agent",
        AgentDomain.ACTUARIAL_FINANCE: "data_processing_agent",
        AgentDomain.APPEALS_GRIEVANCES: "workflow_agent",
        AgentDomain.CLINICAL_RESEARCH: "data_processing_agent",
        AgentDomain.COMPLIANCE_AUDIT: "workflow_agent",
        AgentDomain.CONTRACTING_RFP: "workflow_agent",
        AgentDomain.HEDIS_CARE_GAP: "data_processing_agent",
        AgentDomain.MEMBER_ENGAGEMENT: "conversational_agent",
        AgentDomain.NETWORK_MANAGEMENT: "workflow_agent",
        AgentDomain.PBM_PHARMACY: "data_processing_agent",
        AgentDomain.PROVIDER_DATA_MANAGEMENT: "data_processing_agent",
        AgentDomain.PROVIDER_OPS_CONTRACTING: "workflow_agent",
        AgentDomain.QUALITY_STARS: "data_processing_agent",
        AgentDomain.REVENUE_CYCLE_MANAGEMENT: "workflow_agent",
    }

    # Color mapping for different domains
    DOMAIN_COLORS = {
        AgentDomain.PATIENT_EXPERIENCE: "#3B82F6",     # Blue
        AgentDomain.PROVIDER_ENABLEMENT: "#10B981",    # Green
        AgentDomain.UTILIZATION_MANAGEMENT: "#F59E0B", # Amber
        AgentDomain.UTILIZATION_MANAGEMENT_SPACE: "#F59E0B", # Amber
        AgentDomain.UTILIZATION_MANAGEMENT_MULTI_1: "#F59E0B", # Amber
        AgentDomain.UTILIZATION_MANAGEMENT_MULTI_2: "#F59E0B", # Amber
        AgentDomain.UTILIZATION_MANAGEMENT_MULTI_3: "#F59E0B", # Amber
        AgentDomain.CARE_MANAGEMENT: "#EF4444",        # Red
        AgentDomain.RISK_ADJUSTMENT: "#8B5CF6",        # Purple
        AgentDomain.CLAIMS_OPERATIONS: "#06B6D4",      # Cyan
        AgentDomain.POPULATION_HEALTH: "#EC4899",      # Pink
        AgentDomain.ACTUARIAL_FINANCE: "#059669",      # Emerald
        AgentDomain.APPEALS_GRIEVANCES: "#DC2626",     # Red-600
        AgentDomain.CLINICAL_RESEARCH: "#7C3AED",      # Violet
        AgentDomain.COMPLIANCE_AUDIT: "#1F2937",       # Gray-800
        AgentDomain.CONTRACTING_RFP: "#92400E",        # Amber-800
        AgentDomain.HEDIS_CARE_GAP: "#BE185D",         # Pink-700
        AgentDomain.MEMBER_ENGAGEMENT: "#2563EB",      # Blue-600
        AgentDomain.NETWORK_MANAGEMENT: "#0891B2",     # Sky-600
        AgentDomain.PBM_PHARMACY: "#C026D3",           # Fuchsia-600
        AgentDomain.PROVIDER_DATA_MANAGEMENT: "#16A34A", # Green-600
        AgentDomain.PROVIDER_OPS_CONTRACTING: "#CA8A04", # Yellow-600
        AgentDomain.QUALITY_STARS: "#E11D48",          # Rose-600
        AgentDomain.REVENUE_CYCLE_MANAGEMENT: "#9333EA", # Purple-600
    }

    def create_agent_flow(self, agent_data: AgentData) -> Dict[str, Any]:
        """Create a complete flow data structure for an agent."""
        # Determine template type based on domain
        template_type = self._get_template_type(agent_data.domain_area)

        # Generate unique IDs for nodes
        chat_input_id = str(uuid4())
        agent_id = str(uuid4())
        chat_output_id = str(uuid4())

        # Create base flow structure
        flow_data = {
            "data": {
                "nodes": self._create_nodes(agent_data, chat_input_id, agent_id, chat_output_id),
                "edges": self._create_edges(chat_input_id, agent_id, chat_output_id),
                "viewport": {"x": 0, "y": 0, "zoom": 1}
            }
        }

        return flow_data

    def _get_template_type(self, domain_area: str) -> str:
        """Get template type based on domain area."""
        try:
            domain_enum = AgentDomain(domain_area)
            return self.DOMAIN_TEMPLATES.get(domain_enum, "conversational_agent")
        except ValueError:
            logger.warning(f"Unknown domain area: {domain_area}, using default template")
            return "conversational_agent"

    def _create_nodes(self, agent_data: AgentData, chat_input_id: str, agent_id: str, chat_output_id: str) -> list:
        """Create nodes for the flow."""
        nodes = [
            # Chat Input Node
            {
                "id": chat_input_id,
                "type": "genericNode",
                "position": {"x": 100, "y": 200},
                "data": {
                    "type": "ChatInput",
                    "node": {
                        "base_classes": ["Message"],
                        "display_name": "Chat Input",
                        "description": "Input for chat messages",
                        "template": {
                            "files": {
                                "type": "file",
                                "required": False,
                                "placeholder": "",
                                "list": True,
                                "value": "",
                                "name": "files",
                                "display_name": "Files",
                                "input_types": ["file"]
                            },
                            "input_value": {
                                "type": "str",
                                "required": True,
                                "placeholder": "Type your message here...",
                                "list": False,
                                "multiline": True,
                                "value": "",
                                "name": "input_value",
                                "display_name": "Text"
                            }
                        }
                    }
                },
                "selected": False,
                "dragging": False
            },

            # Agent Node (main processing)
            {
                "id": agent_id,
                "type": "genericNode",
                "position": {"x": 400, "y": 200},
                "data": {
                    "type": "OpenAIModel",
                    "node": {
                        "base_classes": ["LanguageModel"],
                        "display_name": agent_data.agent_name,
                        "description": agent_data.description[:500] + "..." if len(agent_data.description) > 500 else agent_data.description,
                        "template": {
                            "model_name": {
                                "type": "str",
                                "required": True,
                                "value": "gpt-4",
                                "name": "model_name",
                                "display_name": "Model Name"
                            },
                            "temperature": {
                                "type": "float",
                                "required": False,
                                "value": 0.7,
                                "name": "temperature",
                                "display_name": "Temperature"
                            },
                            "max_tokens": {
                                "type": "int",
                                "required": False,
                                "value": 2048,
                                "name": "max_tokens",
                                "display_name": "Max Tokens"
                            },
                            "system_message": {
                                "type": "str",
                                "required": False,
                                "multiline": True,
                                "value": self._generate_system_prompt(agent_data),
                                "name": "system_message",
                                "display_name": "System Message"
                            }
                        }
                    }
                },
                "selected": False,
                "dragging": False
            },

            # Chat Output Node
            {
                "id": chat_output_id,
                "type": "genericNode",
                "position": {"x": 700, "y": 200},
                "data": {
                    "type": "ChatOutput",
                    "node": {
                        "base_classes": ["Message"],
                        "display_name": "Chat Output",
                        "description": "Output for chat messages",
                        "template": {
                            "data_template": {
                                "type": "str",
                                "required": True,
                                "value": "{text}",
                                "name": "data_template",
                                "display_name": "Data Template"
                            },
                            "input_value": {
                                "type": "str",
                                "required": True,
                                "value": "",
                                "name": "input_value",
                                "display_name": "Text"
                            }
                        }
                    }
                },
                "selected": False,
                "dragging": False
            }
        ]

        return nodes

    def _create_edges(self, chat_input_id: str, agent_id: str, chat_output_id: str) -> list:
        """Create edges connecting the nodes."""
        return [
            {
                "id": f"{chat_input_id}-{agent_id}",
                "source": chat_input_id,
                "target": agent_id,
                "sourceHandle": f"{chat_input_id}|input_value|Message",
                "targetHandle": f"{agent_id}|input|Message",
                "style": {"stroke": "#999"},
                "type": "smoothstep",
                "animated": False
            },
            {
                "id": f"{agent_id}-{chat_output_id}",
                "source": agent_id,
                "target": chat_output_id,
                "sourceHandle": f"{agent_id}|text|Message",
                "targetHandle": f"{chat_output_id}|input_value|Message",
                "style": {"stroke": "#999"},
                "type": "smoothstep",
                "animated": False
            }
        ]

    def _generate_system_prompt(self, agent_data: AgentData) -> str:
        """Generate a system prompt based on agent data."""
        prompt = f"""You are the {agent_data.agent_name}, a specialized AI assistant designed to help with {agent_data.domain_area.lower()} tasks.

**Your Role:**
{agent_data.description}

**Your Goals:**
{agent_data.goals}

**Key Performance Areas:**
{agent_data.kpis}

**Available Tools and Connectors:**
{agent_data.tools}

**Instructions:**
- Always provide helpful, accurate, and professional responses
- Focus on achieving the goals outlined above
- Use your knowledge of {agent_data.domain_area.lower()} best practices
- Be concise but thorough in your explanations
- Ask clarifying questions when needed to provide the best assistance

Remember to maintain a professional tone while being approachable and helpful."""

        return prompt

    def get_domain_color(self, domain_area: str) -> str:
        """Get color for domain area."""
        try:
            domain_enum = AgentDomain(domain_area)
            return self.DOMAIN_COLORS.get(domain_enum, "#6B7280")  # Default gray
        except ValueError:
            return "#6B7280"  # Default gray