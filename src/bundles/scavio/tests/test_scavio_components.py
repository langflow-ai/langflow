"""Unit tests for the Scavio extension bundle (``lfx-scavio``).

Everything runs offline: ``httpx.Client`` is patched, so no key and no network
access are needed. The suite guards three things the API has already broken once:

1. Endpoint coverage - the bundle exposes every live billable Scavio endpoint,
   at the right credit cost, and none of the retired ones.
2. Wire names - the handful of endpoints whose field name is not what a caller
   would guess (``search`` on YouTube/X/LinkedIn job search, the ASIN in
   ``asin`` on Amazon, ``product_id`` on Walmart, ``keyword`` on Instagram, a
   string ``cursor`` on TikTok).
3. Envelopes - Google answers flat, every other product wraps in ``data``.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx.schema.dataframe import DataFrame

from lfx_scavio import (
    ScavioAmazonComponent,
    ScavioGoogleAIModeComponent,
    ScavioGoogleFlightsComponent,
    ScavioGoogleHotelsComponent,
    ScavioGoogleMapsComponent,
    ScavioGoogleNewsComponent,
    ScavioGoogleShoppingComponent,
    ScavioGoogleTrendsComponent,
    ScavioInstagramComponent,
    ScavioLinkedInComponent,
    ScavioRedditComponent,
    ScavioSearchComponent,
    ScavioTikTokComponent,
    ScavioTikTokShopComponent,
    ScavioWalmartComponent,
    ScavioXComponent,
    ScavioYouTubeComponent,
)

ALL_COMPONENTS = (
    ScavioSearchComponent,
    ScavioGoogleAIModeComponent,
    ScavioGoogleMapsComponent,
    ScavioGoogleShoppingComponent,
    ScavioGoogleNewsComponent,
    ScavioGoogleTrendsComponent,
    ScavioGoogleFlightsComponent,
    ScavioGoogleHotelsComponent,
    ScavioYouTubeComponent,
    ScavioAmazonComponent,
    ScavioWalmartComponent,
    ScavioRedditComponent,
    ScavioTikTokComponent,
    ScavioTikTokShopComponent,
    ScavioInstagramComponent,
    ScavioXComponent,
    ScavioLinkedInComponent,
)

# The live billable surface, taken from the Scavio route definitions.
# /api/v1/google was retired on 2026-08-04 and now answers 410; the five retired
# LinkedIn paths answer 410 and are never billed; /api/v1/youtube/metadata is a
# deprecated alias of /api/v1/youtube/video. None of them belong here.
LIVE_ENDPOINTS = {
    # Google v2 - 14 endpoints, 1 credit each
    "/api/v2/google": 1,
    "/api/v2/google/ai-mode": 1,
    "/api/v2/google/maps/search": 1,
    "/api/v2/google/maps/place": 1,
    "/api/v2/google/maps/reviews": 1,
    "/api/v2/google/shopping": 1,
    "/api/v2/google/shopping/product": 1,
    "/api/v2/google/shopping/product/stores": 1,
    "/api/v2/google/flights": 1,
    "/api/v2/google/hotels": 1,
    "/api/v2/google/hotels/detail": 1,
    "/api/v2/google/news": 1,
    "/api/v2/google/trends": 1,
    "/api/v2/google/trending": 1,
    # YouTube - 15 exposed endpoints
    "/api/v1/youtube/search": 2,
    "/api/v1/youtube/shorts": 2,
    "/api/v1/youtube/suggestions": 1,
    "/api/v1/youtube/video": 1,
    "/api/v1/youtube/comments": 1,
    "/api/v1/youtube/comments/replies": 1,
    "/api/v1/youtube/transcript": 8,
    "/api/v1/youtube/related": 1,
    "/api/v1/youtube/streams": 3,
    "/api/v1/youtube/channel/search": 1,
    "/api/v1/youtube/channel": 1,
    "/api/v1/youtube/channel/videos": 1,
    "/api/v1/youtube/channel/shorts": 1,
    "/api/v1/youtube/channel/community": 1,
    "/api/v1/youtube/channel/resolve": 1,
    # Amazon - 3 billable endpoints
    "/api/v1/amazon/search": 1,
    "/api/v1/amazon/product": 1,
    "/api/v1/amazon/offers": 1,
    # Walmart - 2
    "/api/v1/walmart/search": 1,
    "/api/v1/walmart/product": 1,
    # Reddit - 12, 1 credit each (it was 2 before Reddit moved providers)
    "/api/v1/reddit/search": 1,
    "/api/v1/reddit/search/suggestions": 1,
    "/api/v1/reddit/post": 1,
    "/api/v1/reddit/post/comments": 1,
    "/api/v1/reddit/post/comments/replies": 1,
    "/api/v1/reddit/subreddit": 1,
    "/api/v1/reddit/subreddit/posts": 1,
    "/api/v1/reddit/user": 1,
    "/api/v1/reddit/user/posts": 1,
    "/api/v1/reddit/user/comments": 1,
    "/api/v1/reddit/popular": 1,
    "/api/v1/reddit/trending": 1,
    # TikTok - 11
    "/api/v1/tiktok/profile": 1,
    "/api/v1/tiktok/user/posts": 1,
    "/api/v1/tiktok/user/followers": 1,
    "/api/v1/tiktok/user/followings": 1,
    "/api/v1/tiktok/video": 1,
    "/api/v1/tiktok/video/comments": 1,
    "/api/v1/tiktok/video/comments/replies": 1,
    "/api/v1/tiktok/search/videos": 1,
    "/api/v1/tiktok/search/users": 1,
    "/api/v1/tiktok/hashtag": 1,
    "/api/v1/tiktok/hashtag/videos": 1,
    # TikTok Shop - 8
    "/api/v1/tiktok-shop/search": 1,
    "/api/v1/tiktok-shop/search/suggestions": 1,
    "/api/v1/tiktok-shop/product": 1,
    "/api/v1/tiktok-shop/product/reviews": 1,
    "/api/v1/tiktok-shop/categories": 1,
    "/api/v1/tiktok-shop/category/products": 1,
    "/api/v1/tiktok-shop/shop/products": 1,
    "/api/v1/tiktok-shop/resolve": 1,
    # Instagram - 12, per-endpoint credits, never a flat rate
    "/api/v1/instagram/profile": 10,
    "/api/v1/instagram/user/posts": 2,
    "/api/v1/instagram/user/reels": 10,
    "/api/v1/instagram/user/tagged": 10,
    "/api/v1/instagram/user/stories": 10,
    "/api/v1/instagram/post": 8,
    "/api/v1/instagram/post/comments": 10,
    "/api/v1/instagram/post/comments/replies": 8,
    "/api/v1/instagram/search/users": 10,
    "/api/v1/instagram/search/hashtags": 10,
    "/api/v1/instagram/user/followers": 10,
    "/api/v1/instagram/user/followings": 10,
    # X - 11
    "/api/v1/x/search": 1,
    "/api/v1/x/tweet": 1,
    "/api/v1/x/tweet/comments": 1,
    "/api/v1/x/tweet/retweeters": 1,
    "/api/v1/x/user": 1,
    "/api/v1/x/user/tweets": 1,
    "/api/v1/x/user/replies": 1,
    "/api/v1/x/user/media": 1,
    "/api/v1/x/user/followers": 1,
    "/api/v1/x/user/followings": 1,
    "/api/v1/x/trending": 1,
    # LinkedIn - the 9 live endpoints, three credit tiers
    "/api/v1/linkedin/person": 1,
    "/api/v1/linkedin/person/about": 1,
    "/api/v1/linkedin/person/posts": 10,
    "/api/v1/linkedin/company": 1,
    "/api/v1/linkedin/company/posts": 10,
    "/api/v1/linkedin/search/jobs": 10,
    "/api/v1/linkedin/job": 30,
    "/api/v1/linkedin/post": 1,
    "/api/v1/linkedin/post/comments": 10,
}

RETIRED_PATHS = {
    "/api/v1/google",
    "/api/v1/youtube/metadata",
    "/api/v1/linkedin/person/contact",
    "/api/v1/linkedin/company/people",
    "/api/v1/linkedin/company/jobs",
    "/api/v1/linkedin/search/people",
    "/api/v1/linkedin/search/posts",
}

GOOGLE_V1_ONLY_PARAMS = {"light_request", "country_code", "language", "search_type", "page"}


def mock_client(json_data=None, status_code=200, text=""):
    """Return a MagicMock standing in for ``httpx.Client`` used as a context manager."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {} if json_data is None else json_data
    response.text = text
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=response)
    else:
        response.raise_for_status.return_value = None
    client = MagicMock()
    client.__enter__.return_value.post.return_value = response
    return client


