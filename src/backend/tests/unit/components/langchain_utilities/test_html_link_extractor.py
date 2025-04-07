import pytest
from langchain_community.graph_vectorstores.links import Link
from langflow.components.langchain_utilities.html_link_extractor import HtmlLinkExtractorComponent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestHtmlLinkExtractorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return HtmlLinkExtractorComponent

    @pytest.fixture
    def default_kwargs(self, html):
        return {"data_input": html, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.1.1", "module": "langchain_utilities", "file_name": "html_link_extractor"},
        ]

    @pytest.fixture
    def html(self):
        source = """
        <!DOCTYPE html>
        <html lang="en">

        <head>
            <meta charset="UTF-8">
            <title>Alexander Graham Bell</title>
        </head>

        <body>
            <h1>Alexander Graham Bell</h1>
            <p>Alexander Graham Bell was a Scottish-born inventor, scientist, and engineer who is credited with inventing and
                patenting the first practical telephone. He also co-founded the American Telephone and Telegraph Company (AT&T)
                in 1885.</p>
            <p>Bell's research on hearing and speech further led him to experiment with hearing devices, which eventually
                culminated in the invention of the telephone. His work profoundly impacted communication technology and laid the
                foundation for modern telecommunications.</p>
            <p>Bell was born on 3 March 1847 in Edinburgh, Scotland. He died on 2 August 1922 in Baddeck, Nova Scotia, Canada.
            </p>
            <p>Related figures: <a href="thomas_edison.html">Thomas Edison</a>, <a href="nikola_tesla.html">Nikola Tesla</a></p>
        </body>

        </html>
        """
        return [
            Data(
                text_key="text",
                data={
                    "text": source,
                    "source": "https://pedrocassalpacheco.github.io/historical_figures_website/Alexander_Graham_Bell.html",
                    "title": "Alexander Graham Bell",
                    "language": "en",
                },
                default_value="",
            )
        ]

    @pytest.fixture
    def all_tags(self):
        return [
            "https://pedrocassalpacheco.github.io/historical_figures_website/Alexander_Graham_Bell.html",
            "https://pedrocassalpacheco.github.io/historical_figures_website/thomas_edison.html",
            "https://pedrocassalpacheco.github.io/historical_figures_website/nikola_tesla.html",
        ]

    def test_link_extraction(self, component_class, default_kwargs, all_tags):
        component = component_class(**default_kwargs)
        assert isinstance(component, HtmlLinkExtractorComponent)
        data = component.transform_data()
        assert data is not None
        assert len(data) == 1
        for datum in data:
            assert isinstance(datum, Data)
            links = datum.data["links"]
            assert links is not None
            for link in links:
                assert isinstance(link, Link)
                assert link.tag in all_tags

    def test_post_code_processing(self, component_class, default_kwargs):
        """Test the post-processing of code in the component class.
        This test verifies that the component class correctly processes the code
        and converts it to a frontend node with the expected structure and values.

        Args:
            component_class (class): The class of the component to be tested.
            default_kwargs (dict): The default keyword arguments to initialize the component.
        Asserts:
            - The node data is not None.
            - The 'value' of 'labels' in the 'template' of node data is "people, places, dates, events".
            - The string "alexander" is present in the 'page_content' of the first item in 'data_input' of 'template'.
        """
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data is not None
        assert "alexander" in node_data["template"]["data_input"]["value"][0]["data"]["text"].lower()
