import urllib.request
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring

from langflow.custom.custom_component.component import Component
from langflow.io import DropdownInput, IntInput, MessageTextInput, Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


class ArXivComponent(Component):
    display_name = "arXiv"
    description = "Search and retrieve papers from arXiv.org"
    icon = "arXiv"

    inputs = [
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            info="The search query for arXiv papers (e.g., 'quantum computing')",
            tool_mode=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Field",
            info="The field to search in",
            options=["all", "title", "abstract", "author", "cat"],  # cat is for category
            value="all",
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of results to return",
            value=10,
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="search_papers_dataframe"),
    ]

    def build_query_url(self) -> str:
        """Build the arXiv API query URL."""
        base_url = "http://export.arxiv.org/api/query?"

        # Build the search query
        search_query = f"{self.search_type}:{self.search_query}"

        # URL parameters
        params = {
            "search_query": search_query,
            "max_results": str(self.max_results),
        }

        # Convert params to URL query string
        query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])

        return base_url + query_string

    def parse_atom_response(self, response_text: str) -> list[dict]:
        """Parse the Atom XML response from arXiv."""
        # Parse XML safely using defusedxml
        root = fromstring(response_text)

        # Define namespace dictionary for XML parsing
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        papers = []
        # Process each entry (paper)
        for entry in root.findall("atom:entry", ns):
            paper = {
                "id": self._get_text(entry, "atom:id", ns),
                "title": self._get_text(entry, "atom:title", ns),
                "summary": self._get_text(entry, "atom:summary", ns),
                "published": self._get_text(entry, "atom:published", ns),
                "updated": self._get_text(entry, "atom:updated", ns),
                "authors": [author.find("atom:name", ns).text for author in entry.findall("atom:author", ns)],
                "arxiv_url": self._get_link(entry, "alternate", ns),
                "pdf_url": self._get_link(entry, "related", ns),
                "comment": self._get_text(entry, "arxiv:comment", ns),
                "journal_ref": self._get_text(entry, "arxiv:journal_ref", ns),
                "primary_category": self._get_category(entry, ns),
                "categories": [cat.get("term") for cat in entry.findall("atom:category", ns)],
            }
            papers.append(paper)

        return papers

    def _get_text(self, element: Element, path: str, ns: dict) -> str | None:
        """Safely extract text from an XML element."""
        el = element.find(path, ns)
        return el.text.strip() if el is not None and el.text else None

    def _get_link(self, element: Element, rel: str, ns: dict) -> str | None:
        """Get link URL based on relation type."""
        for link in element.findall("atom:link", ns):
            if link.get("rel") == rel:
                return link.get("href")
        return None

    def _get_category(self, element: Element, ns: dict) -> str | None:
        """Get primary category."""
        cat = element.find("arxiv:primary_category", ns)
        return cat.get("term") if cat is not None else None

    def run_model(self) -> DataFrame:
        return self.search_papers_dataframe()

    def search_papers(self) -> list[Data]:
        """Search arXiv and return results."""
        try:
            # Build the query URL
            url = self.build_query_url()

            # Validate URL scheme and host
            parsed_url = urlparse(url)
            if parsed_url.scheme not in {"http", "https"}:
                error_msg = f"Invalid URL scheme: {parsed_url.scheme}"
                raise ValueError(error_msg)
            if parsed_url.hostname != "export.arxiv.org":
                error_msg = f"Invalid host: {parsed_url.hostname}"
                raise ValueError(error_msg)

            # Create a custom opener that only allows http/https schemes
            class RestrictedHTTPHandler(urllib.request.HTTPHandler):
                def http_open(self, req):
                    return super().http_open(req)

            class RestrictedHTTPSHandler(urllib.request.HTTPSHandler):
                def https_open(self, req):
                    return super().https_open(req)

            # Build opener with restricted handlers
            opener = urllib.request.build_opener(RestrictedHTTPHandler, RestrictedHTTPSHandler)
            urllib.request.install_opener(opener)

            # Make the request with validated URL using restricted opener
            response = opener.open(url)
            response_text = response.read().decode("utf-8")

            # Parse the response
            papers = self.parse_atom_response(response_text)

            # Convert to Data objects
            results = [Data(data=paper) for paper in papers]
            self.status = results
        except (urllib.error.URLError, ValueError) as e:
            error_data = Data(data={"error": f"Request error: {e!s}"})
            self.status = error_data
            return [error_data]
        else:
            return results

    def search_papers_dataframe(self) -> DataFrame:
        """Convert the Arxiv search results to a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the search results.
        """
        data = self.search_papers()
        return DataFrame(data)
