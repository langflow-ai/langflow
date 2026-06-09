import asyncio
import re

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class SemanticScholarSearchComponent(Component):
    display_name = "Semantic Scholar Search"
    description = "Search academic papers with advanced filters (Open Access, Citations, Sorting)."
    icon = "SemanticScholar"

    inputs = [
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="Topic to search (e.g., 'large language models')",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Total number of papers to fetch after applying filters.",
            value=20,
        ),
        DropdownInput(
            name="sort_by",
            display_name="Sort Results By",
            options=["Relevance (API Default)", "Highest Citations", "Newest First"],
            value="Relevance (API Default)",
            advanced=True,
        ),
        BoolInput(
            name="only_open_access",
            display_name="Only Open Access (PDFs)",
            info="If True, only returns papers that are free to read.",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="min_citations",
            display_name="Minimum Citations",
            info="Filter out papers with fewer citations than this number.",
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="year_filter",
            display_name="Year Range",
            info="Filter by year, e.g., '2020-2024' or '2023-'",
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Semantic Scholar API Key",
            info="Optional, but highly recommended to avoid rate limits.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data_output", method="search_papers"),
        Output(display_name="Table", name="dataframe", method="search_papers_dataframe"),
    ]

    async def search_papers(self) -> list[Data]:
        if not self.search_query:
            return [Data(data={"error": "Search query cannot be empty."})]

        base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        fields = "title,abstract,year,authors,citationCount,url,isOpenAccess"

        all_papers = []
        offset = 0
        pages_fetched = 0
        max_pages = 10  # Failsafe against infinite loops

        headers = {"User-Agent": "Langflow-Academic-Suite/2.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key.strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            while len(all_papers) < self.max_results and pages_fetched < max_pages:
                pages_fetched += 1
                params = {"query": self.search_query.strip(), "limit": 100, "offset": offset, "fields": fields}

                # Year validation
                year_val = getattr(self, "year_filter", None)
                if year_val:
                    clean_year = year_val.strip()
                    if not re.fullmatch(r"\d{4}|\d{4}-\d{4}|\d{4}-|-\d{4}", clean_year):
                        return [Data(data={"error": "Invalid year format. Use YYYY, YYYY-YYYY, YYYY-, or -YYYY."})]
                    params["year"] = clean_year

                try:
                    response = await client.get(base_url, params=params, headers=headers)

                    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        await asyncio.sleep(2)
                        if all_papers:
                            break
                        error_msg = "Rate limit reached. Try again later or use an API key."
                        error_data = Data(data={"error": error_msg})
                        self.status = [error_data]
                        return self.status

                    response.raise_for_status()
                    response_data = response.json()

                    batch_data = response_data.get("data", [])
                    if not batch_data:
                        break

                    for paper in batch_data:
                        # Client-side filtering
                        if getattr(self, "only_open_access", False) and not paper.get("isOpenAccess"):
                            continue

                        cit_count = paper.get("citationCount") or 0
                        if cit_count < getattr(self, "min_citations", 0):
                            continue

                        author_names = [author.get("name") for author in paper.get("authors", [])]
                        clean_paper = {
                            "paper_id": paper.get("paperId"),
                            "title": paper.get("title"),
                            "abstract": paper.get("abstract") or "No abstract available.",
                            "year": paper.get("year"),
                            "citation_count": cit_count,
                            "authors": ", ".join(author_names) if author_names else "Unknown",
                            "url": paper.get("url"),
                            "is_open_access": paper.get("isOpenAccess", False),
                        }
                        all_papers.append(clean_paper)

                        if len(all_papers) >= self.max_results:
                            break

                    # Pagination logic
                    offset = response_data.get("next")
                    if offset is None:
                        break

                    await asyncio.sleep(1)

                except Exception as e:  # noqa: BLE001
                    return [Data(data={"error": f"API Error: {e!s}"})]

        # Final sorting
        sort_choice = getattr(self, "sort_by", "Relevance (API Default)")
        if sort_choice == "Highest Citations":
            all_papers = sorted(all_papers, key=lambda x: x["citation_count"], reverse=True)
        elif sort_choice == "Newest First":
            all_papers = sorted(all_papers, key=lambda x: x["year"] or 0, reverse=True)

        results = [Data(data=paper) for paper in all_papers[: self.max_results]]
        self.status = results
        return results

    async def search_papers_dataframe(self) -> DataFrame:
        """Returns the search results as a DataFrame."""
        data = await self.search_papers()
        return DataFrame(data)
