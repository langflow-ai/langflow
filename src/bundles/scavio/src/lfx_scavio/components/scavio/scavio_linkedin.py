from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output

from lfx_scavio.components.scavio._base import (
    DOCUMENTATION,
    Endpoint,
    ScavioAPIMixin,
    api_key_input,
    choice_input,
    cursor_input,
    default_visibility,
    endpoint_input,
    managed_fields,
    max_results_input,
    number_input,
    text_input,
)

# Only the nine live endpoints are offered. person/contact, company/people,
# company/jobs, search/people and search/posts were retired upstream: they always
# answer 410 and are never billed, so there is nothing to expose.
ENDPOINTS = {
    "Person Profile": Endpoint(
        path="/api/v1/linkedin/person",
        credits=1,
        fields=("username", "url"),
    ),
    "Person About": Endpoint(
        path="/api/v1/linkedin/person/about",
        credits=1,
        fields=("username", "url"),
    ),
    "Person Posts": Endpoint(
        path="/api/v1/linkedin/person/posts",
        credits=10,
        fields=("username", "url", "type", "cursor"),
        result_keys=("data",),
    ),
    "Company Profile": Endpoint(
        path="/api/v1/linkedin/company",
        credits=1,
        fields=("company", "url"),
    ),
    "Company Posts": Endpoint(
        path="/api/v1/linkedin/company/posts",
        credits=10,
        fields=("company", "url", "cursor"),
        result_keys=("data",),
    ),
    "Job Search": Endpoint(
        path="/api/v1/linkedin/search/jobs",
        credits=10,
        fields=("search", "location", "cursor"),
        required=("search",),
        result_keys=("data",),
    ),
    "Job Details": Endpoint(
        path="/api/v1/linkedin/job",
        credits=30,
        fields=("job_id", "url"),
    ),
    "Post Details": Endpoint(
        path="/api/v1/linkedin/post",
        credits=1,
        fields=("post_id", "url"),
    ),
    "Post Comments": Endpoint(
        path="/api/v1/linkedin/post/comments",
        credits=10,
        fields=("post_id", "url", "page"),
        result_keys=("data",),
    ),
}
MANAGED = managed_fields(ENDPOINTS)


class ScavioLinkedInComponent(ScavioAPIMixin, Component):
    display_name = "Scavio LinkedIn"
    description = (
        "The nine live Scavio LinkedIn endpoints: person profile, about and posts, company profile and "
        "posts, job search and job detail, post detail and post comments. Credits are tiered - 1 for the "
        "profile-shaped calls, 10 for the feeds and job search, 30 for job detail, the most expensive "
        "endpoint in the API."
    )
    documentation = DOCUMENTATION
    icon = "Scavio"
    name = "ScavioLinkedIn"

    ENDPOINTS = ENDPOINTS
    MANAGED_FIELDS = MANAGED
    DEFAULT_ENDPOINT = "Person Profile"

    inputs = [
        api_key_input(),
        endpoint_input(ENDPOINTS, "Person Profile"),
        text_input("username", "Person Username", "Public profile identifier, e.g. williamhgates.", tool_mode=True),
        text_input("company", "Company", "Company universal name or slug, e.g. microsoft.", tool_mode=True),
        text_input(
            "search", "Job Search", "Job search terms. LinkedIn's wire field is search, not query.", tool_mode=True
        ),
        text_input("location", "Location", "Geographic filter for Job Search. Leave empty to search everywhere."),
        text_input("job_id", "Job ID", "Numeric LinkedIn job id, e.g. 4415427228.", tool_mode=True),
        text_input(
            "post_id",
            "Post ID",
            "Post id or activity urn, e.g. 7488618410256523265 or urn:li:activity:7488618410256523265.",
            tool_mode=True,
        ),
        text_input(
            "url",
            "URL",
            "A full LinkedIn URL, usable in place of the identifier on every endpoint. A member urn is "
            "never a valid input.",
        ),
        cursor_input("Opaque cursor echoed from a previous response's next_cursor."),
        number_input(
            "page",
            "Comments Page",
            "1-based page for Post Comments - the one LinkedIn endpoint that pages by number, not cursor.",
            value=1,
        ),
        choice_input(
            "type",
            "Person Feed Type",
            "Which person feed to read: their own posts, posts they commented on, or posts they reacted to.",
            ["", "posts", "comments", "reactions"],
            advanced=True,
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
