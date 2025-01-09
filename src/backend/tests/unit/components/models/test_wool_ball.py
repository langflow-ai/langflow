import pytest
import requests
from unittest.mock import Mock, patch, mock_open
from langflow.components.models.wool_ball import WoolBallComponent
from langflow.schema.message import Message
from langflow.schema.dotdict import dotdict

# Fixture for the component
@pytest.fixture
def wool_ball_component():
    return WoolBallComponent()

# Fixture for mock headers
@pytest.fixture
def mock_headers():
    return {
        "Authorization": "Bearer test_api_key",
        "Content-Type": "application/json"
    }

def test_wool_ball_inputs(wool_ball_component):
    """Test if all required inputs are present with correct types"""
    inputs = wool_ball_component.inputs

    # Check required inputs
    input_names = [inp.name for inp in inputs]
    required_inputs = [
        "task_type",
        "text",
        "source_language",
        "target_language",
        "file_input",
        "candidate_labels",
        "api_key"
    ]
    
    for name in required_inputs:
        assert name in input_names, f"Missing input: {name}"

def test_wool_ball_task_types(wool_ball_component):
    """Test if all task types are properly defined"""
    expected_tasks = [
        "Text to Speech",
        "Speech to Text",
        "Text Generation",
        "Translation",
        "Zero-Shot Classification",
        "Sentiment Analysis",
        "Image+text to text",
        "Image Classification",
        "Zero-Shot Image Classification",
        "Summary and summarization",
        "Character to Image"
    ]
    
    assert wool_ball_component.TASK_TYPES == expected_tasks

def test_supported_languages(wool_ball_component):
    """Test if supported languages are properly defined"""
    expected_languages = ["por_Latn", "eng_Latn", "spa_Latn"]
    assert wool_ball_component.SUPPORTED_LANGUAGES == expected_languages

@pytest.mark.parametrize(
    "status_code,expected_error",
    [
        (401, "Could not validate API key"),
        (429, "Rate limit exceeded"),
        (500, "API request failed: 500"),
    ],
)
def test_exception_handling(wool_ball_component, status_code, expected_error):
    """Test exception handling for different HTTP status codes"""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.text = "Error message"
    
    mock_exception = requests.exceptions.HTTPError()
    mock_exception.response = mock_response
    
    with pytest.raises(ValueError, match=expected_error):
        wool_ball_component._get_exception_message(mock_exception)

@patch('requests.post')
def test_text_to_speech(mock_post, wool_ball_component, mock_headers):
    """Test Text to Speech task"""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"audio": "base64_audio_data"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Set component attributes
    wool_ball_component.text = "Test text"
    wool_ball_component.target_language = "eng_Latn"
    wool_ball_component.api_key = "test_api_key"

    # Test the handler
    result = wool_ball_component._handle_tts(mock_headers)
    
    assert isinstance(result, Message)
    assert result.additional_kwargs["audio_data"] == "base64_audio_data"
    mock_post.assert_called_once()

