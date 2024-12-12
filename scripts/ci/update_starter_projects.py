"""Script to update Langflow starter projects with the latest component versions."""

import asyncio

import langflow.main  # noqa: F401
from langflow.initial_setup.setup import create_or_update_starter_projects
from langflow.interface.types import get_and_cache_all_types_dict
from langflow.services.deps import get_settings_service


async def main():
    """Updates the starter projects with the latest component versions."""
    all_types_dict = await get_and_cache_all_types_dict(get_settings_service())
    await create_or_update_starter_projects(all_types_dict, do_create=False)


if __name__ == "__main__":
    asyncio.run(main())
