"""
Langflow Client - Helper for calling Langflow agents programmatically
"""

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LangflowClient:
    """Client for calling Langflow agents/flows programmatically"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def run_flow(self, flow_id: str, inputs: Dict[str, Any], user_id: Optional[str] = None) -> str:
        """
        Run a Langflow flow and return the text output

        Args:
            flow_id: UUID of the Langflow flow
            inputs: Dictionary of input variables to pass to the flow
            user_id: User ID for the flow execution

        Returns:
            Text output from the flow's Chat Output component

        Raises:
            Exception: If flow execution fails
        """
        try:
            self.logger.info(f"Calling Langflow flow {flow_id} with inputs: {list(inputs.keys())}")

            # Use Langflow's helper to run the flow
            from langflow.helpers.flow import run_flow as langflow_run_flow

            # Default user_id (system user) if not provided
            if not user_id:
                user_id = await self._get_or_create_system_user()

            # Pass variables as tweaks to the Prompt Template component
            # This allows the prompt template to use {user_input}, {conversation_history}, {knowledge_base}
            # Note: "Prompt Template" is the display name of the component in Langflow
            tweaks = {
                "Prompt Template": {
                    "user_input": inputs.get("user_input", ""),
                    "conversation_history": inputs.get("conversation_history", "No previous conversation."),
                    "knowledge_base": inputs.get("knowledge_base", "")
                }
            }

            # Also send a simple chat input (required for ChatInput component)
            flow_inputs = {
                "input_value": inputs.get("user_input", ""),
                "type": "chat"
            }

            # DEBUG: Log what's being sent to Langflow
            self.logger.info("=" * 80)
            self.logger.info(f"LANGFLOW CLIENT - Sending to flow {flow_id}:")
            self.logger.info("-" * 80)
            self.logger.info(f"User Input: {inputs.get('user_input', '')}")
            self.logger.info(f"Conversation History (first 200 chars): {inputs.get('conversation_history', '')[:200]}...")
            self.logger.info(f"Knowledge Base (first 200 chars): {inputs.get('knowledge_base', '')[:200]}...")
            self.logger.info(f"Tweaks: {tweaks}")
            self.logger.info("=" * 80)

            # Run the flow with tweaks for prompt template variables
            run_outputs = await langflow_run_flow(
                inputs=[flow_inputs],
                flow_id=flow_id,
                user_id=user_id,
                output_type="chat",
                tweaks=tweaks
            )

            # Extract text output from result
            output_text = self._extract_output_text(run_outputs)

            # DEBUG: Log what was received from Langflow
            self.logger.info("=" * 80)
            self.logger.info(f"LANGFLOW CLIENT - Received from flow {flow_id}:")
            self.logger.info("-" * 80)
            self.logger.info(f"Extracted text: {output_text[:500]}..." if len(output_text) > 500 else f"Extracted text: {output_text}")
            self.logger.info("=" * 80)

            self.logger.info(f"Flow {flow_id} completed successfully")
            return output_text

        except Exception as e:
            self.logger.error(f"Error calling Langflow flow {flow_id}: {e}", exc_info=True)
            raise Exception(f"Failed to call Langflow agent: {str(e)}") from e

    async def _get_or_create_system_user(self) -> str:
        """Get or create a system user for flow execution"""
        from langflow.services.deps import session_scope
        from langflow.services.database.models import User
        from langflow.services.auth.utils import get_password_hash
        from sqlmodel import select
        from uuid import uuid4

        async with session_scope() as session:
            # Try to find existing system user
            stmt = select(User).where(User.username == "system")
            user = (await session.exec(stmt)).first()

            if user:
                return str(user.id)

            # Create system user if not exists
            user_id = str(uuid4())
            user = User(
                id=user_id,
                username="system",
                password=get_password_hash(str(uuid4())),
                is_active=True,
                is_superuser=True
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return str(user.id)

    def _extract_output_text(self, run_outputs: list) -> str:
        """Extract text output from Langflow run_outputs structure"""
        try:
            # run_outputs is a list of RunOutputs objects
            if not run_outputs:
                raise ValueError("No outputs in flow result")

            # Get the first run output
            run_output = run_outputs[0]

            # Extract text from outputs
            # run_output.outputs is a list of output results
            if not run_output.outputs:
                raise ValueError("No outputs in run result")

            # Get the first output (ChatOutputResponse or similar)
            first_output = run_output.outputs[0]

            # Method 1: Try ChatOutputResponse.message.text (most common for Chat Output)
            if hasattr(first_output, 'message'):
                message = first_output.message
                # Check if message has text attribute
                if hasattr(message, 'text') and message.text:
                    return message.text
                # Check if message is a dict
                if isinstance(message, dict) and 'text' in message:
                    return message['text']
                # Check if message has data attribute with text
                if hasattr(message, 'data') and isinstance(message.data, dict):
                    if 'text' in message.data:
                        return message.data['text']

            # Method 2: Try to extract from results dict
            if hasattr(first_output, 'results'):
                # first_output.results is a dict with component_id -> Data objects
                for component_id, data_obj in first_output.results.items():
                    # Try data attribute
                    if hasattr(data_obj, 'data'):
                        data_list = data_obj.data if isinstance(data_obj.data, list) else [data_obj.data]
                        for data_item in data_list:
                            if hasattr(data_item, 'text') and data_item.text:
                                return data_item.text
                    # Try text attribute directly
                    if hasattr(data_obj, 'text') and data_obj.text:
                        return data_obj.text

            # Method 3: Check if first_output has text directly
            if hasattr(first_output, 'text') and first_output.text:
                return first_output.text

            # Method 4: Check if it's a Data object with text
            if hasattr(first_output, 'data'):
                if isinstance(first_output.data, dict) and 'text' in first_output.data:
                    return first_output.data['text']
                if isinstance(first_output.data, list):
                    for item in first_output.data:
                        if hasattr(item, 'text') and item.text:
                            return item.text

            # If we still haven't found text, log the structure for debugging
            self.logger.warning(f"Could not extract text from output. Output type: {type(first_output).__name__}")
            self.logger.debug(f"Output attributes: {dir(first_output)}")

            # Fallback: stringify the result
            return str(first_output)

        except Exception as e:
            self.logger.error(f"Error extracting output text: {e}", exc_info=True)
            # Return raw result as fallback
            return str(run_outputs)

    async def run_flow_sync(self, flow_id: str, inputs: Dict[str, Any]) -> str:
        """
        Synchronous version of run_flow (for non-async contexts)

        Args:
            flow_id: UUID of the Langflow flow
            inputs: Dictionary of input variables

        Returns:
            Text output from the flow
        """
        return await self.run_flow(flow_id, inputs)
