from lfx_scavio._component import Output, ScavioBaseComponent
from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    api_key_input,
    choice_input,
    decimal_input,
    default_visibility,
    endpoint_input,
    flag_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

ENDPOINTS = {
    "Search": Endpoint(
        path="/api/v1/indeed/search",
        credits=2,
        fields=("query", "location", "page", "radius", "max_age_days", "job_type", "min_salary", "remote"),
        result_keys=("jobs",),
    ),
    "Job Details": Endpoint(
        path="/api/v1/indeed/job",
        credits=2,
        fields=("job_id",),
        required=("job_id",),
    ),
    "Company Details": Endpoint(
        path="/api/v1/indeed/company",
        credits=2,
        fields=("company",),
        required=("company",),
    ),
    "Company Reviews": Endpoint(
        path="/api/v1/indeed/company/reviews",
        credits=2,
        fields=("company", "page"),
        required=("company",),
        result_keys=("reviews",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioIndeedComponent(ScavioBaseComponent):
    display_name = "Scavio Indeed"
    description = (
        "Indeed through Scavio: search, job details, company details, company reviews (`/api/v1/indeed/*`, 2 credits "
        "each). Indeed job postings: title, employer, rating, location, salary range, job type, benefits, posting "
        "age, apply route. Pagination: page -- 10 postings per page."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioIndeed"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Search"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Search"),
        text_input(
            "query",
            "Query",
            "Job title, keyword or company. Optional if location is set.",
            tool_mode=True,
        ),
        text_input(
            "location",
            "Location",
            (
                "City and state, postal code, state, country or 'Remote'. Usable with no query at all -- that "
                "returns every posting in a metro."
            ),
        ),
        number_input(
            "page",
            "Page",
            "Result page, 1-based. 10 postings per page.",
        ),
        number_input(
            "radius",
            "Radius",
            (
                "Search radius in miles. Closed set: Indeed IGNORES any other value and returns the unfiltered set, "
                "so asking for 7 would silently buy 50. Options: 0, 5, 10, 15, 25, 35, 50, 100. Default: 50."
            ),
        ),
        number_input(
            "max_age_days",
            "Max Age Days",
            (
                "Only postings published within this many days. Closed set for the same reason as radius. Options: "
                "1, 3, 7, 14."
            ),
        ),
        choice_input(
            "job_type",
            "Job Type",
            "Employment type filter. Options: full_time, part_time, contract, temporary, internship.",
            ["", "full_time", "part_time", "contract", "temporary", "internship"],
            advanced=True,
        ),
        decimal_input(
            "min_salary",
            "Min Salary",
            (
                "Minimum salary. This filters on INDEED'S OWN ESTIMATE for the role, not a posted figure, so "
                "postings that publish no salary still match."
            ),
        ),
        flag_input(
            "remote",
            "Remote",
            "Only return remote roles.",
        ),
        text_input(
            "job_id",
            "Job ID",
            "16-hex Indeed job key, or any indeed.com URL carrying jk= (/viewjob, /rc/clk, /pagead/clk).",
        ),
        text_input(
            "company",
            "Company",
            (
                "indeed.com/cmp/<slug> slug or a full profile URL. Slugs are untidy, e.g. "
                "'Tata-Consultancy-Services-(tcs)'."
            ),
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