def call_args(client):
    """Return (url, payload) from the single POST the component made."""
    post = client.__enter__.return_value.post
    post.assert_called_once()
    return post.call_args.args[0], post.call_args.kwargs["json"]


def run(component, json_data=None, status_code=200, text=""):
    """Run ``fetch_content`` against a mocked transport and return (results, url, payload)."""
    client = mock_client(json_data, status_code, text)
    with patch("httpx.Client", return_value=client):
        results = component.fetch_content()
    if status_code >= 400:
        return results, None, None
    url, payload = call_args(client)
    return results, url, payload


def endpoint_map():
    """Return {path: credits} for every endpoint the bundle offers, asserting no path repeats."""
    seen: dict[str, int] = {}
    for component in ALL_COMPONENTS:
        for endpoint in component.ENDPOINTS.values():
            assert endpoint.path not in seen, f"{endpoint.path} is offered by two components"
            seen[endpoint.path] = endpoint.credits
    return seen


class TestEndpointCoverage:
    def test_every_live_endpoint_is_exposed(self):
        assert set(endpoint_map()) == set(LIVE_ENDPOINTS)

    def test_endpoint_count_is_the_full_live_surface(self):
        assert len(endpoint_map()) == 97

    def test_credit_costs_match_the_api(self):
        assert endpoint_map() == LIVE_ENDPOINTS

    def test_no_retired_endpoint_is_exposed(self):
        assert set(endpoint_map()).isdisjoint(RETIRED_PATHS)

    def test_every_platform_has_a_component(self):
        paths = set(endpoint_map())
        for prefix in (
            "/api/v2/google",
            "/api/v1/youtube/",
            "/api/v1/amazon/",
            "/api/v1/walmart/",
            "/api/v1/reddit/",
            "/api/v1/tiktok/",
            "/api/v1/tiktok-shop/",
            "/api/v1/instagram/",
            "/api/v1/x/",
            "/api/v1/linkedin/",
        ):
            assert any(path.startswith(prefix) for path in paths), prefix

    def test_required_fields_are_declared_fields(self):
        for component in ALL_COMPONENTS:
            declared = {field.name for field in component.inputs}
            for label, endpoint in component.ENDPOINTS.items():
                missing = set(endpoint.fields) - declared
                assert not missing, f"{component.name}/{label} references undeclared inputs {missing}"
                assert set(endpoint.required) <= set(endpoint.fields), f"{component.name}/{label}"

    def test_default_endpoint_exists(self):
        for component in ALL_COMPONENTS:
            assert component.DEFAULT_ENDPOINT in component.ENDPOINTS, component.name


