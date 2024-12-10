# Updates the starter projects with the latest component versions
import os
import sys
import asyncio

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)

import backend.base.langflow.main
from backend.base.langflow.interface.types import get_and_cache_all_types_dict
from backend.base.langflow.services.deps import get_settings_service
from backend.base.langflow.initial_setup.setup import create_or_update_starter_projects

async def main():
    all_types_dict = await get_and_cache_all_types_dict(get_settings_service())
    await create_or_update_starter_projects(all_types_dict, do_create=False)
    pass

if __name__ == "__main__":
    asyncio.run(main())