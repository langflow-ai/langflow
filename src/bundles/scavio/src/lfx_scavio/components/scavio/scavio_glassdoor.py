from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Company Search": Endpoint(
        path="/api/v1/glassdoor/companies",
        credits=1,
        fields=("query",),
        required=("query",),
        result_keys=("results",),
    ),
    "Company Details": Endpoint(
        path="/api/v1/glassdoor/company",
        credits=1,
        fields=("employer_id", "company", "url"),
    ),
    "Reviews": Endpoint(
        path="/api/v1/glassdoor/reviews",
        credits=1,
        fields=("employer_id", "company", "url", "category", "employment_status"),
    ),
    "Salaries": Endpoint(
        path="/api/v1/glassdoor/salaries",
        credits=1,
        fields=("employer_id", "company", "url", "page"),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioGlassdoorComponent(ScavioBaseComponent):
    display_name = "Scavio Glassdoor"
    description = (
        "Glassdoor through Scavio: company search, company details, reviews, salaries (`/api/v1/glassdoor/*`, 1 "
        "credit each). START HERE. Search Glassdoor by company NAME and resolve it to the employer_id every other "
        "endpoint needs."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioGlassdoor"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Company Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Company Search"),
        text_input(
            "query",
            "Query",
            "Company NAME to resolve into an employer_id.",
            tool_mode=True,
        ),
        text_input(
            "employer_id",
            "Employer ID",
            "Glassdoor employer id as a STRING -- a JSON number is rejected. Accepts 1699, E1699 or IE1699.",
        ),
        text_input(
            "company",
            "Company",
            (
                "Company name. COSMETIC only: the profile resolves on employer_id alone, it is ignored entirely "
                "when url is set, and it does not satisfy the required-identifier rule."
            ),
        ),
        text_input(
            "url",
            "URL",
            "Any glassdoor.com employer URL (/Overview/, /Reviews/, /Salary/). Non-glassdoor.com hosts are rejected.",
        ),
        choice_input(
            "category",
            "Category",
            (
                "Review category filter. Closed set: Glassdoor IGNORES an unknown value and returns the unfiltered "
                "set under a 200. Options: career_development, compensation, culture, diversity_and_inclusion, "
                "management, work_life_balance."
            ),
            [
                "",
                "career_development",
                "compensation",
                "culture",
                "diversity_and_inclusion",
                "management",
                "work_life_balance",
            ],
            advanced=True,
        ),
        choice_input(
            "employment_status",
            "Employment Status",
            (
                "Reviewer employment status filter. Closed set for the same reason as category. Options: full_time, "
                "part_time, contract, intern."
            ),
            ["", "full_time", "part_time", "contract", "intern"],
            advanced=True,
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 10 job titles per page; page_count on the response says how many exist.",
        ),
        max_results_input(),
    ]

    # The endpoint dropdown's default decides what is visible before the user
    # touches anything; update_build_config takes over from there.
    default_visibility(inputs, ENDPOINTS, DEFAULT_ENDPOINT)

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Raw JSON", name="raw", method="fetch_raw"),
    ]
