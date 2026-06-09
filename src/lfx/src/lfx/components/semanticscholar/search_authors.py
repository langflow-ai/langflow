import asyncio

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class SearchAuthorsComponent(Component):
    display_name = "Semantic Scholar Author Search"
    description = "Search for academic authors by name to retrieve their ID, h-index, and metrics."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="search_query",
            display_name="Author Name",
            info="The name of the author to search (e.g., 'Andrew Ng' or 'Yoshua Bengio').",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Limits the number of author profiles returned.",
            value=10,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Semantic Scholar API Key",
            info="Optional, but highly recommended to avoid rate limits.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Author Profiles", name="data_output", method="search_authors"),
        Output(display_name="Table", name="dataframe", method="search_authors_dataframe"),
    ]

    async def search_authors(self) -> list[Data]:
        """Searches for authors and retrieves their metrics."""
        query_val = getattr(self, "search_query", "") or ""
        clean_query = query_val.strip()

        if not clean_query:
            return [Data(data={"error": "Search query cannot be empty."})]

        base_url = "https://api.semanticscholar.org/graph/v1/author/search"
        fields = "name,affiliations,paperCount,citationCount,hIndex,url"

        all_authors = []
        offset = 0
        pages_fetched = 0
        max_pages = 10

        max_res = getattr(self, "max_results", 10)

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["x-api-key"] = api_key.strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            while len(all_authors) < max_res and pages_fetched < max_pages:
                pages_fetched += 1

                remaining = max_res - len(all_authors)
                params = {"query": clean_query, "limit": min(100, remaining), "offset": offset, "fields": fields}

                try:
                    response = await client.get(base_url, params=params, headers=headers)

                    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        await asyncio.sleep(2)
                        if all_authors:
                            break
                        error_data = Data(data={"error": "Rate limit reached. Try again."})
                        self.status = error_data
                        return [error_data]

                    response.raise_for_status()
                    response_data = response.json()

                    batch_data = response_data.get("data", [])
                    if not batch_data:
                        break

                    for author in batch_data:
                        # Clean up affiliations list into a comma-separated string
                        affiliations = author.get("affiliations", [])
                        clean_affiliations = ", ".join(affiliations) if affiliations else "Unknown Affiliation"

                        clean_author = {
                            "author_id": author.get("authorId"),
                            "name": author.get("name"),
                            "affiliations": clean_affiliations,
                            "paper_count": author.get("paperCount", 0),
                            "citation_count": author.get("citationCount", 0),
                            "h_index": author.get("hIndex", 0),
                            "url": author.get("url"),
                        }
                        all_authors.append(clean_author)

                        if len(all_authors) >= max_res:
                            break

                    offset = response_data.get("next")
                    if offset is None:
                        break

                    await asyncio.sleep(1)

                except httpx.HTTPStatusError as e:
                    error_data = Data(data={"error": f"HTTP Error {e.response.status_code}: {e.response.text}"})
                    self.status = error_data
                    return [error_data]
                except Exception as e:  # noqa: BLE001
                    error_data = Data(data={"error": f"Unexpected error: {e!s}"})
                    self.status = error_data
                    return [error_data]

        # Prioritize authors with the highest h-index (most impactful)
        all_authors = sorted(all_authors, key=lambda x: x["h_index"] or 0, reverse=True)

        results = [Data(data=author) for author in all_authors]
        self.status = results
        return results

    async def search_authors_dataframe(self) -> DataFrame:
        """Converts results to a DataFrame."""
        data = await self.search_authors()
        return DataFrame(data)
