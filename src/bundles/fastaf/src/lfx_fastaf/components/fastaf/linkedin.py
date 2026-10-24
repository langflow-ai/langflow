from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, boolean_option, require_text
from lfx_fastaf._inputs import (
    api_key_input,
    optional_bool,
    text_input,
)


class FastAFLinkedInComponent(FastAFBaseComponent):
    display_name = "FastAF Get LinkedIn Profile"
    description = "Retrieve public person-profile data for 60 credits; no private profiles or company pages."
    name = "FastAFLinkedIn"
    endpoint = "linkedin"
    result_keys = ()
    inputs = [
        api_key_input(),
        text_input(
            "profile_id",
            "Profile ID",
            "Public person-profile slug after /in/, not the full URL.",
            required=True,
            tool_mode=True,
        ),
        optional_bool("premium", "Premium Retrieval", "Both public-profile modes cost 60 credits."),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_linkedin")]

    def request_body(self) -> dict:
        return {
            "id": require_text(self.profile_id, "Profile ID"),
            "type": "profile",
            "premium": boolean_option(self.premium),
        }

    def fastaf_linkedin(self) -> DataFrame:
        return DataFrame(self.fetch_content())
