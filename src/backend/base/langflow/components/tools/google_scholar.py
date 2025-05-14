from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, Output
from langflow.schema import Data, DataFrame

from scholarly import scholarly
import datetime


class GoogleScholarComponent(Component):
    display_name = "Google Scholar"
    description = "Search and retrieve papers from Google Scholar using scholarly (unofficial)"
    icon = "GoogleScholar"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Key word",
            info="Search query for Google Scholar",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Number of search results to fetch",
            value=10,
        ),
        IntInput(
            name="days_ago",
            display_name="Days Ago",
            info="Limit to papers published in the last N days (approximated by publication year)",
            value=365,
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    def search_papers(self) -> list[Data]:
        try:
            search_results = scholarly.search_pubs(self.query)
            papers = []

            # Calculate cutoff year from days_ago
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=self.days_ago)
            cutoff_year = cutoff_date.year

            fetched = 0
            while fetched < self.max_results:
                try:
                    result = next(search_results)
                except StopIteration:
                    break

                pub_year_str = result.get("bib", {}).get("pub_year")
                pub_year = int(pub_year_str) if pub_year_str and pub_year_str.isdigit() else None

                if pub_year is not None and pub_year < cutoff_year:
                    continue  # Filter out old papers

                paper = {
                    "title": result.get("bib", {}).get("title"),
                    "authors": result.get("bib", {}).get("author"),
                    "abstract": result.get("bib", {}).get("abstract"),
                    "venue": result.get("bib", {}).get("venue"),
                    "pub_year": pub_year,
                    "citation_count": result.get("num_citations"),
                    "link": result.get("pub_url"),
                }

                papers.append(Data(data=paper))
                fetched += 1

            self.status = papers
            return papers

        except Exception as e:
            error_data = Data(data={"error": str(e)})
            self.status = error_data
            return [error_data]

    def as_dataframe(self) -> DataFrame:
        data = self.search_papers()
        return DataFrame(data=[d.data for d in data])
