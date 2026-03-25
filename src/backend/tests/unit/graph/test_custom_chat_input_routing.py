from unittest.mock import MagicMock

from lfx.graph.graph.base import Graph


def test_set_inputs_routes_chat_input_to_custom_input_vertex():
    graph = Graph()
    graph._is_input_vertices = ["CustomComponent-abcde"]

    vertex = MagicMock()
    vertex.id = "CustomComponent-abcde"
    vertex.display_name = "Custom Chat Input"
    vertex._is_chat_input.return_value = True

    graph.get_vertex = MagicMock(return_value=vertex)

    graph._set_inputs(input_components=[], inputs={"input_value": "hello from api"}, input_type="chat")

    vertex.update_raw_params.assert_called_once_with({"input_value": "hello from api"}, overwrite=True)


def test_set_inputs_skips_non_chat_vertex_for_chat_input_type():
    graph = Graph()
    graph._is_input_vertices = ["CustomComponent-abcde"]

    vertex = MagicMock()
    vertex.id = "CustomComponent-abcde"
    vertex.display_name = "Custom Input"
    vertex._is_chat_input.return_value = False

    graph.get_vertex = MagicMock(return_value=vertex)

    graph._set_inputs(input_components=[], inputs={"input_value": "hello from api"}, input_type="chat")

    vertex.update_raw_params.assert_not_called()
