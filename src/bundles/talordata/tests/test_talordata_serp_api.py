from unittest.mock import Mock, patch

from lfx_talordata import TalordataSERPAPIComponent


def test_component_initialization():
    component = TalordataSERPAPIComponent(
        api_key="test-key",
        input_value="best AI search APIs",
        engine="google",
        max_results=5,
        gl="us",
        hl="en",
        location="",
        device="desktop",
        page=1,
        search_params={},
        _session_id="test-session",
    )

    frontend_node = component.to_frontend_node()
    node_data = frontend_node["data"]["node"]

    assert node_data["template"]["input_value"]["value"] == "best AI search APIs"
    assert node_data["template"]["engine"]["value"] == "google"
    assert node_data["template"]["max_results"]["value"] == 5


def test_build_payload_merges_search_params():
    component = TalordataSERPAPIComponent(
        api_key="test-key",
        input_value="coffee",
        engine="google",
        max_results=3,
        gl="us",
        hl="en",
        location="New York, United States",
        device="mobile",
        page=2,
        search_params={"safe": "active"},
        _session_id="test-session",
    )

    payload = component._build_payload()

    assert payload["engine"] == "google"
    assert payload["q"] == "coffee"
    assert payload["num"] == 3
    assert payload["location"] == "New York, United States"
    assert payload["safe"] == "active"


@patch("lfx_talordata.components.talordata.talordata_serp_api.requests.post")
def test_fetch_content_maps_organic_results(mock_post):
    response = Mock()
    response.json.return_value = {
        "organic_results": [
            {
                "position": 1,
                "title": "Example Result",
                "link": "https://example.com",
                "snippet": "Example snippet",
            }
        ]
    }
    response.raise_for_status.return_value = None
    mock_post.return_value = response

    component = TalordataSERPAPIComponent(
        api_key="test-key",
        input_value="coffee",
        engine="google",
        max_results=5,
        gl="us",
        hl="en",
        location="",
        device="desktop",
        page=1,
        search_params={},
        _session_id="test-session",
    )

    results = component.fetch_content()

    assert len(results) == 1
    assert results[0].data["title"] == "Example Result"
    assert results[0].data["link"] == "https://example.com"
    assert results[0].data["snippet"] == "Example snippet"

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["data"]["q"] == "coffee"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
