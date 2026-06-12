"""Tests for pipecat_services components (metadata + tool registration)."""



def _service_input_names(component_cls) -> set:
    return {i.name for i in component_cls.inputs}


def _service_output_types(component_cls) -> set:
    return {t for o in component_cls.outputs for t in o.types}


class TestGeminiLiveLLMServiceComponent:
    """GeminiLiveLLMServiceComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_services.gemini_live_s2s import GeminiLiveLLMServiceComponent

        assert GeminiLiveLLMServiceComponent.display_name == "Gemini Live (S2S)"
        assert GeminiLiveLLMServiceComponent.name == "GeminiLiveLLM"
        assert GeminiLiveLLMServiceComponent.category == "pipecat"

    def test_output_types_include_s2s(self):
        from lfx.components.pipecat_services.gemini_live_s2s import GeminiLiveLLMServiceComponent

        types = _service_output_types(GeminiLiveLLMServiceComponent)
        assert "PipecatS2SService" in types
        assert "PipecatLLMService" in types

    def test_has_required_inputs(self):
        from lfx.components.pipecat_services.gemini_live_s2s import GeminiLiveLLMServiceComponent

        names = _service_input_names(GeminiLiveLLMServiceComponent)
        assert "api_key" in names
        assert "model" in names
        assert "voice_id" in names


class TestOpenAILLMServiceComponent:
    """OpenAILLMServiceComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_services.openai_llm import OpenAILLMServiceComponent

        assert OpenAILLMServiceComponent.display_name == "OpenAI LLM"
        assert OpenAILLMServiceComponent.name == "OpenAILLM"
        assert OpenAILLMServiceComponent.category == "pipecat"

    def test_output_type_is_llm_service(self):
        from lfx.components.pipecat_services.openai_llm import OpenAILLMServiceComponent

        types = _service_output_types(OpenAILLMServiceComponent)
        assert "PipecatLLMService" in types

    def test_has_model_and_api_key(self):
        from lfx.components.pipecat_services.openai_llm import OpenAILLMServiceComponent

        names = _service_input_names(OpenAILLMServiceComponent)
        assert "api_key" in names
        assert "model" in names


class TestDeepgramSTTServiceComponent:
    """DeepgramSTTServiceComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_services.deepgram_stt import DeepgramSTTServiceComponent

        assert DeepgramSTTServiceComponent.display_name == "Deepgram STT"
        assert DeepgramSTTServiceComponent.name == "DeepgramSTT"
        assert DeepgramSTTServiceComponent.category == "pipecat"

    def test_output_type_is_stt(self):
        from lfx.components.pipecat_services.deepgram_stt import DeepgramSTTServiceComponent

        types = _service_output_types(DeepgramSTTServiceComponent)
        assert "PipecatSTTService" in types


class TestElevenLabsTTSServiceComponent:
    """ElevenLabsTTSServiceComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_services.elevenlabs_tts import ElevenLabsTTSServiceComponent

        assert ElevenLabsTTSServiceComponent.display_name == "ElevenLabs TTS"
        assert ElevenLabsTTSServiceComponent.name == "ElevenLabsTTS"
        assert ElevenLabsTTSServiceComponent.category == "pipecat"

    def test_output_type_is_tts(self):
        from lfx.components.pipecat_services.elevenlabs_tts import ElevenLabsTTSServiceComponent

        types = _service_output_types(ElevenLabsTTSServiceComponent)
        assert "PipecatTTSService" in types

    def test_has_voice_id_input(self):
        from lfx.components.pipecat_services.elevenlabs_tts import ElevenLabsTTSServiceComponent

        names = _service_input_names(ElevenLabsTTSServiceComponent)
        assert "voice_id" in names


class TestAnthropicLLMServiceComponent:
    """AnthropicLLMServiceComponent structure."""

    def test_metadata(self):
        from lfx.components.pipecat_services.anthropic_llm import AnthropicLLMServiceComponent

        assert AnthropicLLMServiceComponent.display_name == "Anthropic LLM"
        assert AnthropicLLMServiceComponent.name == "AnthropicLLM"
        assert AnthropicLLMServiceComponent.category == "pipecat"

    def test_output_type_is_llm_service(self):
        from lfx.components.pipecat_services.anthropic_llm import AnthropicLLMServiceComponent

        types = _service_output_types(AnthropicLLMServiceComponent)
        assert "PipecatLLMService" in types


class TestCartesiaTTSServiceComponent:
    def test_metadata(self):
        from lfx.components.pipecat_services.cartesia_tts import CartesiaTTSServiceComponent

        assert CartesiaTTSServiceComponent.display_name == "Cartesia TTS"
        assert CartesiaTTSServiceComponent.category == "pipecat"

    def test_output_type_is_tts(self):
        from lfx.components.pipecat_services.cartesia_tts import CartesiaTTSServiceComponent

        types = _service_output_types(CartesiaTTSServiceComponent)
        assert "PipecatTTSService" in types


class TestOpenAISTTServiceComponent:
    def test_metadata(self):
        from lfx.components.pipecat_services.openai_stt import OpenAISTTServiceComponent

        assert OpenAISTTServiceComponent.display_name == "OpenAI STT (Whisper)"
        assert OpenAISTTServiceComponent.category == "pipecat"

    def test_output_type_is_stt(self):
        from lfx.components.pipecat_services.openai_stt import OpenAISTTServiceComponent

        types = _service_output_types(OpenAISTTServiceComponent)
        assert "PipecatSTTService" in types


class TestOpenAITTSServiceComponent:
    def test_metadata(self):
        from lfx.components.pipecat_services.openai_tts import OpenAITTSServiceComponent

        assert OpenAITTSServiceComponent.display_name == "OpenAI TTS"
        assert OpenAITTSServiceComponent.category == "pipecat"

    def test_output_type_is_tts(self):
        from lfx.components.pipecat_services.openai_tts import OpenAITTSServiceComponent

        types = _service_output_types(OpenAITTSServiceComponent)
        assert "PipecatTTSService" in types


class TestGoogleLLMServiceComponent:
    def test_metadata(self):
        from lfx.components.pipecat_services.google_llm import GoogleLLMServiceComponent

        assert GoogleLLMServiceComponent.display_name == "Google LLM"
        assert GoogleLLMServiceComponent.category == "pipecat"