class TestGoogleSearch:
    def test_targets_v2_and_sends_v2_params_only(self):
        component = ScavioSearchComponent(
            api_key="sk_live_test",  # pragma: allowlist secret
            query="serpapi alternative",
            gl="us",
            hl="en",
            google_domain="google.com",
            device="desktop",
            start=10,
        )
        _results, url, payload = run(component, {"organic_results": []})

        assert url == "https://api.scavio.dev/api/v2/google"
        assert payload["query"] == "serpapi alternative"
        assert payload["gl"] == "us"
        assert payload["hl"] == "en"
        assert payload["google_domain"] == "google.com"
        assert payload["start"] == 10
        # Google v1 is gone; none of its params may leak onto the v2 call.
        assert GOOGLE_V1_ONLY_PARAMS.isdisjoint(payload)

    def test_parses_flat_organic_results(self):
        body = {
            "search_parameters": {"q": "openai"},
            "organic_results": [
                {
                    "title": f"Result {i}",
                    "link": f"https://example.com/{i}",
                    "snippet": f"Description {i}",
                    "position": i,
                }
                for i in range(1, 6)
            ],
            "credits_used": 1,
        }
        component = ScavioSearchComponent(api_key="k", query="openai")  # pragma: allowlist secret
        results, _url, _payload = run(component, body)

        assert len(results) == 5
        assert results[0].data["title"] == "Result 1"
        assert results[0].data["url"] == "https://example.com/1"
        assert results[0].data["content"] == "Description 1"
        assert results[0].text == "Description 1"

    def test_respects_max_results(self):
        body = {"organic_results": [{"title": str(i), "link": "u", "snippet": "s"} for i in range(10)]}
        component = ScavioSearchComponent(api_key="k", query="openai", max_results=2)  # pragma: allowlist secret
        results, _url, _payload = run(component, body)
        assert len(results) == 2

    def test_dataframe_output(self):
        body = {"organic_results": [{"title": "a", "link": "u", "snippet": "s"}]}
        component = ScavioSearchComponent(api_key="k", query="openai")  # pragma: allowlist secret
        client = mock_client(body)
        with patch("httpx.Client", return_value=client):
            assert isinstance(component.fetch_content_dataframe(), DataFrame)

    def test_resolve_ai_overview_false_is_transmitted(self):
        component = ScavioSearchComponent(
            api_key="k",  # pragma: allowlist secret
            query="openai",
            resolve_ai_overview=False,
        )
        _results, _url, payload = run(component, {"organic_results": []})
        assert payload["resolve_ai_overview"] is False

    def test_http_error_is_handled(self):
        component = ScavioSearchComponent(api_key="bad", query="openai")  # pragma: allowlist secret
        results, _url, _payload = run(component, status_code=401, text="unauthorized")
        assert len(results) == 1
        assert "error" in results[0].data


