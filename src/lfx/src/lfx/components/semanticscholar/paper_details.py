import asyncio
import urllib.parse

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class PaperDetailsComponent(Component):
    display_name = "Paper Details Fetcher"
    description = "Retrieve deep details for a single paper, including TLDR and direct PDF links."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="paper_id",
            display_name="Paper ID or DOI",
            info="Can be a Semantic Scholar ID, DOI, CorpusID, or arXiv ID (e.g., 'arXiv:1706.03762')",
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
            info="Optional, but highly recommended.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Paper Details", name="data_output", method="fetch_details"),
        Output(display_name="Table", name="dataframe", method="fetch_details_dataframe"),
    ]

    async def fetch_details(self) -> list[Data]:
        """Fetches detailed metadata for a single academic paper."""
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

        # Security Barrier
        if not clean_id:
            error_data = Data(data={"error": "Paper ID empty or could not be extracted."})
            self.status = error_data
            return [error_data]

        encoded_id = urllib.parse.quote(clean_id, safe="")
        base_url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded_id}"

        # Requesting deep fields like tldr and openAccessPdf
        fields = "title,abstract,year,authors,citationCount,url,isOpenAccess,openAccessPdf,tldr,venue,publicationDate"

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["x-api-key"] = api_key.strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(base_url, params={"fields": fields}, headers=headers)

                if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                    await asyncio.sleep(2)
                    error_data = Data(data={"error": "Rate limit reached. Try again later."})
                    self.status = error_data
                    return [error_data]

                if response.status_code == httpx.codes.NOT_FOUND:
                    error_data = Data(data={"error": f"Paper '{clean_id}' not found."})
                    self.status = error_data
                    return [error_data]

                response.raise_for_status()
                paper_data = response.json()
            except httpx.HTTPStatusError as e:
                error_data = Data(data={"error": f"HTTP Error {e.response.status_code}: {e.response.text}"})
                self.status = error_data
                return [error_data]
            except Exception as e:  # noqa: BLE001
                error_data = Data(data={"error": f"Unexpected error: {e!s}"})
                self.status = error_data
                return [error_data]
            else:
                # Safely extract nested JSON objects
                author_names = [author.get("name") for author in paper_data.get("authors", [])]
                tldr_obj = paper_data.get("tldr") or {}
                oa_pdf_obj = paper_data.get("openAccessPdf") or {}

                clean_paper = {
                    "paper_id": paper_data.get("paperId"),
                    "title": paper_data.get("title"),
                    "tldr": tldr_obj.get("text", "No TLDR available."),
                    "abstract": paper_data.get("abstract") or "No abstract available.",
                    "year": paper_data.get("year"),
                    "publication_date": paper_data.get("publicationDate"),
                    "venue": paper_data.get("venue", "Unknown Venue"),
                    "citation_count": paper_data.get("citationCount", 0),
                    "authors": ", ".join(author_names) if author_names else "Unknown",
                    "url": paper_data.get("url"),
                    "is_open_access": paper_data.get("isOpenAccess", False),
                    "pdf_url": oa_pdf_obj.get("url", None),
                }

                result = [Data(data=clean_paper)]
                self.status = result
                return result

    async def fetch_details_dataframe(self) -> DataFrame:
        """Converts the single paper result to a DataFrame."""
        data = await self.fetch_details()
        return DataFrame(data)
