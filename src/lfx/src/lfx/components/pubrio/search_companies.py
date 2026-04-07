import json


from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioSearchCompaniesComponent(Component):
    display_name = "Pubrio Search Companies"
    description = "Search B2B companies by name, domain, location, industry, technology, headcount, revenue, and more."
    icon = "building"
    name = "PubrioSearchCompanies"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="JSON search parameters or company name to search.",
            tool_mode=True,
        ),
        MessageTextInput(name="company_name", display_name="Company Name", advanced=True),
        MessageTextInput(
            name="domains", display_name="Domains", info="Comma-separated company domains.", advanced=True
        ),
        MessageTextInput(
            name="linkedin_urls",
            display_name="LinkedIn URLs",
            info="Comma-separated LinkedIn company URLs.",
            advanced=True,
        ),
        MessageTextInput(
            name="locations",
            display_name="Locations",
            info="Comma-separated ISO country codes (e.g. US, GB).",
            advanced=True,
        ),
        MessageTextInput(name="exclude_locations", display_name="Exclude Locations", advanced=True),
        MessageTextInput(
            name="places", display_name="Places", info="Comma-separated place names (city, region).", advanced=True
        ),
        MessageTextInput(
            name="keywords",
            display_name="Keywords",
            info="Comma-separated keywords for free-text search.",
            advanced=True,
        ),
        MessageTextInput(
            name="verticals", display_name="Industry Verticals", info="Comma-separated vertical names.", advanced=True
        ),
        MessageTextInput(name="vertical_categories", display_name="Vertical Categories", advanced=True),
        MessageTextInput(name="vertical_sub_categories", display_name="Vertical Sub-Categories", advanced=True),
        MessageTextInput(
            name="technologies", display_name="Technologies", info="Comma-separated technology names.", advanced=True
        ),
        MessageTextInput(name="categories", display_name="Technology Categories", advanced=True),
        MessageTextInput(
            name="companies",
            display_name="Company UUIDs",
            info="Comma-separated domain_search_id UUIDs.",
            advanced=True,
        ),
        IntInput(name="employees_min", display_name="Min Employees", advanced=True),
        IntInput(name="employees_max", display_name="Max Employees", advanced=True),
        IntInput(name="revenue_min", display_name="Min Revenue", advanced=True),
        IntInput(name="revenue_max", display_name="Max Revenue", advanced=True),
        IntInput(name="founded_year_start", display_name="Founded Year Start", advanced=True),
        IntInput(name="founded_year_end", display_name="Founded Year End", advanced=True),
        BoolInput(
            name="is_enable_similarity_search", display_name="Enable Similarity Search", value=False, advanced=True
        ),
        MessageTextInput(name="exclude_fields", display_name="Exclude Fields", advanced=True),
        MessageTextInput(name="job_titles", display_name="Job Titles Filter", advanced=True),
        MessageTextInput(name="job_locations", display_name="Job Locations Filter", advanced=True),
        MessageTextInput(name="news_categories", display_name="News Categories Filter", advanced=True),
        MessageTextInput(name="news_published_date_from", display_name="News Published Date From", info="Start date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="news_published_date_to", display_name="News Published Date To", info="End date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="advertisement_search_terms", display_name="Ad Search Terms", advanced=True),
        MessageTextInput(name="advertisement_target_locations", display_name="Ad Target Locations", advanced=True),
        MessageTextInput(name="job_posted_date_from", display_name="Job Posted Date From", info="Start date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="job_posted_date_to", display_name="Job Posted Date To", info="End date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="advertisement_start_date_from", display_name="Ad Start Date From", info="Start date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="advertisement_start_date_to", display_name="Ad Start Date To", info="End date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="advertisement_end_date_from", display_name="Ad End Date From", info="Start date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="advertisement_end_date_to", display_name="Ad End Date To", info="End date (YYYY-MM-DD).", advanced=True),
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        IntInput(name="per_page", display_name="Per Page", value=25, advanced=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search_companies"),
    ]

    def search_companies(self) -> DataFrame:
        body: dict = {"page": self.page or 1, "per_page": self.per_page or 25}

        # If tool_mode query is JSON, parse it
        if self.query:
            try:
                parsed = json.loads(self.query)
                if isinstance(parsed, dict):
                    body.update(parsed)
                else:
                    body["company_name"] = self.query
            except (json.JSONDecodeError, TypeError, ValueError):
                body["company_name"] = self.query

        if self.company_name:
            body["company_name"] = self.company_name

        for key in (
            "domains",
            "linkedin_urls",
            "locations",
            "exclude_locations",
            "places",
            "verticals",
            "vertical_categories",
            "vertical_sub_categories",
            "technologies",
            "categories",
            "companies",
            "exclude_fields",
            "keywords",
            "job_titles",
            "job_locations",
            "news_categories",
            "advertisement_search_terms",
            "advertisement_target_locations",
        ):
            val = getattr(self, key, None)
            if val:
                body[key] = split_csv(val)

        if self.employees_min or self.employees_max:
            body["employees"] = [self.employees_min or 1, self.employees_max or 1000000]
        if self.revenue_min is not None or self.revenue_max is not None:
            body["revenues"] = [self.revenue_min or 0, self.revenue_max or 999999999999]
        if self.founded_year_start is not None or self.founded_year_end is not None:
            body["founded_dates"] = [self.founded_year_start or 1900, self.founded_year_end or 2100]
        if self.is_enable_similarity_search:
            body["is_enable_similarity_search"] = True

        if self.job_posted_date_from or self.job_posted_date_to:
            f = self.job_posted_date_from or self.job_posted_date_to
            t = self.job_posted_date_to or self.job_posted_date_from
            body["job_posted_dates"] = [f[:10], t[:10]]
        if self.news_published_date_from or self.news_published_date_to:
            f = self.news_published_date_from or self.news_published_date_to
            t = self.news_published_date_to or self.news_published_date_from
            body["news_published_dates"] = [f[:10], t[:10]]
        if self.advertisement_start_date_from or self.advertisement_start_date_to:
            f = self.advertisement_start_date_from or self.advertisement_start_date_to
            t = self.advertisement_start_date_to or self.advertisement_start_date_from
            body["advertisement_start_dates"] = [f[:10], t[:10]]
        if self.advertisement_end_date_from or self.advertisement_end_date_to:
            f = self.advertisement_end_date_from or self.advertisement_end_date_to
            t = self.advertisement_end_date_to or self.advertisement_end_date_from
            body["advertisement_end_dates"] = [f[:10], t[:10]]

        result = pubrio_post(self.api_key, "/companies/search", body)
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
