"""Component for listing all flows and users as actors in the system."""

from uuid import UUID

from langflow.custom import Component
from langflow.io import Output
from langflow.schema import Data
from langflow.services.database.models.actor.utils import list_actors_with_details_for_user


class FlowsListerComponent(Component):
    display_name = "Actors Lister"
    description = "Lists all actors (flows and users) in the project."
    icon = "list"
    name = "FlowsLister"

    outputs = [
        Output(name="actors", display_name="Actors", method="list_actors"),
    ]

    async def list_actors(self) -> Data:
        """Return a list of all actors in the system."""
        try:
            # Get actor information as a list of dictionaries
            actors_list = await self.get_actors_info()
            # Structure the response
            actors_dict = {"actors": actors_list}
            return Data(data=actors_dict)
        except Exception as e:  # noqa: BLE001
            return Data(data={"error": str(e), "actors": []})

    async def get_actors_info(self) -> list[dict]:
        """Get all actor information from the system as a list of dictionaries."""
        # Get the folder_id of the current flow
        project_id = await self.get_project_id()

        # Get the user_id of the current flow
        user_id = self.user_id
        if user_id is None:
            msg = "User ID not found"
            raise ValueError(msg)

        if isinstance(user_id, str):
            user_id = UUID(user_id)

        # Use the utility function to get actors with details for this user in this project
        return await list_actors_with_details_for_user(user_id=user_id, project_id=project_id)
