import json

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

from ._base import pubrio_post, split_csv


class PubrioSearchPeopleComponent(Component):
    display_name = "Pubrio Search People"
    description = "Search business professionals by name, title, department, seniority, location, and company."
    icon = "users"
    name = "PubrioSearchPeople"

    inputs = [
        SecretStrInput(name="api_key", display_name="Pubrio API Key", required=True),
        MessageTextInput(name="query", display_name="Search Query", info="JSON search parameters or free-text search.", tool_mode=True),
        MessageTextInput(name="people_name", display_name="Person Name", advanced=True),
        MessageTextInput(name="people_titles", display_name="Job Titles", info="Comma-separated titles (fuzzy match).", advanced=True),
        MessageTextInput(name="management_levels", display_name="Management Levels", info="c_level, director, entry, head, manager, senior, vp", advanced=True),
        MessageTextInput(name="departments", display_name="Departments", info="master_engineering, master_finance, master_sales, etc.", advanced=True),
        MessageTextInput(name="department_functions", display_name="Department Functions", advanced=True),
        MessageTextInput(name="people_locations", display_name="Person Locations", info="Comma-separated ISO country codes.", advanced=True),
        MessageTextInput(name="company_locations", display_name="Company Locations", advanced=True),
        MessageTextInput(name="domains", display_name="Company Domains", info="Comma-separated domains.", advanced=True),
        MessageTextInput(name="linkedin_urls", display_name="LinkedIn URLs", advanced=True),
        MessageTextInput(name="company_linkedin_urls", display_name="Company LinkedIn URLs", advanced=True),
        MessageTextInput(name="companies", display_name="Company UUIDs", advanced=True),
        MessageTextInput(name="peoples", display_name="People UUIDs", advanced=True),
        IntInput(name="employees_min", display_name="Min Employees", advanced=True),
        IntInput(name="employees_max", display_name="Max Employees", advanced=True),
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        IntInput(name="per_page", display_name="Per Page", value=25, advanced=True),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search_people"),
    ]

    def search_people(self) -> DataFrame:
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

        for key in ("people_name",):
            val = getattr(self, key, None)
            if val:
                body[key] = val

        for key in ("people_titles", "management_levels", "departments", "department_functions",
                     "people_locations", "company_locations", "domains", "linkedin_urls",
                     "company_linkedin_urls", "companies", "peoples"):
            val = getattr(self, key, None)
            if val:
                body[key] = split_csv(val)

        if self.employees_min or self.employees_max:
            body["employees"] = [self.employees_min or 1, self.employees_max or 1000000]

        result = pubrio_post(self.api_key, "/people/search", body)
        records = result.get("data", result) if isinstance(result, dict) else result
        if isinstance(records, list):
            data = [Data(text=json.dumps(r), data=r) for r in records]
        else:
            data = [Data(text=json.dumps(records), data=records if isinstance(records, dict) else {"result": records})]
        self.status = data
        return DataFrame(data)
