from pathlib import Path

from langflow.components import helpers
from langflow.custom.utils import build_custom_component_template
from langflow.schema import Data
from langflow.schema.message import Message


# def test_update_data_component():
#     # Arrange
#     update_data_component = helpers.UpdateDataComponent()

#     # Act
#     new_data = {"new_key": "new_value"}
#     existing_data = Data(data={"existing_key": "existing_value"})
#     result = update_data_component.build(existing_data, new_data)
#     assert result.data == {"existing_key": "existing_value", "new_key": "new_value"}
#     assert result.existing_key == "existing_value"
#     assert result.new_key == "new_value"


# def test_document_to_data_component():
#     # Arrange
#     document_to_data_component = helpers.DocumentsToDataComponent()

#     # Act
#     # Replace with your actual test data
#     document = Document(page_content="key: value", metadata={"url": "https://example.com"})
#     result = document_to_data_component.build(document)

#     # Assert
#     # Replace with your actual expected result
#     assert result == [Data(data={"text": "key: value", "url": "https://example.com"})]


def test_uuid_generator_component():
    # Arrange
    uuid_generator_component = helpers.IDGeneratorComponent()
    uuid_generator_component._code = Path(helpers.IDGenerator.__file__).read_text()

    frontend_node, _ = build_custom_component_template(uuid_generator_component)

    # Act
    build_config = frontend_node.get("template")
    field_name = "unique_id"
    build_config = uuid_generator_component.update_build_config(build_config, None, field_name)
    result = uuid_generator_component.generate_id()

    # Assert
    # UUID should be a string of length 36
    assert isinstance(result, Message)
    assert len(result.text) == 36


def test_data_as_text_component():
    # Arrange
    data_as_text_component = helpers.ParseDataComponent()

    # Act
    # Replace with your actual test data
    data = [Data(data={"key": "value", "bacon": "eggs"})]
    template = "Data:{data} -- Bacon:{bacon}"
    data_as_text_component.set_attributes({"data": data, "template": template})
    result = data_as_text_component.parse_data()

    # Assert
    # Replace with your actual expected result
    assert result.text == "Data:{'key': 'value', 'bacon': 'eggs'} -- Bacon:eggs"


# def test_text_to_data_component():
#     # Arrange
#     text_to_data_component = helpers.CreateDataComponent()

#     # Act
#     # Replace with your actual test data
#     dict_with_text = {"field_1": {"key": "value"}}
#     result = text_to_data_component.build(number_of_fields=1, **dict_with_text)

#     # Assert
#     # Replace with your actual expected result
#     assert result == Data(data={"key": "value"})
