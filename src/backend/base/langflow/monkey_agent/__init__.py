"""
Stub module for the monkey_agent package

This stub forwards to the actual implementation to avoid circular imports
"""
from fastapi import APIRouter

def init_monkey_agent() -> APIRouter:
    """
    Initialize the monkey agent module
    
    This is a stub that forwards to the actual implementation
    """
    # Import here to avoid circular imports
    from langflow.monkey_agent import init_monkey_agent as _init_monkey_agent
    
    # Forward to the actual implementation
    return _init_monkey_agent()
