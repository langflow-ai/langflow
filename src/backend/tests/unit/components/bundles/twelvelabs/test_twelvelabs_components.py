"""Unit tests for TwelveLabs components cloud validation."""

import os
import types
from unittest.mock import MagicMock, patch

import pytest
from lfx_bundles.twelvelabs.split_video import SplitVideoComponent
from lfx_bundles.twelvelabs.video_file import VideoFileComponent
from lfx_bundles.twelvelabs.video_search import SearchError, TwelveLabsVideoSearch


@pytest.mark.unit
class TestTwelveLabsCloudValidation:
    """Test TwelveLabs components cloud validation."""

    def test_video_file_process_disabled_in_astra_cloud(self):
        """Test that VideoFile process_files raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = VideoFileComponent(api_key="test-key", index_id="test-index")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.process_files([])

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    def test_split_video_process_disabled_in_astra_cloud(self):
        """Test that SplitVideo process raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = SplitVideoComponent(api_key="test-key", index_id="test-index")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.process()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg


@pytest.mark.unit
class TestTwelveLabsVideoSearch:
    """Tests for the TwelveLabs Video Search component."""

    def test_search_requires_inputs(self):
        """Missing required inputs raise SearchError before any network call."""
        for kwargs in (
            {"api_key": "", "index_id": "i", "query": "q"},
            {"api_key": "k", "index_id": "", "query": "q"},
            {"api_key": "k", "index_id": "i", "query": ""},
        ):
            with pytest.raises(SearchError):
                TwelveLabsVideoSearch(**kwargs).search()

    def test_search_wiring_and_data_conversion(self):
        """Search wires the SDK call and converts results to Data (no network)."""
        clip = types.SimpleNamespace(
            score=92.5, start=10.0, end=14.0, video_id="vid123", confidence="high", thumbnail_url="https://x/t.jpg"
        )
        fake_result = types.SimpleNamespace(data=[clip])

        component = TwelveLabsVideoSearch(
            api_key="k",
            index_id="idx1",
            query="a dog playing",
            search_options="visual,audio",
            group_by="clip",
            threshold="medium",
            page_limit=5,
        )

        with patch("lfx_bundles.twelvelabs.video_search.TwelveLabs") as mock_tl:
            client = MagicMock()
            client.search.query.return_value = fake_result
            mock_tl.return_value = client
            results = component.search()

        call_kwargs = client.search.query.call_args.kwargs
        assert call_kwargs["index_id"] == "idx1"
        assert call_kwargs["options"] == ["visual", "audio"]
        assert call_kwargs["query_text"] == "a dog playing"
        assert call_kwargs["group_by"] == "clip"
        assert call_kwargs["threshold"] == "medium"
        assert call_kwargs["page_limit"] == 5

        assert len(results) == 1
        data = results[0].data
        assert data["video_id"] == "vid123"
        assert data["start"] == 10.0
        assert data["end"] == 14.0
        assert data["score"] == 92.5
        assert data["index_id"] == "idx1"
        assert "vid123" in results[0].text

    def test_search_falls_back_to_raw_response_on_parse_error(self):
        """When the typed SDK call fails to parse, the raw transport response is used."""
        component = TwelveLabsVideoSearch(api_key="k", index_id="idx1", query="goal")

        with patch("lfx_bundles.twelvelabs.video_search.TwelveLabs") as mock_tl:
            client = MagicMock()
            client.search.query.side_effect = ValueError("validation error")
            client.search._post.return_value = {"data": [{"video_id": "v9", "start": 0, "end": 8, "rank": 1}]}
            mock_tl.return_value = client
            results = component.search()

        assert len(results) == 1
        assert results[0].data["video_id"] == "v9"
        assert results[0].data["rank"] == 1

    @pytest.mark.skipif(not os.getenv("TWELVELABS_API_KEY"), reason="requires TWELVELABS_API_KEY")
    def test_search_live(self):
        """Live smoke test: search a Marengo-enabled index for matching clips."""
        api_key = os.environ["TWELVELABS_API_KEY"]
        index_id = os.getenv("TWELVELABS_SEARCH_INDEX_ID")
        if not index_id:
            from twelvelabs import TwelveLabs

            client = TwelveLabs(api_key=api_key)
            index_id = next(
                (idx.id for idx in client.index.list() if any("marengo" in m.name for m in (idx.models or []))),
                None,
            )
            if not index_id:
                pytest.skip("no Marengo-enabled index available")

        component = TwelveLabsVideoSearch(
            api_key=api_key, index_id=index_id, query="a person", threshold="low", page_limit=3
        )
        results = component.search()
        assert isinstance(results, list)
        for data in results:
            assert data.data.get("video_id")
