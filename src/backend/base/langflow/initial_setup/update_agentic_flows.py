import asyncio
import sys
from pathlib import Path
from copy import deepcopy
import orjson

# Add src/backend/base to sys.path to allow imports
sys.path.append(str(Path(__file__).resolve().parents[3]))

from langflow.services.deps import get_settings_service, get_telemetry_service
from langflow.services.utils import initialize_settings_service
from lfx.interface.components import get_and_cache_all_types_dict
from lfx.log.logger import configure
from langflow.initial_setup.setup import (
    update_projects_components_with_latest_component_versions,
    update_edges_with_latest_component_versions,
)

async def main():
    configure()
    initialize_settings_service()
    settings_service = get_settings_service()
    telemetry_service = get_telemetry_service()
    
    # Cache types
    print("Caching types...")
    all_types_dict = await get_and_cache_all_types_dict(settings_service, telemetry_service)
    print("Types cached.")

    flows_dir = Path(__file__).resolve().parent.parent / "agentic" / "flows"
    print(f"Flows directory: {flows_dir}")
    
    for flow_file in flows_dir.glob("*.json"):
        print(f"Processing {flow_file.name}...")
        try:
            with open(flow_file, "r", encoding="utf-8") as f:
                flow_data = orjson.loads(f.read())
            
            if "data" in flow_data:
                project_data = flow_data["data"]
                updated_project_data = update_projects_components_with_latest_component_versions(
                    deepcopy(project_data), all_types_dict
                )
                updated_project_data = update_edges_with_latest_component_versions(updated_project_data)
                
                if updated_project_data != project_data:
                    flow_data["data"] = updated_project_data
                    with open(flow_file, "w", encoding="utf-8") as f:
                        f.write(orjson.dumps(flow_data, option=orjson.OPT_INDENT_2).decode())
                    print(f"Updated {flow_file.name}")
                else:
                    print(f"No changes for {flow_file.name}")
            else:
                print(f"Skipping {flow_file.name}: No 'data' field found.")

        except Exception as e:
            print(f"Error processing {flow_file.name}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
