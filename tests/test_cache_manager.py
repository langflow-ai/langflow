from io import StringIO

import pandas as pd
import pytest
from langflow.cache.manager import CacheManager
from PIL import Image


@pytest.fixture
def cache_manager():
    return CacheManager()


def test_cache_manager_attach_detach_notify(cache_manager):
    observer_called = False

    def observer():
        nonlocal observer_called
        observer_called = True

    cache_manager.attach(observer)
    cache_manager.notify()

    assert observer_called

    observer_called = False
    cache_manager.detach(observer)
    cache_manager.notify()

    assert not observer_called


def test_cache_manager_client_context(cache_manager):
    with cache_manager.set_client_id("client1"):
        cache_manager.add("foo", "bar", "string")
        assert cache_manager.get("foo") == {
            "obj": "bar",
            "type": "string",
            "extension": "str",
        }

    with cache_manager.set_client_id("client2"):
        cache_manager.add("baz", "qux", "string")
        assert cache_manager.get("baz") == {
            "obj": "qux",
            "type": "string",
            "extension": "str",
        }

    with pytest.raises(KeyError):
        cache_manager.get("foo")


def test_cache_manager_add_pandas(cache_manager):
    df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

    with cache_manager.set_client_id("client1"):
        cache_manager.add_pandas("test_df", df)
        cached_df = cache_manager.get("test_df")
        assert cached_df["type"] == "pandas"
        assert cached_df["extension"] == "csv"
        read_df = pd.read_csv(StringIO(cached_df["obj"]), index_col=0)
        pd.testing.assert_frame_equal(df, read_df)


def test_cache_manager_add_image(cache_manager):
    img = Image.new("RGB", (50, 50), color="red")

    with cache_manager.set_client_id("client1"):
        cache_manager.add_image("test_image", img)
        cached_img = cache_manager.get("test_image")
        assert cached_img["type"] == "image"
        assert cached_img["extension"] == "png"
        assert isinstance(cached_img["obj"], Image.Image)


def test_cache_manager_get_last(cache_manager):
    with cache_manager.set_client_id("client1"):
        cache_manager.add("foo", "bar", "string")
        cache_manager.add("baz", "qux", "string")
        last_item = cache_manager.get_last()
        assert last_item == {"obj": "qux", "type": "string", "extension": "str"}
