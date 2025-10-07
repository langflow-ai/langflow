from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langflow.api.v1.knowledge_bases import get_kb_root_path
from langflow.custom import Component
from langflow.io import DropdownInput, IntInput, MultilineInput, MultiselectInput, Output
from langflow.schema import Data
from langflow.services.deps import get_settings_service
from loguru import logger


class KnowledgeHubSearchComponent(Component):
    display_name = "Knowledge Hub Search"
    description = (
        "This component is used to search for information in the knowledge hub."
    )
    icon = "Autonomize"
    name = "KnowledgeHubSearch"

    def __init__(self, **kwargs):
        self._hub_data: list[dict[str, str]] = []
        self._selected_hub_names: list[str] = []
        super().__init__(**kwargs)

    async def update_build_config(
        self, build_config: dict, field_value: Any, field_name: str | None = None
    ):
        """Update the build configuration based on field changes."""
        logger.info(f"update_build_config called with field_name: {field_name}")

        if field_name == "selected_hubs":
            try:
                # Get real knowledge bases from API
                options = []

                try:
                    kb_root_path = get_kb_root_path()
                    # For demo purposes, get a basic user directory (you'd get this from current user in real app)
                    # This assumes knowledge bases are stored in user directories
                    if kb_root_path.exists():
                        for user_dir in kb_root_path.iterdir():
                            if user_dir.is_dir() and not user_dir.name.startswith('.'):
                                for kb_dir in user_dir.iterdir():
                                    if kb_dir.is_dir() and not kb_dir.name.startswith('.'):
                                        # Convert directory name to display name
                                        display_name = kb_dir.name.replace("_", " ").replace("-", " ").title()
                                        options.append(display_name)
                                        self._hub_data.append({"id": kb_dir.name, "name": display_name, "path": str(kb_dir)})

                    if not options:
                        options = ["No knowledge bases found"]

                except Exception as e:
                    logger.error(f"Error fetching knowledge bases: {e}")
                    options = ["Error loading knowledge bases"]

                logger.info(f"Available knowledge bases: {options}")

                build_config["selected_hubs"]["options"] = options

                if field_value and isinstance(field_value, list):
                    self._selected_hub_names = field_value
                    logger.info(
                        f"Stored selected hub names: {self._selected_hub_names}"
                    )

                return build_config
            except Exception as e:
                logger.exception(f"Error in update_build_config: {e!s}")
                raise
        return build_config

    inputs = [
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
        ),
        MultiselectInput(
            name="selected_hubs",
            display_name="Data Sources",
            value=[],
            refresh_button=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["similarity", "semantic", "keyword", "hybrid"],
            value="similarity",
            info="Type of search to perform",
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            value=10,
            info="Number of top results to retrieve",
        ),
    ]

    outputs = [
        Output(
            display_name="Query Results",
            name="query_results",
            method="build_output",
        ),
    ]

    async def build_output(self) -> Data:
        """Generate the output based on selected knowledge hubs."""
        try:
            # Get configuration values
            search_type = getattr(self, 'search_type', 'similarity')
            top_k = getattr(self, 'top_k', 10)

            if not self._selected_hub_names:
                logger.warning("No knowledge hubs selected.")
                return Data(
                    text="No knowledge bases selected for search.",
                    data={"query_results": [], "error": "No knowledge bases selected"}
                )

            # Perform real search using Chroma
            all_results = []
            used_sources = []

            try:
                kb_root_path = get_kb_root_path()

                for selected_name in self._selected_hub_names:
                    if selected_name in ["No knowledge bases found", "Error loading knowledge bases"]:
                        continue

                    # Find the corresponding hub data
                    hub_info = None
                    for hub in self._hub_data:
                        if hub["name"] == selected_name:
                            hub_info = hub
                            break

                    if not hub_info:
                        logger.warning(f"Could not find hub info for: {selected_name}")
                        continue

                    try:
                        # Create Chroma instance for this knowledge base
                        kb_path = Path(hub_info["path"])
                        if not kb_path.exists():
                            logger.warning(f"Knowledge base path does not exist: {kb_path}")
                            continue

                        chroma = Chroma(
                            persist_directory=str(kb_path),
                            collection_name=hub_info["id"],
                        )

                        # Perform similarity search
                        results = chroma.similarity_search_with_score(
                            query=self.search_query,
                            k=top_k
                        )

                        # Process results
                        for doc, score in results:
                            result_item = {
                                "metadata": {
                                    "content": doc.page_content,
                                    "source": hub_info["name"],
                                    "score": float(score),
                                    **doc.metadata
                                }
                            }
                            all_results.append(result_item)

                        used_sources.append(selected_name)
                        logger.info(f"Found {len(results)} results from {selected_name}")

                    except Exception as e:
                        logger.error(f"Error searching knowledge base {selected_name}: {e}")
                        continue

                # Sort all results by score (lower is better for similarity)
                all_results.sort(key=lambda x: x["metadata"].get("score", float('inf')))

                # Limit to top_k results overall
                all_results = all_results[:top_k]

                # Create plain text output
                if all_results:
                    contents = [
                        result["metadata"]["content"]
                        for result in all_results
                    ]
                    plain_text = "\n\n=== NEW CHUNK ===\n\n".join(contents)
                else:
                    plain_text = "No relevant results found in the selected knowledge bases."

                logger.info(f"Search completed. Found {len(all_results)} total results across {len(used_sources)} sources")

            except Exception as e:
                logger.error(f"Error during knowledge base search: {e}")
                return Data(
                    text=f"Error searching knowledge bases: {str(e)}",
                    data={"query_results": [], "error": str(e)}
                )

            data = Data(
                text=plain_text,
                data={
                    "result": all_results,
                    "used_data_sources": used_sources,
                    "search_type": search_type,
                    "top_k": top_k,
                    "total_results": len(all_results)
                },
            )
            self.status = data
            return data

        except Exception as e:
            logger.error(f"Error in build_output: {e!s}")
            return Data(
                text=f"Error in search: {str(e)}",
                data={"query_results": [], "error": str(e)}
            )