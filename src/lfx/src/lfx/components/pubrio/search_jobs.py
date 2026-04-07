import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioSearchJobsComponent(Component):
    display_name = "Pubrio Search Jobs"
    description = "Search job postings by title, location, keyword, company, and date."
    icon = "briefcase"
    name = "PubrioSearchJobs"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(
            name="query", display_name="Search Query", info="JSON search parameters or keyword.", tool_mode=True
        ),
        MessageTextInput(name="titles", display_name="Job Titles", advanced=True),
        MessageTextInput(name="locations", display_name="Job Locations", advanced=True),
        MessageTextInput(name="exclude_locations", display_name="Exclude Locations", advanced=True),
        MessageTextInput(name="company_locations", display_name="Company Locations", advanced=True),
        MessageTextInput(name="companies", display_name="Companies", advanced=True),
        MessageTextInput(name="domains", display_name="Company Domains", advanced=True),
        MessageTextInput(name="linkedin_urls", display_name="LinkedIn URLs", advanced=True),
        MessageTextInput(name="posted_date_from", display_name="Posted Date From", info="Start date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="posted_date_to", display_name="Posted Date To", info="End date (YYYY-MM-DD).", advanced=True),
        MessageTextInput(name="search_terms", display_name="Search Terms", advanced=True),
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

        if self.titles:
            body["titles"] = split_csv(self.titles)
        if self.locations:
            body["locations"] = split_csv(self.locations)
        if self.exclude_locations:
            body["exclude_locations"] = split_csv(self.exclude_locations)
        if self.company_locations:
            body["company_locations"] = split_csv(self.company_locations)
        if self.companies:
            body["companies"] = split_csv(self.companies)
        if self.domains:
            body["domains"] = split_csv(self.domains)
        if self.linkedin_urls:
            body["linkedin_urls"] = split_csv(self.linkedin_urls)
        if self.posted_date_from or self.posted_date_to:
            f = self.posted_date_from or self.posted_date_to
            t = self.posted_date_to or self.posted_date_from
            body["posted_dates"] = [f[:10], t[:10]]
        if self.search_terms:
            body["search_terms"] = split_csv(self.search_terms)

        result = pubrio_post(self.api_key, "/companies/jobs/search", body)
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
