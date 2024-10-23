import pytest
from langflow.components.data import URLComponent
from langflow.schema import Data


def test_url_component_tool_integration():
    url_component = URLComponent()
    url_component.urls = ["https://example.com"]
    url_component.format = "Text"

    # Simulate adding the component to a toolkit
    toolkit = url_component.to_toolkit()

    assert len(toolkit) == 2  # Expecting one tool in the toolkit
    tool = toolkit[0]

    assert tool.name == "URL-fetch_content"  # Check the tool name
    assert tool.description == (
        "fetch_content(format: FieldTypes.TEXT, urls: Message) - " "Fetch content from one or more URLs."
    )
    output_data = tool.func()  # Assuming the function is callable directly

    assert len(output_data) == 1  # Expecting one Data object
    assert isinstance(output_data[0], Data)  # Ensure the output is of type Data
    assert output_data[0].text is not None  # Check that text is not None
    assert "example" in output_data[0].text  # Check that the fetched content contains expected text


def test_url_component_tool_invalid_url():
    url_component = URLComponent()
    url_component.urls = None

    # Simulate adding the component to a toolkit

    toolkit = url_component.to_toolkit()
    tool = toolkit[0]

    with pytest.raises(ValueError, match="Invalid URL: The URL is empty."):
        tool.func()  # Invoke the tool's fetch_content method # Check for the correct error message


def test_url_component_tool_with_params():
    url_component = URLComponent()

    # Simulate adding the component to a toolkit
    toolkit = url_component.to_toolkit()
    tool = toolkit[0]

    params = {"format": "TEXT", "urls": ["https://example.com"]}  # Prepare parameters as a dictionary
    output_data = tool.func(**params)  # Invoke the tool's fetch_content method with parameters
    assert len(output_data) == 1  # Expecting one Data object
    assert isinstance(output_data[0], Data)  # Ensure the output is of type Data
    assert output_data[0].text is not None  # Check that text is not None
    assert "example" in output_data[0].text  # Check that the fetched content contains expected text


def test_url_component_with_list_of_urls():
    url_component = URLComponent()
    url_component.urls = ["https://example.com", "https://example.com/2"]
    url_component.format = "TEXT"
    content = url_component.fetch_content()
    assert len(content) == 2
    assert isinstance(content[0], Data)
    assert isinstance(content[1], Data)


def test_url_fetch_content_with_list_of_urls():
    url_component = URLComponent()
    url_component.format = "TEXT"
    urls = {"urls": ["https://example.com", "https://example.com/2"]}
    url_component.set(**urls)
    content = url_component.fetch_content()
    assert url_component.urls == ["https://example.com", "https://example.com/2"]
    assert len(content) == 2
    assert isinstance(content[0], Data)
    assert isinstance(content[1], Data)


def test_url_component_set_urls():
    url_component = URLComponent()
    url_component.set(urls=["https://example.com", "https://example.com/2"])
    assert url_component.urls == ["https://example.com", "https://example.com/2"]
