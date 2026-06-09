import asyncio

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class AuthorPortfolioComponent(Component):
    display_name = "Author Portfolio Fetcher"
    description = "Retrieve the list of papers written by a specific academic author."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="author_id",
            display_name="Author ID",
            info="The unique Semantic Scholar Author ID (e.g., '1440621' for Andrew Ng).",
            tool_mode=True,
        ),
        DataInput(
            name="author_data",
            display_name="Input Data (Connection)",
            info="Connect the output of the 'Search Authors' component here.",
            is_list=True,
            advanced=False,
        ),
        IntInput(
            name="max_results",
            display_name="Max Papers to Fetch",
            info="Limits the number of papers returned.",
            value=20,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Semantic Scholar API Key",
            info="Optional, but highly recommended.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Author Papers", name="data_output", method="fetch_portfolio"),
        Output(display_name="Table", name="dataframe", method="fetch_portfolio_dataframe"),
    ]

    async def fetch_portfolio(self) -> list[Data]:
        clean_id = ""

        # Smart Funnel: Process the DataInput connection (e.g., from Search Authors)
        raw_data = getattr(self, "author_data", None)
        if raw_data and isinstance(raw_data, list) and len(raw_data) > 0:
            first_item = raw_data[0]
            if hasattr(first_item, "data") and isinstance(first_item.data, dict):
                extracted_id = first_item.data.get("author_id", "")
                if extracted_id:
                    clean_id = str(extracted_id).strip()

        # Process the manual text input (fallback)
        if not clean_id:
            raw_text = getattr(self, "author_id", None)
            if raw_text and isinstance(raw_text, str):
                clean_id = raw_text.strip()

        if not clean_id:
            error_data = Data(data={"error": "Author ID cannot be empty or could not be extracted."})
            self.status = error_data
            return [error_data]

        base_url = f"https://api.semanticscholar.org/graph/v1/author/{clean_id}/papers"
        fields = "title,abstract,year,authors,citationCount,url,isOpenAccess"

        all_papers = []
        offset = 0
        pages_fetched = 0
        max_pages = 10  # Failsafe against infinite loops

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["x-api-key"] = api_key.strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            while len(all_papers) < self.max_results and pages_fetched < max_pages:
                pages_fetched += 1

                # Limit calculation based on fetched items
                remaining = self.max_results - len(all_papers)
                params = {"limit": min(100, remaining), "offset": offset, "fields": fields}

                try:
                    response = await client.get(base_url, params=params, headers=headers)

                    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        await asyncio.sleep(2)
                        # Graceful degradation: return what we have so far
                        if all_papers:
                            break
                        error_data = Data(data={"error": "Rate limit reached. Try again."})
                        self.status = error_data
                        return [error_data]

                    if response.status_code == httpx.codes.NOT_FOUND:
                        error_data = Data(data={"error": f"Author ID '{clean_id}' not found."})
                        self.status = error_data
                        return [error_data]

                    response.raise_for_status()
                    response_data = response.json()

                    batch_data = response_data.get("data", [])
                    if not batch_data:
                        break

                    for paper in batch_data:
                        author_names = [author.get("name") for author in paper.get("authors", []) if author.get("name")]

                        clean_paper = {
                            "author_id": clean_id,
                            "paper_id": paper.get("paperId"),
                            "title": paper.get("title"),
                            "abstract": paper.get("abstract") or "No abstract available.",
                            "year": paper.get("year"),
                            "citation_count": paper.get("citationCount", 0),
                            "authors": ", ".join(author_names) if author_names else "Unknown",
                            "url": paper.get("url"),
                            "is_open_access": paper.get("isOpenAccess", False),
                        }
                        all_papers.append(clean_paper)

                        if len(all_papers) >= self.max_results:
                            break

                    offset = response_data.get("next")
                    # Strict None check for offset
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

        # Prioritize the author's most impactful work
        all_papers = sorted(all_papers, key=lambda x: x["citation_count"] or 0, reverse=True)

        results = [Data(data=paper) for paper in all_papers]
        self.status = results
        return results

    async def fetch_portfolio_dataframe(self) -> DataFrame:
        data = await self.fetch_portfolio()
        return DataFrame(data)
