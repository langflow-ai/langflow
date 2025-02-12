from typing import Dict, Optional
from langflow.io import StrInput, Output
from permit import Permit
from langflow.base.auth.model import AuthComponent

class PermitCheckComponent(AuthComponent):
    display_name = "Permit Check"
    description = "Performs authorization checks using Permit.io"
    documentation = "https://python.langchain.com/docs/get_started/introduction"
    icon = "PermitCheck"

    inputs = [
        StrInput(name="user", display_name="User", required=True),
        StrInput(name="action", display_name="Action", required=True),
        StrInput(name="resource", display_name="Resource", required=True),
        StrInput(name="tenant", display_name="Tenant", required=False),
    ]

    outputs = [
        Output(name="allowed", display_name="Allowed", method="execute"),
    ]

    def build_config(self) -> Dict:
        return {
            "pdp_url": {
                "display_name": "PDP URL",
                "description": "URL of the Policy Decision Point",
                "type": "str",
                "required": True,
            },
            "api_key": {
                "display_name": "API Key",
                "description": "Permit.io API key",
                "type": "str",
                "required": True,
            }
        }

    def build(self, pdp_url: str, api_key: str) -> None:
        """Initialize the Permit client."""
        self.permit = Permit(
            pdp=pdp_url,
            token=api_key
        )

    def execute(
        self,
        user: str,
        action: str,
        resource: str,
        tenant: Optional[str] = None
    ) -> bool:
        """
        Check if the action is allowed.
        
        Args:
            user: User identifier
            action: Action to check
            resource: Resource identifier
            tenant: Optional tenant identifier
            
        Returns:
            bool: True if action is allowed, False otherwise
        """
        try:
            # Create the context for the check
            context = {
                "tenant": tenant
            } if tenant else {}
            
            # Perform the permission check
            allowed = self.permit.check(
                user=user,
                action=action,
                resource=resource,
                context=context
            )
            
            self.status = allowed
            return allowed
            
        except Exception as e:
            raise ValueError(f"Permission check failed: {str(e)}")