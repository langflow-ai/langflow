from unittest.mock import Mock, patch

import pytest
import requests
from langflow.components.models.wool_ball import WoolBallComponent
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message


@pytest.fixture
def wool_ball_component():
    return WoolBallComponent()


@pytest.fixture
def mock_headers():
    return {"Authorization": "Bearer test_api_key", "Content-Type": "application/json"}


def test_wool_ball_inputs(wool_ball_component):
    inputs = wool_ball_component.inputs
    input_names = [inp.name for inp in inputs]
    required_inputs = ["task_type", "text", "source_language", "target_language", "candidate_labels", "api_key"]

    for name in required_inputs:
        assert name in input_names, f"Missing input: {name}"


def test_wool_ball_task_types(wool_ball_component):
    expected_tasks = [
        "Text to Speech",
        "Text Generation",
        "Translation",
        "Zero-Shot Classification",
        "Summary",
        "Character to Image",
    ]

    assert expected_tasks == wool_ball_component.TASK_TYPES


@patch("requests.get")
def test_text_generation(mock_get, wool_ball_component, mock_headers):
    mock_response = Mock()
    mock_response.json.return_value = {"data": "generated content"}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    wool_ball_component.text = "Input text"
    result = wool_ball_component._handle_text_generation(mock_headers)

    assert isinstance(result, Message)
    assert result.text == "generated content"
    mock_get.assert_called_once()


@patch("requests.post")
def test_translation(mock_post, wool_ball_component, mock_headers):
    mock_response = Mock()
    mock_response.json.return_value = {"data": "translated content"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    wool_ball_component.text = "Hello"
    wool_ball_component.source_language = "eng_Latn"
    wool_ball_component.target_language = "por_Latn"

    result = wool_ball_component._handle_translation(mock_headers)

    assert isinstance(result, Message)
    assert result.text == "translated content"
    mock_post.assert_called_once()


def test_input_types(wool_ball_component):
    inputs = wool_ball_component.inputs
    expected_input_types = {
        "text": ["str", "Document", "BaseMessage"],
        "source_language": ["str"],
        "target_language": ["str"],
        "candidate_labels": ["str", "List"],
        "api_key": ["str"],
    }

    for input_field in inputs:
        if input_field.name in expected_input_types:
            assert hasattr(input_field, "input_types"), f"{input_field.name} deve ter input_types"
            assert (
                input_field.input_types == expected_input_types[input_field.name]
            ), f"input_types incorretos para {input_field.name}"


@patch("requests.get")
def test_update_build_config_languages(mock_get, wool_ball_component):
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"code": "en"}, {"code": "pt"}]}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    build_config = dotdict({"source_language": {"options": []}, "target_language": {"options": []}})

    updated_config = wool_ball_component.update_build_config(
        build_config=build_config, field_value="Translation", field_name="task_type"
    )

    assert len(updated_config["source_language"]["options"]) > 0
    assert len(updated_config["target_language"]["options"]) > 0


@patch("requests.get")
def test_text_to_speech(mock_get, wool_ball_component, mock_headers):
    mock_response = Mock()
    mock_response.json.return_value = {"data": "base64_audio_data"}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    wool_ball_component.text = "Test text"
    wool_ball_component.target_language = "en"
    result = wool_ball_component._handle_tts(mock_headers)

    assert isinstance(result, Message)
    assert result.additional_kwargs["audio_data"] == "base64_audio_data"
    mock_get.assert_called_once()


@patch("requests.post")
def test_zero_shot_classification(mock_post, wool_ball_component, mock_headers):
    mock_response = Mock()
    mock_response.json.return_value = {"data": {"labels": ["category1", "category2"], "scores": [0.8, 0.2]}}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    wool_ball_component.text = "Test text"
    wool_ball_component.candidate_labels = "category1,category2"
    result = wool_ball_component._handle_zero_shot_classification(mock_headers)

    assert isinstance(result, Message)
    assert isinstance(result.text, str)
    mock_post.assert_called_once()


@patch("requests.post")
def test_summary(mock_post, wool_ball_component, mock_headers):
    mock_response = Mock()
    mock_response.json.return_value = {"data": "summarized text"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    wool_ball_component.text = "Long text to summarize"
    result = wool_ball_component._handle_summary(mock_headers)

    assert isinstance(result, Message)
    assert result.text == "summarized text"
    mock_post.assert_called_once()


@patch("requests.get")
def test_char_to_image(mock_get, wool_ball_component, mock_headers):
    mock_response = Mock()
    mock_response.json.return_value = {"data": "base64_image_data"}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    wool_ball_component.text = "A"
    result = wool_ball_component._handle_char_to_image(mock_headers)

    assert isinstance(result, Message)
    assert result.additional_kwargs["image_data"] == "base64_image_data"
    mock_get.assert_called_once()


def test_error_handling(wool_ball_component, mock_headers):
    with pytest.raises(ValueError, match="API key is required"):
        wool_ball_component.process_task()

    wool_ball_component.api_key = "test_key"
    wool_ball_component.task_type = "invalid_task"
    with pytest.raises(ValueError, match="Invalid task type selected"):
        wool_ball_component.process_task()

    wool_ball_component.task_type = "Text to Speech"
    with pytest.raises(ValueError, match="Text and target language are required"):
        wool_ball_component._handle_tts(mock_headers)

    wool_ball_component.task_type = "Translation"
    with pytest.raises(ValueError, match="Text, source language, and target language are required"):
        wool_ball_component._handle_translation(mock_headers)


@patch("requests.get")
def test_list_languages(mock_get, wool_ball_component):
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"code": "en"}, {"code": "pt"}]}
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    languages = wool_ball_component.list_languages()
    assert len(languages) > 0
    assert all(isinstance(lang, str) for lang in languages)

    mock_get.side_effect = requests.exceptions.RequestException
    languages = wool_ball_component.list_languages()
    assert languages == ["por_Latn", "eng_Latn", "spa_Latn"]


def test_update_build_config_all_tasks(wool_ball_component):
    build_config = dotdict(
        {
            "text": {"show": False},
            "source_language": {"show": False, "options": []},
            "target_language": {"show": False, "options": []},
            "candidate_labels": {"show": False},
            "api_key": {"show": False},
        }
    )

    task_field_mapping = {
        "Text to Speech": ["text", "target_language", "api_key"],
        "Text Generation": ["text", "api_key"],
        "Translation": ["text", "source_language", "target_language", "api_key"],
        "Zero-Shot Classification": ["text", "candidate_labels", "api_key"],
        "Summary": ["text", "api_key"],
        "Character to Image": ["text", "api_key"],
    }

    for task_type, expected_fields in task_field_mapping.items():
        updated_config = wool_ball_component.update_build_config(
            build_config=build_config.copy(), field_value=task_type, field_name="task_type"
        )

        for field in expected_fields:
            assert updated_config[field]["show"] is True, f"Campo {field} deveria estar visível para {task_type}"

        all_fields = ["text", "source_language", "target_language", "candidate_labels", "api_key"]
        hidden_fields = [f for f in all_fields if f not in expected_fields]
        for field in hidden_fields:
            assert updated_config[field]["show"] is False, f"Campo {field} deveria estar oculto para {task_type}"


if __name__ == "__main__":
    pytest.main([__file__])