class TestGoogleVerticals:
    def test_maps_reviews_sort_is_sent_as_sort_by(self):
        component = ScavioGoogleMapsComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Place Reviews",
            place_id="ChIJtest",
            reviews_sort_by="newest",
        )
        _results, url, payload = run(component, {"reviews": []})
        assert url.endswith("/api/v2/google/maps/reviews")
        assert payload["sort_by"] == "newest"
        assert "reviews_sort_by" not in payload

    def test_shopping_stores_uses_nested_result_key(self):
        body = {"product_results": {"stores": [{"name": "Store A"}, {"name": "Store B"}]}}
        component = ScavioGoogleShoppingComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Product Stores",
            catalog_id="cat1",
            next_page_token="tok",  # noqa: S106 - a pagination cursor, not a credential
        )
        results, _url, _payload = run(component, body)
        assert [row.data["name"] for row in results] == ["Store A", "Store B"]

    def test_trending_uses_geo_and_renamed_cat_and_status(self):
        component = ScavioGoogleTrendsComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Trending Now",
            geo="US",
            trending_cat=3,
            trend_status="active",
        )
        _results, url, payload = run(component, {"trends": []})
        assert url.endswith("/api/v2/google/trending")
        assert payload == {"geo": "US", "cat": 3, "status": "active"}

    def test_ai_mode_reads_references(self):
        body = {"references": [{"title": "Ref", "link": "https://example.com"}]}
        component = ScavioGoogleAIModeComponent(api_key="k", query="what is rag")  # pragma: allowlist secret
        results, url, _payload = run(component, body)
        assert url.endswith("/api/v2/google/ai-mode")
        assert results[0].data["title"] == "Ref"

    def test_news_and_flights_and_hotels_paths(self):
        news = ScavioGoogleNewsComponent(api_key="k", query="ai")  # pragma: allowlist secret
        _r, url, _p = run(news, {"news_results": []})
        assert url.endswith("/api/v2/google/news")

        flights = ScavioGoogleFlightsComponent(
            api_key="k",  # pragma: allowlist secret
            departure_id="JFK",
            arrival_id="LHR",
            outbound_date="2026-09-01",
        )
        _r, url, payload = run(flights, {"best_flights": []})
        assert url.endswith("/api/v2/google/flights")
        assert payload["departure_id"] == "JFK"

        hotels = ScavioGoogleHotelsComponent(
            api_key="k",  # pragma: allowlist secret
            query="Austin hotels",
            check_in_date="2026-09-01",
            check_out_date="2026-09-03",
        )
        _r, url, _p = run(hotels, {"properties": []})
        assert url.endswith("/api/v2/google/hotels")


