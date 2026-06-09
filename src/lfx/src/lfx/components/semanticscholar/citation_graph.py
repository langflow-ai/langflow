import asyncio
import urllib.parse

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class CitationGraphComponent(Component):
    display_name = "Citation Graph Fetcher"
    description = "Retrieve papers that cited a specific academic paper (Forward Snowballing)."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="paper_id",
            display_name="Paper ID or DOI",
            info="Can be a Semantic Scholar ID, DOI, or arXiv ID (e.g., 'arXiv:1706.03762')",
            tool_mode=True,
        ),
        DataInput(
            name="paper_data",
            display_name="Input Data (Connection)",
            info="Connect the output of 'Semantic Scholar Search' or similar components here.",
            is_list=True,
            advanced=False,
        ),
        IntInput(
            name="max_results",
            display_name="Max Citations to Fetch",
            info="Limits the number of citing papers returned to prevent overload.",
            value=20,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Semantic Scholar API Key",
            info="Optional, but highly recommended to avoid rate limits.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Citing Papers", name="data_output", method="fetch_citations"),
        Output(display_name="Table", name="dataframe", method="fetch_citations_dataframe"),
    ]

    async def fetch_citations(self) -> list[Data]:
        """Fetches citing papers with pagination and error handling."""
        clean_id = ""

        # Smart Funnel: Process the DataInput connection
        raw_data = getattr(self, "paper_data", None)
        if raw_data and isinstance(raw_data, list) and len(raw_data) > 0:
            first_item = raw_data[0]
            if hasattr(first_item, "data") and isinstance(first_item.data, dict):
                extracted_id = (
                    first_item.data.get("paper_id")
                    or first_item.data.get("recommended_paper_id")
                    or first_item.data.get("citing_paper_id")
                    or first_item.data.get("referenced_paper_id")
                )
                if extracted_id:
                    clean_id = str(extracted_id).strip()

        # Process the manual text input (fallback)
        if not clean_id:
            raw_text = getattr(self, "paper_id", None)
            if raw_text and isinstance(raw_text, str):
                clean_id = raw_text.strip()

        if not clean_id:
            error_data = Data(data={"error": "Paper ID empty or could not be extracted"})
            self.status = error_data
            return [error_data]

        encoded_id = urllib.parse.quote(clean_id, safe="")
        base_url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded_id}/citations"
        fields = "title,abstract,year,authors,citationCount,url,isOpenAccess"

        all_citing_papers = []
        offset = 0
        pages_fetched = 0
        max_pages = 10

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["x-api-key"] = api_key.strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            while len(all_citing_papers) < self.max_results and pages_fetched < max_pages:
                pages_fetched += 1
                remaining = self.max_results - len(all_citing_papers)
                params = {"limit": min(100, remaining), "offset": offset, "fields": fields}

                try:
                    response = await client.get(base_url, params=params, headers=headers)

                    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        await asyncio.sleep(2)
                        # If already has some data, break and return partial results
                        if all_citing_papers:
                            break
                        error_data = Data(data={"error": "Rate limit reached. Try again."})
                        self.status = error_data
                        return [error_data]

                    if response.status_code == httpx.codes.NOT_FOUND:
                        error_data = Data(data={"error": f"Paper ID '{clean_id}' not found."})
                        self.status = error_data
                        return [error_data]

                    response.raise_for_status()
                    response_data = response.json()

                    batch_data = response_data.get("data", [])
                    if not batch_data:
                        break

                    for citation_record in batch_data:
                        paper_info = citation_record.get("citingPaper")

                        # Skip records without citingPaper info
                        if paper_info:
                            author_names = [author.get("name") for author in paper_info.get("authors", [])]

                            clean_paper = {
                                "source_paper_id": clean_id,
                                "citing_paper_id": paper_info.get("paperId"),
                                "title": paper_info.get("title"),
                                "abstract": paper_info.get("abstract") or "No abstract available.",
                                "year": paper_info.get("year"),
                                "citation_count": paper_info.get("citationCount", 0),
                                "authors": ", ".join(author_names) if author_names else "Unknown",
                                "url": paper_info.get("url"),
                                "is_open_access": paper_info.get("isOpenAccess", False),
                                "citation_contexts": citation_record.get("contexts", []),
                                "citation_intents": citation_record.get("intents", []),
                            }
                            all_citing_papers.append(clean_paper)

                        if len(all_citing_papers) >= self.max_results:
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

        # Local sorting to prioritize impact
        all_citing_papers = sorted(all_citing_papers, key=lambda x: x["citation_count"] or 0, reverse=True)

        results = [Data(data=paper) for paper in all_citing_papers]
        self.status = results
        return results

    async def fetch_citations_dataframe(self) -> DataFrame:
        """Converts the citation results to a DataFrame."""
        data = await self.fetch_citations()
        return DataFrame(data)