@patch('requests.post')
def test_speech_to_text(mock_post, wool_ball_component, mock_headers):
    """Test Speech to Text task"""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {"text": "transcribed text"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Mock file
    mock_file = mock_open(read_data=b"audio data")
    
    with patch('builtins.open', mock_file):
        wool_ball_component.file_input = "test.wav"
        result = wool_ball_component._handle_stt(mock_headers)
    
    assert isinstance(result, Message)
    assert result.text == "transcribed text"
    mock_post.assert_called_once()

@patch('requests.post')
def test_text_generation(mock_post, wool_ball_component, mock_headers):
    """Test Text Generation task"""
    mock_response = Mock()
    mock_response.json.return_value = {"generated_text": "generated content"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    wool_ball_component.text = "Input text"
    result = wool_ball_component._handle_text_generation(mock_headers)
    
    assert isinstance(result, Message)
    assert result.text == "generated content"
    mock_post.assert_called_once()

@patch('requests.post')
def test_translation(mock_post, wool_ball_component, mock_headers):
    """Test Translation task"""
    mock_response = Mock()
    mock_response.json.return_value = {"translated_text": "translated content"}
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    wool_ball_component.text = "Hello"
    wool_ball_component.source_language = "eng_Latn"
    wool_ball_component.target_language = "por_Latn"
    
    result = wool_ball_component._handle_translation(mock_headers)
    
    assert isinstance(result, Message)
    assert result.text == "translated content"
    mock_post.assert_called_once()

def test_build_config(wool_ball_component):
    """Test build configuration updates"""
    # Primeiro, chamar o build da classe pai
    build_config = wool_ball_component.build()
    
    # Verificar se é um dotdict
    assert isinstance(build_config, dotdict), "build_config deve ser um dotdict"
    
    # Verificar campos necessários
    required_fields = [
        "task_type", "text", "source_language", 
        "target_language", "candidate_labels", "file_input"
    ]
    for field in required_fields:
        assert field in build_config, f"Campo {field} não encontrado"
        assert isinstance(build_config[field], dict), f"Campo {field} não é um dicionário"
    
    # Verificar valor padrão do task_type
    assert "task_type" in build_config
    assert "value" in build_config["task_type"]
    assert build_config["task_type"]["value"] == "Text Generation"

def test_update_build_config_with_none(wool_ball_component):
    """Test update_build_config with None input"""
    result = wool_ball_component.update_build_config(
        build_config=None,
        field_value="Text Generation",
        field_name="task_type"
    )
    
    assert isinstance(result, dotdict)
    assert "text" in result
    assert result["text"]["show"] is True

@pytest.mark.parametrize(
    "task_type,required_fields",
    [
        ("Text to Speech", ["text", "target_language"]),
        ("Speech to Text", ["file_input"]),
        ("Text Generation", ["text"]),
        ("Translation", ["text", "source_language", "target_language"]),
        ("Zero-Shot Classification", ["text", "candidate_labels"]),
        ("Sentiment Analysis", ["file_input"]),
        ("Image+text to text", ["text", "file_input"]),
        ("Image Classification", ["file_input"]),
        ("Zero-Shot Image Classification", ["file_input", "candidate_labels"]),
        ("Summary and summarization", ["text"]),
        ("Character to Image", ["text"]),
    ],
)
def test_field_visibility(wool_ball_component, task_type, required_fields):
    """Test field visibility for different task types"""
    # Criar configuração inicial como dotdict
    build_config = dotdict({
        "task_type": {"value": task_type},
    })
    
    # Inicializar campos
    all_fields = ["text", "source_language", "target_language", "candidate_labels", "file_input"]
    for field in all_fields:
        build_config[field] = {"show": False}
    
    # Atualizar configuração
    updated_config = wool_ball_component.update_build_config(
        build_config=build_config,
        field_value=task_type,
        field_name="task_type"
    )
    
    # Verificações
    assert isinstance(updated_config, dotdict), "updated_config deve ser um dotdict"
    
    # Verificar campos visíveis
    for field in required_fields:
        assert field in updated_config, f"Campo {field} não encontrado"
        assert updated_config[field]["show"] is True, f"Campo {field} deveria estar visível para {task_type}"

def test_initial_build_config(wool_ball_component):
    """Test the initial build configuration structure"""
    build_config = wool_ball_component.build()
    
    # Verificar campos necessários
    required_fields = [
        "task_type", "text", "source_language", 
        "target_language", "file_input", "candidate_labels"
    ]
    
    for field in required_fields:
        assert field in build_config, f"Campo {field} não encontrado"
        if field == "task_type":
            assert "value" in build_config[field]
            assert build_config[field]["value"] == "Text Generation"
        else:
            assert "show" in build_config[field]

def test_update_build_config_structure(wool_ball_component):
    """Test the update_build_config method structure"""
    initial_config = wool_ball_component.build()
    
    for task_type in wool_ball_component.TASK_TYPES:
        updated_config = wool_ball_component.update_build_config(
            build_config=initial_config.copy(),
            field_value=task_type,
            field_name="task_type"
        )
        
        # Verificar estrutura básica
        assert "task_type" in updated_config
        
        # Verificar se todos os campos têm o atributo show
        all_fields = ["text", "source_language", "target_language", "candidate_labels", "file_input"]
        for field in all_fields:
            assert field in updated_config, f"Campo {field} não encontrado para {task_type}"
            assert "show" in updated_config[field], f"Atributo 'show' não encontrado em {field} para {task_type}"

if __name__ == "__main__":
    pytest.main([__file__]) 