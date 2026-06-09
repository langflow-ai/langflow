import asyncio
import random

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class BatchPaperFetcherComponent(Component):
    display_name = "Batch Paper Fetcher"
    description = "Fetch multiple papers in a single highly-optimized API call (solves the N+1 query problem)."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="paper_ids",
            display_name="Paper IDs (Manual Entry)",
            info="List of Paper IDs or DOIs separated by commas.",
            tool_mode=True,
        ),
        DataInput(
            name="paper_data",
            display_name="Input Data (Connection)",
            info="Connect the output of another Semantic Scholar component here.",
            is_list=True,
            advanced=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Semantic Scholar API Key",
            info="Optional, but highly recommended to avoid rate limits.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Batch Papers", name="data_output", method="fetch_batch"),
        Output(display_name="Table", name="dataframe", method="fetch_batch_dataframe"),
    ]

    async def fetch_batch(self) -> list[Data]:
        """Fetches details for multiple papers, combining text and data inputs."""
        clean_ids = []

        # Smart Funnel: Process the DataInput connection
        raw_data = getattr(self, "paper_data", None)
        if raw_data and isinstance(raw_data, list):
            for item in raw_data:
                if hasattr(item, "data") and isinstance(item.data, dict):
                    paper_id = (
                        item.data.get("paper_id")
                        or item.data.get("recommended_paper_id")
                        or item.data.get("citing_paper_id")
                        or item.data.get("referenced_paper_id")
                    )
                    if paper_id:
                        clean_ids.append(str(paper_id).strip())

        # Process the manual text input
        raw_text = getattr(self, "paper_ids", None)
        if raw_text and isinstance(raw_text, str):
            text_ids = [pid.strip() for pid in raw_text.split(",") if pid.strip()]
            clean_ids.extend(text_ids)

        # Remove duplicates while preserving original order
        clean_ids = list(dict.fromkeys(filter(None, clean_ids)))

        if not clean_ids:
            error_msg = "No valid Paper IDs could be extracted from either input"
            self.status = [Data(data={"error": error_msg})]
            return self.status

        # The API has a limit of 500 IDs per Batch request. Enforce it strictly.
        clean_ids = clean_ids[:500]

        base_url = "https://api.semanticscholar.org/graph/v1/paper/batch"
        fields = "title,abstract,year,authors,citationCount,url,isOpenAccess"

        payload = {"ids": clean_ids}
        params = {"fields": fields}

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["x-api-key"] = api_key.strip()

        async with httpx.AsyncClient(timeout=20.0) as client:
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Batch requests use POST instead of GET
                    response = await client.post(base_url, json=payload, params=params, headers=headers)

                    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        if attempt < max_attempts - 1:
                            retry_after = response.headers.get("Retry-After")
                            if retry_after and retry_after.isdigit():
                                delay = int(retry_after)
                            else:
                                delay = 2**attempt + random.uniform(0, 1)  # noqa: S311
                            await asyncio.sleep(delay)
                            continue

                        error_msg = "Rate limit reached. Please wait or use an API Key."
                        self.status = [Data(data={"error": error_msg})]
                        return self.status

                    response.raise_for_status()
                    batch_data = response.json()
                    break
                except httpx.HTTPStatusError as e:
                    error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
                    self.status = [Data(data={"error": error_msg})]
                    return self.status
                except Exception as e:  # noqa: BLE001
                    error_msg = f"Unexpected error: {e!s}"
                    self.status = [Data(data={"error": error_msg})]
                    return self.status

            all_papers = []
            for paper in batch_data:
                # The API might return 'None' for IDs it couldn't find
                if not paper:
                    continue

                author_names = [author.get("name") for author in paper.get("authors", []) if author.get("name")]

                clean_paper = {
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

            results = [Data(data=paper) for paper in all_papers]
            self.status = results
            return results

    async def fetch_batch_dataframe(self) -> DataFrame:
        """Converts results to a DataFrame."""
        data = await self.fetch_batch()
        return DataFrame(data)
