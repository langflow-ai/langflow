import datetime
import xml.etree.ElementTree as ET

import requests

from langflow.custom import Component
from langflow.io import IntInput, MessageTextInput, Output
from langflow.schema import Data, DataFrame


class PubMedComponent(Component):
    display_name = "PubMed"
    description = "Search and retrieve papers from PubMed"
    icon = "PubMed"

    inputs = [
        MessageTextInput(
            name="keyword",
            display_name="Keyword",
            info="Keyword to search for in PubMed",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of results to return",
            value=10,
        ),
        IntInput(
            name="days_ago",
            display_name="Days Ago",
            info="Limit to papers published in the last N days",
            value=7,
        ),
        MessageTextInput(
            name="api_key",
            display_name="NCBI API Key",
            info="Your PubMed NCBI API Key (optional)",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="search_papers"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def search_papers(self) -> list[Data]:
        try:
            article_ids = self._search_pubmed()
            papers = []

            for pmid in article_ids:
                paper = self._fetch_article_details(pmid)
                if paper:
                    papers.append(paper)

            results = [Data(data=p) for p in papers]
            self.status = results
        except Exception as e:
            error = {"error": str(e)}
            self.status = Data(data=error)
            return [Data(data=error)]
        else:
            return results

    def _search_pubmed(self) -> list[str]:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        today = datetime.datetime.now()
        past = today - datetime.timedelta(days=self.days_ago)
        date_range = f"{past.strftime('%Y/%m/%d')}:{today.strftime('%Y/%m/%d')}[pdat]"

        query = f"({self.keyword}) AND {date_range}"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": self.max_results,
            "retmode": "xml",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        resp = requests.get(base_url, params=params)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        return [id_elem.text for id_elem in root.findall(".//IdList/Id")]

    def _fetch_article_details(self, pmid: str) -> dict | None:
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            return None

        root = ET.fromstring(resp.content)
        title = root.findtext(".//ArticleTitle", default="No Title")
        abstract = root.findtext(".//AbstractText", default="No Abstract")
        journal = root.findtext(".//Journal/Title", default="Unknown Journal")
        doi = root.findtext(".//ArticleId[@IdType='doi']", default="No DOI")

        authors = []
        for author in root.findall(".//AuthorList/Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            if last or fore:
                authors.append(f"{fore} {last}".strip())

        pub_date = self._extract_pub_date(root)
        access_link = f"https://doi.org/{doi}" if doi != "No DOI" else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        return {
            "pmid": pmid,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "journal": journal,
            "doi": doi,
            "access_link": access_link,
            "publication_date": pub_date,
        }

    def _extract_pub_date(self, root) -> str:
        for path in [".//PubMedPubDate[@PubStatus='pubmed']", ".//ArticleDate", ".//PubDate"]:
            date_elem = root.find(path)
            if date_elem is not None:
                year = date_elem.findtext("Year", "0000")
                month = date_elem.findtext("Month", "01")
                day = date_elem.findtext("Day", "01")
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return "Unknown"

    def as_dataframe(self) -> DataFrame:
        data = self.search_papers()
        if isinstance(data, list):
            return DataFrame(data=[d.data for d in data])
        return DataFrame(data=[data.data])
