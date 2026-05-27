import asyncio
import urllib.parse

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class AIRecommendationsComponent(Component):
    display_name = "AI Paper Recommendations"
    description = "Get AI-driven paper recommendations based on a specific academic paper."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="paper_id",
            display_name="Source Paper ID",
            info="The Semantic Scholar ID, DOI, or arXiv ID to base recommendations on.",
            tool_mode=True,
        ),
        DataInput(
            name="paper_data",
            display_name="Input Data (Connection)",
            info="Connect the output of another Semantic Scholar component here.",
            is_list=True,
            advanced=False,
        ),
        IntInput(
            name="max_results",
            display_name="Max Recommendations",
            info="Number of recommended papers to retrieve (Max 500).",
            value=10,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Semantic Scholar API Key",
            info="Optional, but highly recommended.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Recommendations", name="data_output", method="fetch_recommendations"),
        Output(display_name="Table", name="dataframe", method="fetch_recommendations_dataframe"),
    ]

    async def fetch_recommendations(self) -> list[Data]:
        """Fetches AI recommendations in a single optimized request."""
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
            error_data = Data(data={"error": "Source Paper ID empty or could not be extracted"})
            self.status = error_data
            return [error_data]

        encoded_id = urllib.parse.quote(clean_id, safe="")
        base_url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{encoded_id}"
        fields = "title,abstract,year,authors,citationCount,url,isOpenAccess"

        max_res = getattr(self, "max_results", 10)

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            headers["x-api-key"] = api_key.strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Semantic Scholar limits recommendations to 500 max per request
            params = {"limit": min(500, max_res), "fields": fields}

            try:
                response = await client.get(base_url, params=params, headers=headers)

                if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                    await asyncio.sleep(2)
                    error_data = Data(data={"error": "Rate limit reached. Try again later."})
                    self.status = error_data
                    return [error_data]

                if response.status_code == httpx.codes.NOT_FOUND:
                    error_data = Data(data={"error": f"Source Paper '{clean_id}' not found."})
                    self.status = error_data
                    return [error_data]

                response.raise_for_status()
                response_data = response.json()
            except httpx.HTTPStatusError as e:
                error_data = Data(data={"error": f"HTTP Error {e.response.status_code}: {e.response.text}"})
                self.status = error_data
                return [error_data]
            except Exception as e:  # noqa: BLE001
                error_data = Data(data={"error": f"Unexpected error: {e!s}"})
                self.status = error_data
                return [error_data]
            else:
                recommended_papers = response_data.get("recommendedPapers", [])

                if not recommended_papers:
                    error_msg = f"No AI recommendations found for Paper ID '{clean_id}' (might lack citation network)."
                    error_data = Data(data={"error": error_msg})
                    self.status = error_data
                    return [error_data]

                all_papers = []
                for paper in recommended_papers:
                    author_names = [author.get("name") for author in paper.get("authors", [])]

                    clean_paper = {
                        "source_paper_id": clean_id,
                        "recommended_paper_id": paper.get("paperId"),
                        "title": paper.get("title"),
                        "abstract": paper.get("abstract") or "No abstract available.",
                        "year": paper.get("year"),
                        "citation_count": paper.get("citationCount", 0),
                        "authors": ", ".join(author_names) if author_names else "Unknown",
                        "url": paper.get("url"),
                        "is_open_access": paper.get("isOpenAccess", False),
                    }
                    all_papers.append(clean_paper)

                max_res = getattr(self, "max_results", 10)
                results = [Data(data=p) for p in all_papers[:max_res]]
                self.status = results
                return results

    async def fetch_recommendations_dataframe(self) -> DataFrame:
        """Converts results to a DataFrame."""
        data = await self.fetch_recommendations()
        return DataFrame(data)
