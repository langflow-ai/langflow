from typing import Any

from lfx.custom import Component
from lfx.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput, StrInput
from lfx.io import Output
from lfx.schema import Data
from twelvelabs import TwelveLabs


class TwelveLabsError(Exception):
    """Base exception for TwelveLabs errors."""


class SearchError(TwelveLabsError):
    """Error raised when a search request fails."""


class TwelveLabsVideoSearch(Component):
    """Search inside an indexed video library using the TwelveLabs Marengo engine."""

    display_name = "TwelveLabs Video Search"
    description = "Run a semantic search over videos in a TwelveLabs index and return matching clips."
    icon = "TwelveLabs"
    name = "TwelveLabsVideoSearch"
    documentation = "https://github.com/twelvelabs-io/twelvelabs-developer-experience/blob/main/integrations/Langflow/TWELVE_LABS_COMPONENTS_README.md"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="TwelveLabs API Key",
            info="Enter your TwelveLabs API Key.",
            required=True,
        ),
        StrInput(
            name="index_id",
            display_name="Index ID",
            info="ID of the index to search (e.g. from the Pegasus Index Video component).",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Natural-language query to search for inside the indexed videos.",
            required=True,
        ),
        DropdownInput(
            name="search_options",
            display_name="Search Options",
            info="Which modalities to search over.",
            options=["visual", "audio", "visual,audio"],
            value="visual,audio",
            advanced=True,
        ),
        DropdownInput(
            name="group_by",
            display_name="Group By",
            info="Return individual clips or group results by video.",
            options=["clip", "video"],
            value="clip",
            advanced=True,
        ),
        DropdownInput(
            name="threshold",
            display_name="Confidence Threshold",
            info="Minimum confidence level for returned matches.",
            options=["high", "medium", "low", "none"],
            value="medium",
            advanced=True,
        ),
        IntInput(
            name="page_limit",
            display_name="Max Results",
            info="Maximum number of matches to return.",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Search Results",
            name="results",
            method="search",
            output_types=["Data"],
            is_list=True,
        ),
    ]

    @staticmethod
    def _field(item: Any, name: str) -> Any:
        """Read a field from either a pydantic model or a raw dict.

        The pinned SDK's response models can lag the live API, so we also
        accept the raw JSON dict returned by the lower-level transport.
        """
        if isinstance(item, dict):
            return item.get(name)
        return getattr(item, name, None)

    def _to_data(self, item: Any) -> Data:
        """Convert a single search result (model or dict) into a Langflow Data object."""
        start = self._field(item, "start")
        end = self._field(item, "end")
        video_id = self._field(item, "video_id")
        score = self._field(item, "score")
        confidence = self._field(item, "confidence")
        rank = self._field(item, "rank")
        thumbnail_url = self._field(item, "thumbnail_url")

        text = f"Match in video {video_id} from {start}s to {end}s (confidence: {confidence})"
        return Data(
            text=text,
            data={
                "video_id": video_id,
                "start": start,
                "end": end,
                "score": score,
                "confidence": confidence,
                "rank": rank,
                "thumbnail_url": thumbnail_url,
                "index_id": self.index_id,
            },
        )

    def search(self) -> list[Data]:
        """Search the index and return matching clips as Data objects."""
        if not self.api_key:
            error_msg = "TwelveLabs API Key is required"
            raise SearchError(error_msg)
        if not self.index_id:
            error_msg = "Index ID is required"
            raise SearchError(error_msg)
        if not self.query:
            error_msg = "Query is required"
            raise SearchError(error_msg)

        options = [opt.strip() for opt in self.search_options.split(",") if opt.strip()]

        client = TwelveLabs(api_key=self.api_key)
        self.status = f"Searching index {self.index_id} for: {self.query}"
        entries = self._run_query(client, options)

        results: list[Data] = []
        for group in entries:
            # When group_by="video" each entry exposes nested clips; otherwise it is a clip itself.
            clips = self._field(group, "clips")
            if clips:
                results.extend(self._to_data(clip) for clip in clips)
            else:
                results.append(self._to_data(group))

        self.status = f"Found {len(results)} match(es)."
        return results

    def _run_query(self, client: TwelveLabs, options: list[str]) -> list[Any]:
        """Run the search, falling back to the raw response when the SDK can't parse it.

        Returns a list of result entries (pydantic models or raw dicts).
        """
        try:
            result = client.search.query(
                index_id=self.index_id,
                options=options,
                query_text=self.query,
                group_by=self.group_by,
                threshold=self.threshold,
                page_limit=self.page_limit,
            )
            return list(result.data)
        except Exception as typed_error:  # noqa: BLE001 - SDK may raise ValidationError, HTTP errors, etc.
            # The typed call failed (often the pinned SDK's models lagging the live
            # API). Retry against the raw transport so a parse-only mismatch doesn't
            # break search; re-raise the original error if the raw call also fails.
            try:
                raw = client.search._post(  # noqa: SLF001 - intentional raw-transport fallback
                    "search",
                    data={
                        "index_id": self.index_id,
                        "search_options": options,
                        "query_text": self.query,
                        "group_by": self.group_by,
                        "threshold": self.threshold,
                        "page_limit": self.page_limit,
                    },
                    files={"_": ""},
                )
            except Exception:  # noqa: BLE001 - surface the original, more meaningful error
                error_msg = f"TwelveLabs search failed: {typed_error!s}"
                self.status = error_msg
                raise SearchError(error_msg) from typed_error

            data = raw.get("data", []) if isinstance(raw, dict) else []
            return list(data)
