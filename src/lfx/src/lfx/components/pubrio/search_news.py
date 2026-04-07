import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioSearchNewsComponent(Component):
    display_name = "Pubrio Search News"
    description = "Search company news and press releases by category, location, and date."
    icon = "newspaper"
    name = "PubrioSearchNews"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query", display_name="Search Query", info="JSON search parameters or keyword.", tool_mode=True
        ),
        MessageTextInput(name="categories", display_name="Categories", advanced=True),
        MessageTextInput(name="locations", display_name="Locations", advanced=True),
        MessageTextInput(name="company_locations", display_name="Company Locations", advanced=True),
        MessageTextInput(name="companies", display_name="Companies", advanced=True),
        MessageTextInput(name="domains", display_name="Domains", advanced=True),
        MessageTextInput(name="linkedin_urls", display_name="LinkedIn URLs", advanced=True),
        MessageTextInput(name="published_date_from", display_name="Published Date From", info="Start date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="published_date_to", display_name="Published Date To", info="End date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="search_terms", display_name="Search Terms", advanced=True),
        MessageTextInput(name="news_galleries", display_name="News Galleries", advanced=True),
        MessageTextInput(name="news_gallery_ids", display_name="News Gallery IDs", advanced=True),
        MessageTextInput(name="news_languages", display_name="News Languages", advanced=True),
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        IntInput(name="per_page", display_name="Per Page", value=25, advanced=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search"),
    ]

    def search(self) -> DataFrame:
        body: dict = {"page": self.page or 1, "per_page": self.per_page or 25}

        if self.query:
            try:
                parsed = json.loads(self.query)
                if isinstance(parsed, dict):
                    body.update(parsed)
                else:
                    body["search_term"] = self.query
            except (json.JSONDecodeError, TypeError, ValueError):
                body["search_term"] = self.query

        if self.categories:
            body["categories"] = split_csv(self.categories)
        if self.locations:
            body["locations"] = split_csv(self.locations)
        if self.company_locations:
            body["company_locations"] = split_csv(self.company_locations)
        if self.companies:
            body["companies"] = split_csv(self.companies)
        if self.domains:
            body["domains"] = split_csv(self.domains)
        if self.linkedin_urls:
            body["linkedin_urls"] = split_csv(self.linkedin_urls)
        if self.published_date_from or self.published_date_to:
            f = self.published_date_from or self.published_date_to
            t = self.published_date_to or self.published_date_from
            body["published_dates"] = [f[:10], t[:10]]
        if self.search_terms:
            body["search_terms"] = split_csv(self.search_terms)
        if self.news_galleries:
            body["news_galleries"] = split_csv(self.news_galleries)
        if self.news_gallery_ids:
            body["news_gallery_ids"] = split_csv(self.news_gallery_ids)
        if self.news_languages:
            body["news_languages"] = split_csv(self.news_languages)

        result = pubrio_post(self.api_key, "/companies/news/search", body)
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
