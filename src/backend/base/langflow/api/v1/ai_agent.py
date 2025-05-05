from fastapi import APIRouter, HTTPException, Depends, Body, Security
from typing import Dict, List, Any, Optional, Union, Annotated
from langflow.api.v1.schemas import ChatMessage, ChatResponse
from langflow.schema.actions import Action, AddNodeAction, EditNodeAction, ConnectNodesAction, CreateWorkflowAction
from pydantic import BaseModel
from langflow.services.auth.utils import get_current_active_user
from langflow.services.deps import get_settings_service, get_db_service, get_variable_service, session_scope
from langflow.services.database.models.user.model import User
from langflow.agent.agent import process_agent_request

import logging
import os
from openai import OpenAI
import json

logger = logging.getLogger(__name__)

# Simple in-memory storage for API keys by user ID
# In a production environment, this should be replaced with a secure storage solution
api_key_storage = {}

router = APIRouter(prefix="/ai-agent", tags=["AI Agent"])

class AIAgentRequest(BaseModel):
    message: str
    flow_state: Dict[str, Any]

class AIAgentAction(BaseModel):
    type: str
    data: Optional[Dict[str, Any]] = None
    node_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None
    name: Optional[str] = None

class AIAgentResponse(BaseModel):
    message: str
    actions: Optional[List[AIAgentAction]] = None

class APIKeyRequest(BaseModel):
    api_key: str

@router.post("/api-key")
async def set_api_key(
    request: APIKeyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Set the OpenAI API key for the current user
    """
    user_id = str(current_user.id)
    api_key_storage[user_id] = request.api_key
    logger.info(f"API key set for user {user_id}")
    return {"message": "API key set successfully"}

@router.post("/chat", response_model=AIAgentResponse)
async def ai_agent_chat(
    request: AIAgentRequest,
    current_user: User = Depends(get_current_active_user),
) -> AIAgentResponse:
    """
    Chat with AI agent to manipulate the workflow
    """
    try:
        # Get services
        settings_service = get_settings_service()
        variable_service = get_variable_service()
        
        # Debug logging for request
        logger.info(f"Chat request received: {request.message[:100]}...")
        logger.info(f"Flow state has {len(request.flow_state.get('nodes', []))} nodes and {len(request.flow_state.get('edges', []))} edges")
        
        # First try to get API key from our direct storage
        user_id = str(current_user.id)
        openai_api_key = api_key_storage.get(user_id)
        
        if openai_api_key:
            logger.info(f"Using API key from direct storage for user {user_id}")
        else:
            # Try to get the API key from variables as fallback
            logger.info("API key not found in direct storage, checking variables")
            
            # Need to use the async DB session to get variables
            async with session_scope() as session:
                try:
                    # Get all variables for the current user
                    variables = await variable_service.get_all(user_id=current_user.id, session=session)
                    logger.info(f"Found {len(variables)} variables for user {current_user.id}")
                    
                    # Log all variable names for debugging
                    logger.info(f"Available variables: {[var.name for var in variables]}")
                    
                    # Check for OpenAI API key
                    for var in variables:
                        logger.info(f"Checking variable: {var.name}")
                        if var.name.lower() in ["openai_api_key", "openai api key", "openai", "my_openai_key"]:
                            openai_api_key = var.value
                            # Log part of the key for debugging (safely)
                            if openai_api_key and len(openai_api_key) > 8:
                                safe_key = openai_api_key[:4] + "..." + openai_api_key[-4:]
                                logger.info(f"Found OpenAI API key in variable: {var.name} (Key: {safe_key})")
                            else:
                                logger.info(f"Found OpenAI API key in variable: {var.name} but it seems invalid or empty")
                            break
                except Exception as e:
                    logger.error(f"Error fetching variables: {e}")
            
        if not openai_api_key:
            # Try to get from environment as fallback
            openai_api_key = os.environ.get("OPENAI_API_KEY", "")
            if openai_api_key:
                logger.info("Found OpenAI API key in environment variables")
                
        if not openai_api_key:
            logger.warning("OpenAI API key not found")
            return AIAgentResponse(
                message="I need an OpenAI API key to help with workflow manipulation. Please use the 'Set API Key' button in the chat interface to provide your OpenAI API key.",
                actions=[]
            )
        
        # Debug log the API key
        if openai_api_key == "dummy":
            logger.error("API key is still set to 'dummy'. This is likely a placeholder value.")
            return AIAgentResponse(
                message="Your OpenAI API key is set to 'dummy', which is a placeholder value. Please update it with a valid API key.",
                actions=[]
            )
            
        if len(openai_api_key) < 20:  # Real OpenAI keys are longer
            logger.error(f"API key seems too short to be valid: {len(openai_api_key)} characters")
            return AIAgentResponse(
                message=f"Your OpenAI API key seems too short ({len(openai_api_key)} characters). Valid OpenAI API keys are typically much longer. Please check your API key.",
                actions=[]
            )
                
        # Process the request using our agent framework
        try:
            # Get model name from settings or use default
            model_name = "gpt-4o-2024-08-06"  # Default model
            logger.info(f"Using OpenAI model: {model_name}")
            
            # Process the request with our agent framework
            message, actions = process_agent_request(
                message=request.message,
                flow_state=request.flow_state,
                api_key=openai_api_key,
                model=model_name
            )
            
            logger.info(f"Agent generated {len(actions)} actions")
            return AIAgentResponse(message=message, actions=actions)
            
        except Exception as api_error:
            error_msg = str(api_error)
            logger.error(f"OpenAI API error: {error_msg}")
            
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                return AIAgentResponse(
                    message=f"Authentication error with OpenAI API: {error_msg}. Please check that your API key is valid, properly formatted, and has sufficient credits.",
                    actions=[]
                )
            else:
                return AIAgentResponse(
                    message=f"Error processing your request: {error_msg}",
                    actions=[]
                )
                
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in AI agent: {error_msg}")
        return AIAgentResponse(
            message=f"I encountered an unexpected error: {error_msg}. Please try again or check server logs for more details.",
            actions=[]
        )
