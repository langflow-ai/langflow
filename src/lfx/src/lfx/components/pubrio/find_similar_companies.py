import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioFindSimilarCompaniesComponent(Component):
    display_name = "Pubrio Find Similar Companies"
    description = "Find lookalike companies similar to a given company."
    icon = "building"
    name = "PubrioFindSimilarCompanies"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="query", display_name="Query", info="JSON with lookup_type and value.", tool_mode=True),
        DropdownInput(
            name="lookup_type",
            display_name="Lookup Type",
            options=["domain", "linkedin_url", "domain_search_id"],
            value="domain",
        ),
        MessageTextInput(name="value", display_name="Value", info="The domain, LinkedIn URL, or ID to look up."),
        MessageTextInput(
            name="locations",
            display_name="Locations",
            info="Comma-separated ISO country codes (e.g. US, GB).",
            advanced=True,
        ),
        MessageTextInput(name="exclude_locations", display_name="Exclude Locations", advanced=True),
        IntInput(name="employees_min", display_name="Min Employees", advanced=True),
        IntInput(name="employees_max", display_name="Max Employees", advanced=True),
        IntInput(name="revenue_min", display_name="Min Revenue", advanced=True),
        IntInput(name="revenue_max", display_name="Max Revenue", advanced=True),
        IntInput(name="founded_year_start", display_name="Founded Year Start", advanced=True),
        IntInput(name="founded_year_end", display_name="Founded Year End", advanced=True),
        MessageTextInput(
            name="technologies", display_name="Technologies", info="Comma-separated technology names.", advanced=True
        ),
        MessageTextInput(name="categories", display_name="Technology Categories", advanced=True),
        MessageTextInput(
            name="verticals", display_name="Industry Verticals", info="Comma-separated vertical names.", advanced=True
        ),
        MessageTextInput(name="vertical_categories", display_name="Vertical Categories", advanced=True),
        MessageTextInput(name="vertical_sub_categories", display_name="Vertical Sub-Categories", advanced=True),
        MessageTextInput(name="job_titles", display_name="Job Titles Filter", advanced=True),
        MessageTextInput(name="job_locations", display_name="Job Locations Filter", advanced=True),
        MessageTextInput(
            name="job_posted_date_from",
            display_name="Job Posted Date From",
            info="Start date (YYYY-MM-DD).",
            advanced=True,
        ),
        MessageTextInput(
            name="job_posted_date_to", display_name="Job Posted Date To", info="End date (YYYY-MM-DD).", advanced=True
        ),
        MessageTextInput(name="news_categories", display_name="News Categories Filter", advanced=True),
        MessageTextInput(
            name="news_published_date_from",
            display_name="News Published Date From",
            info="Start date (YYYY-MM-DD).",
            advanced=True,
        ),
        MessageTextInput(
            name="news_published_date_to",
            display_name="News Published Date To",
            info="End date (YYYY-MM-DD).",
            advanced=True,
        ),
        BoolInput(
            name="is_enable_similarity_search", display_name="Enable Similarity Search", value=False, advanced=True
        ),
        FloatInput(name="similarity_score", display_name="Similarity Score", advanced=True),
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        IntInput(name="per_page", display_name="Per Page", value=25, advanced=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run_lookup"),
    ]

    def run_lookup(self) -> DataFrame:
        lookup_type = self.lookup_type
        value = self.value

        if self.query and not value:
            try:
                params = json.loads(self.query)
                if not isinstance(params, dict):
                    raise TypeError
                lookup_type = params.get("lookup_type", lookup_type)
                value = params.get("value", "")
            except (json.JSONDecodeError, TypeError, ValueError):
                value = self.query

        body: dict = {lookup_type: value, "page": self.page or 1, "per_page": self.per_page or 25}

        for key in (
            "locations",
            "exclude_locations",
            "technologies",
            "categories",
            "verticals",
            "vertical_categories",
            "vertical_sub_categories",
            "job_titles",
            "job_locations",
            "news_categories",
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

        if self.job_posted_date_from or self.job_posted_date_to:
            f = self.job_posted_date_from or self.job_posted_date_to
            t = self.job_posted_date_to or self.job_posted_date_from
            body["job_posted_dates"] = [f[:10], t[:10]]
        if self.news_published_date_from or self.news_published_date_to:
            f = self.news_published_date_from or self.news_published_date_to
            t = self.news_published_date_to or self.news_published_date_from
            body["news_published_dates"] = [f[:10], t[:10]]

        if self.is_enable_similarity_search:
            body["is_enable_similarity_search"] = True
        if self.similarity_score is not None:
            body["similarity_score"] = self.similarity_score

        result = pubrio_post(self.api_key, "/companies/lookalikes/search", body)
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
