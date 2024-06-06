from langchain_core.documents import Document

from langflow.components import helpers
from langflow.custom.utils import build_custom_component_template
from langflow.schema import Record


def test_update_record_component():
    # Arrange
    update_record_component = helpers.UpdateRecordComponent()

    # Act
    new_data = {"new_key": "new_value"}
    existing_record = Record(data={"existing_key": "existing_value"})
    result = update_record_component.build(existing_record, new_data)
    assert result.data == {"existing_key": "existing_value", "new_key": "new_value"}
    assert result.existing_key == "existing_value"
    assert result.new_key == "new_value"


def test_document_to_record_component():
    # Arrange
    document_to_record_component = helpers.DocumentToRecordComponent()

    # Act
    # Replace with your actual test data
    document = Document(page_content="key: value", metadata={"url": "https://example.com"})
    result = document_to_record_component.build(document)

    # Assert
    # Replace with your actual expected result
    assert result == [Record(data={"text": "key: value", "url": "https://example.com"})]


def test_uuid_generator_component():
    # Arrange
    uuid_generator_component = helpers.UUIDGeneratorComponent()
    uuid_generator_component.code = open(helpers.IDGenerator.__file__, "r").read()

    frontend_node, _ = build_custom_component_template(uuid_generator_component)

    # Act
    build_config = frontend_node.get("template")
    field_name = "unique_id"
    build_config = uuid_generator_component.update_build_config(build_config, None, field_name)
    unique_id = build_config["unique_id"]["value"]
    result = uuid_generator_component.build(unique_id)

    # Assert
    # UUID should be a string of length 36
    assert isinstance(result, str)
    assert len(result) == 36


def test_records_as_text_component():
    # Arrange
    records_as_text_component = helpers.RecordsToTextComponent()

    # Act
    # Replace with your actual test data
    records = [Record(data={"key": "value", "bacon": "eggs"})]
    template = "Data:{data} -- Bacon:{bacon}"
    result = records_as_text_component.build(records, template=template)

    # Assert
    # Replace with your actual expected result
    assert result == "Data:{'key': 'value', 'bacon': 'eggs'} -- Bacon:eggs"


def test_text_to_record_component():
    # Arrange
    text_to_record_component = helpers.CreateRecordComponent()

    # Act
    # Replace with your actual test data
    dict_with_text = {"field_1": {"key": "value"}}
    result = text_to_record_component.build(number_of_fields=1, **dict_with_text)

    # Assert
    # Replace with your actual expected result
    assert result == Record(data={"key": "value"})
