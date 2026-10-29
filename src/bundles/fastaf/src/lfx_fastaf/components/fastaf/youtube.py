from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, FastAFError, require_text
from lfx_fastaf._inputs import (
    api_key_input,
    choice_input,
    localization_inputs,
    query_input,
    text_input,
)


class FastAFYouTubeComponent(FastAFBaseComponent):
    display_name = "FastAF Get YouTube Data"
    description = "Video transcript: 1 credit; one page of video search: 5 credits. Captions must be available."
    name = "FastAFYouTube"
    endpoint = "youtube"
    result_keys = ("transcripts", "video_results", "all_videos", "allVideos", "videos", "results")
    inputs = [
        api_key_input(),
        choice_input(
            "resource",
            "Resource",
            ["transcript", "search"],
            "transcript",
            "Choose transcript or search.",
            tool_mode=True,
        ),
        text_input(
            "video_id", "Video ID", "Value after v= in the public video URL; required for transcript.", tool_mode=True
        ),
        query_input(required=False),
        text_input(
            "search_token",
            "Search Filter or Page Token",
            "YouTube sp token from a search URL/previous response. Search only.",
            advanced=True,
        ),
        *localization_inputs(),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_youtube")]

    def request_body(self) -> dict:
        if self.resource not in {"transcript", "search"}:
            msg = "Unsupported YouTube resource."
            raise FastAFError(msg)
        body = {"resource": self.resource, **self.localization()}
        if self.resource == "transcript":
            body["v"] = require_text(self.video_id, "Video ID")
        else:
            body.update(search_query=require_text(self.query, "Search Query"), sp=self.search_token)
        return body

    def fastaf_youtube(self) -> DataFrame:
        return DataFrame(self.fetch_content())