class TestReddit:
    def test_search_sends_only_query_and_cursor(self):
        component = ScavioRedditComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Search",
            query="serpapi alternative",
            cursor="abc",
            sort="TOP",
            feed_sort="RISING",
        )
        _results, url, payload = run(component, {"results": []})
        assert url.endswith("/api/v1/reddit/search")
        # The backend silently strips anything else, so the component must not send it.
        assert payload == {"query": "serpapi alternative", "cursor": "abc"}

    def test_search_reads_results_not_posts(self):
        body = {"data": {"results": [{"title": "A post"}], "next_cursor": "n", "has_more": True}}
        component = ScavioRedditComponent(api_key="k", endpoint="Search", query="x")  # pragma: allowlist secret
        results, _url, _payload = run(component, body)
        assert len(results) == 1
        assert results[0].data["title"] == "A post"

    def test_post_is_a_flat_object_with_no_comments(self):
        body = {"data": {"post_id": "t3_1", "title": "Flat post", "num_comments": 12}}
        component = ScavioRedditComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Post Details",
            post_id="t3_1",
        )
        results, _url, _payload = run(component, body)
        assert len(results) == 1
        assert results[0].data["post_id"] == "t3_1"
        assert "comments" not in results[0].data

    def test_subreddit_feed_reads_posts(self):
        body = {"data": {"posts": [{"title": "One"}, {"title": "Two"}]}}
        component = ScavioRedditComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Subreddit Posts",
            subreddit="AskReddit",
            feed_sort="RISING",
        )
        results, _url, payload = run(component, body)
        assert len(results) == 2
        assert payload["sort"] == "RISING"

    def test_reply_cursor_is_required(self):
        component = ScavioRedditComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Comment Replies",
            post_id="t3_1",
        )
        client = mock_client({})
        with patch("httpx.Client", return_value=client):
            results = component.fetch_content()

        # The request never leaves the component: a reply_cursor is mandatory here.
        client.__enter__.return_value.post.assert_not_called()
        assert "cursor" in results[0].data["error"]


class TestWireQuirks:
    def test_youtube_search_uses_the_search_field(self):
        component = ScavioYouTubeComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Search",
            search="python tutorial",
        )
        _results, url, payload = run(component, {"data": {"results": []}})
        assert url.endswith("/api/v1/youtube/search")
        assert payload == {"search": "python tutorial"}
        assert "query" not in payload

    def test_youtube_features_is_a_list(self):
        component = ScavioYouTubeComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Search",
            search="drone",
            features=["4k", "hdr"],
        )
        _results, _url, payload = run(component, {"data": {"results": []}})
        assert payload["features"] == ["4k", "hdr"]

    def test_amazon_product_sends_the_asin(self):
        component = ScavioAmazonComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Product Details",
            asin="B09V3KXJPB",
            country="gb",
        )
        _results, url, payload = run(component, {"data": {}})
        assert url.endswith("/api/v1/amazon/product")
        assert payload == {"asin": "B09V3KXJPB", "country": "gb"}

    def test_walmart_product_sends_product_id(self):
        component = ScavioWalmartComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Product Details",
            product_id="123456789",
        )
        _results, url, payload = run(component, {"data": {}})
        assert url.endswith("/api/v1/walmart/product")
        assert payload == {"product_id": "123456789"}

    def test_tiktok_cursor_stays_a_string(self):
        component = ScavioTikTokComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="User Posts",
            sec_user_id="MS4wLjAB",
            cursor="20",
            count=30,
        )
        _results, _url, payload = run(component, {"data": {"aweme_list": []}})
        assert payload["cursor"] == "20"
        assert isinstance(payload["cursor"], str)
        assert payload["count"] == 30

    def test_instagram_search_uses_keyword(self):
        component = ScavioInstagramComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Search Users",
            keyword="fashion",
        )
        _results, url, payload = run(component, {"data": {"users": []}})
        assert url.endswith("/api/v1/instagram/search/users")
        assert payload == {"keyword": "fashion"}
        assert "query" not in payload

    def test_x_search_uses_the_search_field(self):
        component = ScavioXComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Search",
            search="langflow",
            search_type="Latest",
        )
        _results, url, payload = run(component, {"data": {"timeline": []}})
        assert url.endswith("/api/v1/x/search")
        assert payload == {"search": "langflow", "search_type": "Latest"}

    def test_x_followings_reads_the_following_array(self):
        body = {"data": {"following": [{"screen_name": "a"}, {"screen_name": "b"}]}}
        component = ScavioXComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="User Followings",
            screen_name="elonmusk",
        )
        results, _url, _payload = run(component, body)
        assert len(results) == 2

    def test_linkedin_job_search_uses_the_search_field(self):
        component = ScavioLinkedInComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Job Search",
            search="software engineer",
            location="Berlin",
        )
        _results, url, payload = run(component, {"data": {"data": []}})
        assert url.endswith("/api/v1/linkedin/search/jobs")
        assert payload == {"search": "software engineer", "location": "Berlin"}

    def test_tiktok_shop_search_uses_the_search_field(self):
        component = ScavioTikTokShopComponent(
            api_key="k",  # pragma: allowlist secret
            endpoint="Search",
            search="phone case",
        )
        _results, url, payload = run(component, {"data": {"products": []}})
        assert url.endswith("/api/v1/tiktok-shop/search")
        # Search is US-catalog only: there is no region param on this endpoint.
        assert payload == {"search": "phone case"}


