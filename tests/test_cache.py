import json
import hashlib
from pathlib import Path
import dill
import tempfile
from langflow.cache.utils import compute_hash, load_cache, save_cache, PREFIX
from langflow.interface.run import load_langchain_object, process_graph
import pytest


def get_graph(_type="basic"):
    """Get a graph from a json file"""
    if _type == "basic":
        path = pytest.BASIC_EXAMPLE_PATH
    elif _type == "complex":
        path = pytest.COMPLEX_EXAMPLE_PATH
    elif _type == "openapi":
        path = pytest.OPENAPI_EXAMPLE_PATH

    with open(path, "r") as f:
        flow_graph = json.load(f)
    return flow_graph["data"]


@pytest.fixture
def basic_data_graph():
    return get_graph()


@pytest.fixture
def complex_data_graph():
    return get_graph("complex")


@pytest.fixture
def openapi_data_graph():
    return get_graph("openapi")


def langchain_objects_are_equal(obj1, obj2):
    return str(obj1) == str(obj2)


def test_cache_creation(basic_data_graph):
    # Compute hash for the input data_graph
    computed_hash = compute_hash(basic_data_graph)

    # Call process_graph function to build and cache the langchain_object
    _ = load_langchain_object(basic_data_graph)

    # Check if the cache file exists
    cache_file = Path(tempfile.gettempdir()) / f"{PREFIX}_{computed_hash}.dill"
    assert cache_file.exists()


def test_cache_reuse(basic_data_graph):
    # Call process_graph function to build and cache the langchain_object
    result1 = load_langchain_object(basic_data_graph)

    # Call process_graph function again to use the cached langchain_object
    result2 = load_langchain_object(basic_data_graph)

    # Compare the results to ensure the same langchain_object was used
    assert langchain_objects_are_equal(result1, result2)
