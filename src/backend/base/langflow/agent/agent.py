"""
Agent implementation for the Langflow AI Agent.
This module contains the core agent logic for processing
user requests and generating actions to manipulate the Langflow canvas.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import uuid

from openai import OpenAI
from pydantic import BaseModel, Field

from langflow.agent.tools import (
    AGENT_TOOLS,
    AGENT_TOOL_DESCRIPTIONS,
    create_question_answering_workflow,
)

# Configure logging
logger = logging.getLogger(__name__)

class AgentRequest(BaseModel):
    """Input request for the Langflow Agent."""
    message: str = Field(..., description="User message")
    flow_state: Dict[str, Any] = Field(..., description="Current state of the flow")

class AgentResponse(BaseModel):
    """Response from the Langflow Agent."""
    message: str = Field(..., description="Response message to the user")
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="Actions to perform on the flow")

class LangflowAgent:
    """
    Agent that processes user requests and generates actions
    to manipulate the Langflow canvas.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o-2024-08-06"):
        """
        Initialize the agent.
        
        Args:
            api_key: OpenAI API key
            model: Model to use for the agent
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a user request and generate a response.
        
        Args:
            request: Agent request with user message and flow state
            
        Returns:
            Agent response with message and actions
        """
        # Check for specific intents that can be handled directly
        direct_actions = self._check_direct_intents(request.message)
        if direct_actions:
            return AgentResponse(
                message=f"I'll create that for you right away.",
                actions=direct_actions
            )
            
        # Process with AI if no direct intent match
        try:
            # Call OpenAI API with function calling
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": self._format_user_message(request)}
                ],
                tools=AGENT_TOOL_DESCRIPTIONS,
                tool_choice="auto"
            )
            
            return self._process_completion(completion)
            
        except Exception as e:
            logger.error(f"Error in agent: {e}")
            return AgentResponse(
                message=f"I encountered an error: {str(e)}. Please try again with a different request.",
                actions=[]
            )
    
    def _check_direct_intents(self, message: str) -> Optional[List[Dict[str, Any]]]:
        """
        Check for specific intents that can be handled directly without AI.
        
        Args:
            message: User message
            
        Returns:
            List of actions if a direct match is found, None otherwise
        """
        message_lower = message.lower()
        
        # Check for QA workflow intent
        qa_workflow_patterns = [
            "create a question answering workflow",
            "question answering flow",
            "qa workflow",
            "simple qa flow",
            "make a qa workflow"
        ]
        
        for pattern in qa_workflow_patterns:
            if pattern in message_lower:
                return create_question_answering_workflow()
                
        return None
    
    def _format_user_message(self, request: AgentRequest) -> str:
        """
        Format the user message with flow state information.
        
        Args:
            request: Agent request
            
        Returns:
            Formatted message for the LLM
        """
        # Format the flow state information
        flow_info = self._format_flow_state(request.flow_state)
        
        return f"""
User Request: {request.message}

Current Flow State:
{flow_info}

Please help the user by responding to their request and taking appropriate actions 
on the flow canvas. Return actions that can be executed to fulfill the user's request.
"""
    
    def _format_flow_state(self, flow_state: Dict[str, Any]) -> str:
        """
        Format the flow state information for the LLM.
        
        Args:
            flow_state: Current state of the flow
            
        Returns:
            Formatted flow state information
        """
        nodes = flow_state.get("nodes", [])
        edges = flow_state.get("edges", [])
        
        nodes_info = f"Nodes ({len(nodes)}):"
        for i, node in enumerate(nodes[:10]):  # Limit to first 10 nodes
            nodes_info += f"\n  - Node {i+1}: ID={node.get('id')}, Type={node.get('data', {}).get('type')}"
            
        edges_info = f"Edges ({len(edges)}):"
        for i, edge in enumerate(edges[:10]):  # Limit to first 10 edges
            edges_info += f"\n  - Edge {i+1}: {edge.get('source')} -> {edge.get('target')}"
            
        if len(nodes) > 10:
            nodes_info += f"\n  ... and {len(nodes) - 10} more nodes"
        if len(edges) > 10:
            edges_info += f"\n  ... and {len(edges) - 10} more edges"
            
        return f"{nodes_info}\n\n{edges_info}"
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the agent.
        
        Returns:
            System prompt
        """
        return """You are an AI assistant that helps users build workflows in Langflow, a visual 
programming tool for LangChain. Your job is to help users create, modify, and connect nodes in their workflow.

You have the ability to perform the following actions to help the user:
1. Add a new node to the canvas
2. Edit an existing node's parameters
3. Connect nodes together
4. Create a complete workflow from scratch

When the user asks you to create or modify a workflow, use the provided tools to perform the necessary actions.
Be specific and precise with your actions. Always use the available tools rather than just explaining what to do.

Some common node types in Langflow include:
- ChatOpenAI: For creating a chat model
- PromptTemplate: For creating a template for prompts
- HumanInputNode: For user input
- TextNode: For displaying text output
- WebScraper: For scraping web content
- ConversationBufferMemory: For adding memory to conversations
- VectorStore: For storing vector embeddings

When connecting nodes, make sure the connection makes logical sense (e.g., connecting an output to an input).
"""
    
    def _process_completion(self, completion) -> AgentResponse:
        """
        Process the completion from the LLM.
        
        Args:
            completion: Completion from the LLM
            
        Returns:
            Agent response
        """
        message_content = completion.choices[0].message.content or ""
        tool_calls = completion.choices[0].message.tool_calls or []
        
        actions = []
        
        # Process tool calls
        for tool_call in tool_calls:
            try:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name in AGENT_TOOLS:
                    tool_fn = AGENT_TOOLS[function_name]
                    action = tool_fn(function_args)
                    actions.append(action)
                    logger.info(f"Added action: {action['type']}")
                else:
                    logger.warning(f"Unknown tool: {function_name}")
                    
            except Exception as e:
                logger.error(f"Error processing tool call: {e}")
        
        # Return the response
        return AgentResponse(
            message=message_content,
            actions=actions
        )


def process_agent_request(
    message: str, 
    flow_state: Dict[str, Any], 
    api_key: str, 
    model: str = "gpt-4o-2024-08-06"
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Process an agent request.
    
    Args:
        message: User message
        flow_state: Current state of the flow
        api_key: OpenAI API key
        model: Model to use for the agent
        
    Returns:
        Tuple of (message, actions)
    """
    agent = LangflowAgent(api_key=api_key, model=model)
    request = AgentRequest(message=message, flow_state=flow_state)
    response = agent.process_request(request)
    
    return response.message, response.actions
