"""Script to update Langflow starter projects with the latest component versions."""

import asyncio
import os

import langflow.main  # noqa: F401
from langflow.initial_setup.setup import (
    get_project_data,
    load_starter_projects,
    update_edges_with_latest_component_versions,
    update_project_file,
    update_projects_components_with_latest_component_versions,
)
from langflow.interface.components import get_and_cache_all_types_dict
from langflow.services.deps import get_settings_service
from langflow.services.utils import initialize_services


async def main():
    """Updates the starter projects with the latest component versions.

    Copies the code from langflow/initial_setup/setup.py. Doesn't use the
    create_or_update_starter_projects function directly to avoid sql interactions.
    """
    await initialize_services(fix_migration=False)
    all_types_dict = await get_and_cache_all_types_dict(get_settings_service())

    starter_projects = await load_starter_projects()
    for project_path, project in starter_projects:
        _, _, _, _, project_data, _, _, _, _ = get_project_data(project)
        do_update_starter_projects = os.environ.get("LANGFLOW_UPDATE_STARTER_PROJECTS", "true").lower() == "true"
        if do_update_starter_projects:
            updated_project_data = update_projects_components_with_latest_component_versions(
                project_data.copy(), all_types_dict
            )
            updated_project_data = update_edges_with_latest_component_versions(updated_project_data)
            if updated_project_data != project_data:
                project_data = updated_project_data
                await update_project_file(project_path, project, updated_project_data)


if __name__ == "__main__":
    asyncio.run(main())
