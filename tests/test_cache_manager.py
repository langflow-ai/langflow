from io import StringIO

import pandas as pd
import pytest
from langflow.services.chat.cache import CacheService
from PIL import Image


@pytest.fixture
def cache_service():
    return CacheService()


def test_cache_service_attach_detach_notify(cache_service):
    observer_called = False

    def observer():
        nonlocal observer_called
        observer_called = True

    cache_service.attach(observer)
    cache_service.notify()

    assert observer_called

    observer_called = False
    cache_service.detach(observer)
    cache_service.notify()

    assert not observer_called


def test_cache_service_client_context(cache_service):
    with cache_service.set_client_id("client1"):
        cache_service.add("foo", "bar", "string")
        assert cache_service.get("foo") == {
            "obj": "bar",
            "type": "string",
            "extension": "str",
        }

    with cache_service.set_client_id("client2"):
        cache_service.add("baz", "qux", "string")
        assert cache_service.get("baz") == {
            "obj": "qux",
            "type": "string",
            "extension": "str",
        }

    with pytest.raises(KeyError):
        cache_service.get("foo")


def test_cache_service_add_pandas(cache_service):
    df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

    with cache_service.set_client_id("client1"):
        cache_service.add_pandas("test_df", df)
        cached_df = cache_service.get("test_df")
        assert cached_df["type"] == "pandas"
        assert cached_df["extension"] == "csv"
        read_df = pd.read_csv(StringIO(cached_df["obj"]), index_col=0)
        pd.testing.assert_frame_equal(df, read_df)


def test_cache_service_add_image(cache_service):
    img = Image.new("RGB", (50, 50), color="red")

    with cache_service.set_client_id("client1"):
        cache_service.add_image("test_image", img)
        cached_img = cache_service.get("test_image")
        assert cached_img["type"] == "image"
        assert cached_img["extension"] == "png"
        assert isinstance(cached_img["obj"], Image.Image)


def test_cache_service_get_last(cache_service):
    with cache_service.set_client_id("client1"):
        cache_service.add("foo", "bar", "string")
        cache_service.add("baz", "qux", "string")
        last_item = cache_service.get_last()
        assert last_item == {"obj": "qux", "type": "string", "extension": "str"}