class TestEnvelopes:
    def test_google_is_flat(self):
        component = ScavioGoogleNewsComponent(api_key="k", query="ai")  # pragma: allowlist secret
        results, _url, _payload = run(component, {"news_results": [{"title": "Headline"}], "credits_used": 1})
        assert results[0].data["title"] == "Headline"

    def test_other_products_unwrap_data(self):
        component = ScavioXComponent(api_key="k", endpoint="User Profile", screen_name="a")  # pragma: allowlist secret
        body = {"data": {"screen_name": "a", "followers_count": 5}, "response_time": 1, "credits_used": 1}
        results, _url, _payload = run(component, body)
        assert results[0].data == {"screen_name": "a", "followers_count": 5}

    def test_raw_output_keeps_the_credit_counters(self):
        component = ScavioXComponent(api_key="k", endpoint="Trending")  # pragma: allowlist secret
        body = {"data": {"trends": []}, "response_time": 12, "credits_used": 1, "credits_remaining": 49}
        client = mock_client(body)
        with patch("httpx.Client", return_value=client):
            raw = component.fetch_raw()
        assert raw.data["credits_remaining"] == 49


class TestBuildConfig:
    @pytest.mark.parametrize(
        ("component_cls", "label"),
        [
            (ScavioRedditComponent, "Subreddit Posts"),
            (ScavioYouTubeComponent, "Transcript"),
            (ScavioLinkedInComponent, "Job Details"),
            (ScavioInstagramComponent, "Comment Replies"),
        ],
    )
    def test_only_the_selected_endpoints_fields_are_shown(self, component_cls, label):
        component = component_cls()
        build_config = {name: {"show": True, "required": False} for name in component_cls.MANAGED_FIELDS}
        build_config["endpoint"] = {"value": label}

        updated = component.update_build_config(build_config, label, "endpoint")

        endpoint = component_cls.ENDPOINTS[label]
        for name in component_cls.MANAGED_FIELDS:
            assert updated[name]["show"] is (name in endpoint.fields), name
            assert updated[name]["required"] is (name in endpoint.required), name

    def test_unrelated_field_updates_are_ignored(self):
        component = ScavioRedditComponent()
        build_config = {"query": {"show": False, "required": False}, "endpoint": {"value": "Search"}}
        assert component.update_build_config(build_config, "x", "query") == build_config

    def test_fresh_node_shows_the_default_endpoints_fields(self):
        """A node dropped on the canvas must be usable before the dropdown is touched."""
        for component_cls in ALL_COMPONENTS:
            managed = set(component_cls.MANAGED_FIELDS)
            if not managed:
                continue
            endpoint = component_cls.ENDPOINTS[component_cls.DEFAULT_ENDPOINT]
            for field in component_cls.inputs:
                if field.name in managed:
                    assert field.show is (field.name in endpoint.fields), f"{component_cls.name}.{field.name}"
                    assert field.required is (field.name in endpoint.required), f"{component_cls.name}.{field.name}"
