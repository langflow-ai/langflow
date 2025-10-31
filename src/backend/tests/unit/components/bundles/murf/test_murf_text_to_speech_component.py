import sys
from unittest.mock import MagicMock, patch

import pytest
from lfx.components.Murf.text_to_speech import MurfTextToSpeech
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestMurfTextToSpeechComponent(ComponentTestBaseWithoutClient):
    """Test suite for MurfTextToSpeech component."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return MurfTextToSpeech

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "text": "Testing Murf TTS",
            "api_key": "dummy_key",  # pragma: allowlist secret
            "locale": "en-US",
            "voice_id": "en-US-1",
            "multi_native_locale": None,
            "encode_as_base_64": False,
            "channel_type": "Mono",
            "format": "mp3",
            "rate": 0,
            "pitch": 0,
            "sample_rate": "44100",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    @pytest.fixture
    def dummy_voice_list(self):
        """Return mock voice list data for testing."""
        return [
            {
                "accent": "UK",
                "available_styles": ["Conversational"],
                "description": "Young Adult",
                "display_language": "English",
                "display_name": "Hazel (F)",
                "gender": "Female",
                "locale": "en-UK",
                "supported_locales": {
                    "en-US": {"available_styles": ["Conversational", "Promo"], "detail": "English (US & Canada)"},
                    "id-ID": {"available_styles": ["Narration"], "detail": "Indonesian (Indonesia)"},
                },
                "voice_id": "en-UK-hazel",
            },
            {
                "accent": "US & Canada",
                "available_styles": ["Promo", "Narration", "Newscast Formal", "Meditative"],
                "description": "Young Adult",
                "display_language": "English",
                "display_name": "Natalie (F)",
                "gender": "Female",
                "locale": "en-US",
                "supported_locales": {
                    "fr-FR": {"available_styles": ["Promo"], "detail": "French (France)"},
                    "es-ES": {"available_styles": ["Promo", "Conversational"], "detail": "Spanish (Spain)"},
                    "it-IT": {"available_styles": ["Conversational"], "detail": "Italian (Italy)"},
                    "en-US": {
                        "available_styles": ["Promo", "Narration", "Newscast Formal", "Meditative"],
                        "detail": "English (US & Canada)",
                    },
                },
                "voice_id": "en-US-natalie",
            },
        ]

    @pytest.fixture
    def mock_voice_objects(self, dummy_voice_list):
        """Return mock voice objects for API testing."""
        # Convert each dict in dummy_voice_list to a MagicMock with those attributes, simulating real voice objects
        from unittest.mock import MagicMock

        mock_voice_objs = []
        for voice_dict in dummy_voice_list:
            mock_voice = MagicMock()
            mock_voice.__dict__ = voice_dict.copy()  # __dict__ provides attribute access
            mock_voice_objs.append(mock_voice)
        return mock_voice_objs

    @pytest.fixture
    def mock_voice_dict(self, dummy_voice_list):
        """Return voice list organized as a dict by locale (as returned by initialize_voice_list_data)."""
        locales_to_voices = {}
        for voice_dict in dummy_voice_list:
            locale = voice_dict["locale"]
            if locale not in locales_to_voices:
                locales_to_voices[locale] = {
                    "display_name": f"{voice_dict['display_language']}({voice_dict['accent']})",
                    "voice_list": {},
                }
            locales_to_voices[locale]["voice_list"][voice_dict["voice_id"]] = voice_dict
        return locales_to_voices

    def _mock_murf_client(
        self,
        mock_generate_return=None,
        mock_generate_side_effect=None,
        mock_get_voices_return=None,
        mock_get_voices_side_effect=None,
    ):
        """Helper method to create and patch Murf client for testing.

        Args:
            mock_generate_return: Return value for the generate method
            mock_generate_side_effect: Side effect (like exception) for the generate method
            mock_get_voices_return: Return value for the get_voices method
            mock_get_voices_side_effect: Side effect (like exception) for the get_voices method

        Returns:
            tuple: (mock_murf_class, mock_client, context_manager)
        """
        # Create a mock Murf class
        mock_murf_class = MagicMock()
        mock_client = MagicMock()
        mock_generate = MagicMock()
        mock_get_voices = MagicMock()

        # Configure generate
        if mock_generate_side_effect:
            mock_generate.side_effect = mock_generate_side_effect
        else:
            # Convert dict to object with __dict__ populated (as expected by the component)
            generate_return = mock_generate_return or {"audio_url": "http://example.com/audio.mp3"}
            if isinstance(generate_return, dict):
                # Create a simple object instance with __dict__ attribute
                class MockResponse:
                    pass

                mock_response = MockResponse()
                mock_response.__dict__ = generate_return.copy()
                mock_generate.return_value = mock_response
            else:
                mock_generate.return_value = generate_return
        # Attach generate to client
        mock_client.text_to_speech.generate = mock_generate

        # Configure get_voices
        if mock_get_voices_side_effect:
            mock_get_voices.side_effect = mock_get_voices_side_effect
        else:
            # Default: return empty list if not given
            mock_get_voices.return_value = mock_get_voices_return if mock_get_voices_return is not None else []
        # Attach get_voices to client
        mock_client.text_to_speech.get_voices = mock_get_voices

        mock_murf_class.return_value = mock_client

        # Create a mock module with the mock Murf class
        mock_murf_module = MagicMock(Murf=mock_murf_class)

        # Return the context manager for patching
        return mock_murf_class, mock_client, patch.dict(sys.modules, {"murf": mock_murf_module})

    # Component Initialization Tests

    def test_component_initialization(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)

        assert component.text == "Testing Murf TTS"
        assert component.api_key == "dummy_key"  # pragma: allowlist secret
        assert component.locale == "en-US"
        assert component.voice_id == "en-US-1"
        assert component.encode_as_base_64 is False
        assert component.channel_type == "Mono"
        assert component.format == "mp3"
        assert component.rate == 0
        assert component.pitch == 0
        assert component.sample_rate == "44100"

    def test_component_display_properties(self, component_class):
        """Test component display properties."""
        component = component_class()

        assert component.display_name == "Murf Text to Speech"
        assert component.description == "Convert text to speech using Murf AI"
        assert component.icon == "Murf"
        assert component.documentation == "https://murf.ai/api/docs/api-reference/text-to-speech/generate"

    # generate_speech() Method Tests

    def test_generate_speech_success(self, component_class, default_kwargs):
        """Test successful speech generation."""
        mock_murf_class, mock_client, patch_context = self._mock_murf_client(
            mock_generate_return={
                "audio_url": "http://example.com/audio.mp3",
                "encoded_audio": None,
            },
        )

        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.generate_speech()

        assert isinstance(result, Data)
        assert "audio_url" in result.data
        mock_client.text_to_speech.generate.assert_called_once()
        mock_murf_class.assert_called_once_with(api_key=default_kwargs["api_key"])

    def test_generate_speech_no_api_key(self, component_class, default_kwargs):
        """Test speech generation with missing API key."""
        kwargs = dict(default_kwargs)
        kwargs["api_key"] = None

        component = component_class()
        component.set_attributes(kwargs)
        result = component.generate_speech()
        assert "error" in result.data
        assert "API error: Set your MURF_API_KEY as environment variable." in result.data["error"]

    def test_generate_speech_api_error(self, component_class, default_kwargs):
        """Test speech generation with API error."""
        _, _, patch_context = self._mock_murf_client(mock_generate_side_effect=RuntimeError("API failed"))

        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.generate_speech()

        assert isinstance(result, Data)
        assert "error" in result.data
        assert "API error" in result.data["error"]

    def test_generate_speech_with_multi_native_locale(self, component_class, default_kwargs):
        """Test speech generation with multi-native locale."""
        _, mock_client, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"}
        )

        kwargs = dict(default_kwargs)
        kwargs["multi_native_locale"] = "en-US"

        with patch_context:
            component = component_class()
            component.set_attributes(kwargs)
            result = component.generate_speech()

        assert isinstance(result, Data)
        mock_client.text_to_speech.generate.assert_called_once()
        call_args = mock_client.text_to_speech.generate.call_args[1]
        assert call_args["multi_native_locale"] == "en-US"

    # initialize_voice_list_data() Method Tests

    def test_initialize_voice_list_data_success(self, component_class, default_kwargs, mock_voice_objects):
        """Test successful voice list initialization."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )

        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.initialize_voice_list_data()
            assert isinstance(result, dict)
            assert "en-UK" in result
            assert "voice_list" in result["en-UK"]
            assert "en-UK-hazel" in result["en-UK"]["voice_list"]
            voice_data = result["en-UK"]["voice_list"]["en-UK-hazel"]
            assert "supported_locales" in voice_data
            assert "en-US" in voice_data["supported_locales"]
            assert "id-ID" in voice_data["supported_locales"]

    def test_initialize_voice_list_data_keyerror(self, component_class, default_kwargs):
        """Test voice list initialization with KeyError."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_side_effect=KeyError("No __dict__"),
        )
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.initialize_voice_list_data()
            assert isinstance(result, dict)
            assert "error" in result
            assert "Error initializing Murf Voice List: 'No __dict__'" in result["error"]

    def test_initialize_voice_list_data_attribute_error(self, component_class, default_kwargs):
        """Test voice list initialization with AttributeError."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_side_effect=AttributeError("No __dict__"),
        )
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.initialize_voice_list_data()
            assert isinstance(result, dict)
            assert "error" in result
            assert "Error initializing Murf Voice List: No __dict__" in result["error"]

    def test_initialize_voice_list_data_value_error(self, component_class, default_kwargs):
        """Test voice list initialization with ValueError."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_side_effect=ValueError("Invalid API key"),
        )
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.initialize_voice_list_data()
            assert isinstance(result, dict)
            assert "error" in result
            assert "Error initializing Murf Voice List: Invalid API key" in result["error"]

    # _update_build_config_locale() Method Tests

    def test_update_build_config_locale_with_voices(self, component_class, default_kwargs, mock_voice_objects):
        """Test locale config update with voice data."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )

        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            voice_list = component.initialize_voice_list_data()
            build_config = {
                "locale": {},
                "voice_id": {},
                "multi_native_locale": {},
                "murf_voice_list": voice_list,
            }
            result = component._update_build_config_locale(build_config)
            assert result["locale"]["show"] is True
            assert "en-UK" in result["locale"]["options"]
            assert "en-US" in result["locale"]["options"]

    def test_update_build_config_locale_without_voices(self, component_class):
        """Test locale config update without voice data."""
        build_config = {
            "murf_voice_list": None,
            "locale": {},
            "voice_id": {},
            "multi_native_locale": {},
        }

        component = component_class()
        result = component._update_build_config_locale(build_config)

        assert result["locale"]["show"] is False

    def test_update_build_config_locale_empty_voices(self, component_class):
        """Test locale config update with empty voice data."""
        build_config = {
            "murf_voice_list": {},
            "locale": {},
            "voice_id": {},
            "multi_native_locale": {},
        }

        component = component_class()
        result = component._update_build_config_locale(build_config)

        assert result["locale"]["show"] is False

    # _update_build_config_voice_id() Method Tests

    def test_update_build_config_voice_id_success(self, component_class, default_kwargs, mock_voice_objects):
        """Test voice ID config update with valid locale."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {
            "locale": {"value": "en-US"},
            "voice_id": {},
            "multi_native_locale": {},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            voice_list = component.initialize_voice_list_data()
            build_config["murf_voice_list"] = voice_list
            result = component._update_build_config_voice_id(build_config)
            assert result["voice_id"]["show"] is True
            assert "en-US-natalie" in result["voice_id"]["options"]
            assert "en-US-natalie" in result["voice_id"]["value"]

    def test_update_build_config_voice_id_no_locale(self, component_class, dummy_voice_list):
        """Test voice ID config update without locale selection."""
        build_config = {
            "murf_voice_list": dummy_voice_list,
            "locale": {},
            "voice_id": {},
            "multi_native_locale": {},
        }

        component = component_class()
        result = component._update_build_config_voice_id(build_config)

        assert result["voice_id"]["show"] is False

    def test_update_build_config_voice_id_invalid_locale(self, component_class, dummy_voice_list):
        """Test voice ID config update with invalid locale."""
        build_config = {
            "murf_voice_list": dummy_voice_list,
            "locale": {"value": "invalid-locale"},
            "voice_id": {},
            "multi_native_locale": {},
        }

        component = component_class()
        result = component._update_build_config_voice_id(build_config)

        assert result["voice_id"]["show"] is False

    def test_update_build_config_voice_id_empty_voice_list(self, component_class, default_kwargs, mock_voice_objects):
        """Test voice ID config update with empty voice list for locale."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"locale": {"value": "en-US"}, "voice_id": {}, "multi_native_locale": {}, "murf_voice_list": {}}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component._update_build_config_voice_id(build_config)
            assert result["voice_id"]["show"] is False

    # _update_build_config_multi_native_locale() Method Tests

    def test_update_build_config_multi_native_locale_success(self, component_class, default_kwargs, mock_voice_objects):
        #     """Test multi-native locale config update with valid voice."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {
            "locale": {"value": "en-US"},
            "voice_id": {
                "value": "en-US-natalie",
            },
            "multi_native_locale": {},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            voice_list = component.initialize_voice_list_data()
            result = component._update_build_config_multi_native_locale(build_config, "en-US-natalie", voice_list)
            assert result["multi_native_locale"]["show"] is True
            assert "en-US" in result["multi_native_locale"]["options"]
            assert "es-ES" in result["multi_native_locale"]["options"]

    def test_update_build_config_multi_native_locale_no_voices(
        self, component_class, default_kwargs, mock_voice_objects
    ):
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        """Test multi-native locale config update without voice data."""
        build_config = {
            "murf_voice_list": None,
            "locale": {"value": "en-US"},
            "voice_id": {},
            "multi_native_locale": {},
        }

        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component._update_build_config_multi_native_locale(build_config, "en-US-natalie", [])
            assert result["multi_native_locale"]["show"] is False

    def test_update_build_config_multi_native_locale_invalid_voice(
        self, component_class, default_kwargs, mock_voice_objects
    ):
        """Test multi-native locale config update with invalid voice."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )

        build_config = {
            "murf_voice_list": mock_voice_objects,
            "locale": {"value": "en-US"},
            "voice_id": {},
            "multi_native_locale": {},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component._update_build_config_multi_native_locale(build_config, "en-US-1")
            assert result["multi_native_locale"]["show"] is False

    def test_update_build_config_multi_native_locale_no_supported_locales(
        self, component_class, default_kwargs, mock_voice_objects
    ):
        """Test multi-native locale config update with voice having no supported locales."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {
            "murf_voice_list": mock_voice_objects,
            "locale": {"value": "en-US"},
            "voice_id": {},
            "multi_native_locale": {},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component._update_build_config_multi_native_locale(build_config, "en-US-natalie")
            assert result["multi_native_locale"]["show"] is False

    # build_config() Method Tests

    def test_build_config_with_api_key(self, component_class, default_kwargs, mock_voice_objects, mock_voice_dict):
        """Test build config with API key triggers voice list initialization."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"murf_voice_list": None}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.build_config(build_config)
            assert result["murf_voice_list"] == mock_voice_dict
            assert result["locale"]["show"] is True

    def test_build_config_without_api_key(self, component_class, default_kwargs, mock_voice_objects):
        """Test build config without API key doesn't trigger voice list initialization."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"murf_voice_list": None}
        with patch_context:
            component = component_class()
            # Set api_key to empty string to test without API key
            kwargs = dict(default_kwargs)
            kwargs["api_key"] = ""
            component.set_attributes(kwargs)
            result = component.build_config(build_config)
            # Without API key, voice list should remain None
            assert result["murf_voice_list"] is None

    def test_build_config_with_existing_voices(self, component_class, default_kwargs, mock_voice_dict):
        """Test build config with existing voice list doesn't reinitialize."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
        )
        build_config = {"murf_voice_list": mock_voice_dict}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.build_config(build_config)
            # With existing voices, should not reinitialize
            assert result["murf_voice_list"] == mock_voice_dict

    # update_build_config() Method Tests

    def test_update_build_config_api_key_field(
        self, component_class, default_kwargs, mock_voice_objects, mock_voice_dict
    ):
        """Test build config update with API key field change."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"murf_voice_list": None}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "new_api_key", field_name="api_key")
            assert result["murf_voice_list"] == mock_voice_dict
            assert result["locale"]["show"] is True

    def test_update_build_config_api_key_empty(self, component_class, default_kwargs, mock_voice_objects):
        """Test build config update with empty API key."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"murf_voice_list": None}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "", field_name="api_key")
            # Empty API key should not trigger voice list initialization
            assert result["murf_voice_list"] is None

    def test_update_build_config_locale_field(self, component_class, default_kwargs, mock_voice_dict):
        """Test build config update with locale field change."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
        )
        build_config = {
            "murf_voice_list": mock_voice_dict,
            "locale": {"value": "en-US"},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "en-US", field_name="locale")
            assert result["voice_id"]["show"] is True

    def test_update_build_config_locale_field_empty(self, component_class, default_kwargs, mock_voice_dict):
        """Test build config update with empty locale field."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
        )
        build_config = {
            "murf_voice_list": mock_voice_dict,
            "locale": {"value": "en-US"},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "", field_name="locale")
            assert result["voice_id"]["show"] is False

    def test_update_build_config_voice_id_field(self, component_class, default_kwargs, mock_voice_dict):
        """Test build config update with voice ID field change."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
        )
        build_config = {
            "multi_native_locale": {},
            "murf_voice_list": mock_voice_dict,
            "locale": {"value": "en-US"},
            "voice_id": {"value": "en-US-natalie"},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "en-US-natalie", field_name="voice_id")
            assert result["multi_native_locale"]["show"] is True

        build_config = {
            "multi_native_locale": {},
            "murf_voice_list": mock_voice_dict,
            "locale": {"value": "en-UK"},
            "voice_id": {"value": "en-UK-hazel"},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "en-UK-hazel", field_name="voice_id")
            assert result["multi_native_locale"]["show"] is True

    def test_update_build_config_voice_id_field_empty(self, component_class, default_kwargs, mock_voice_dict):
        """Test build config update with empty voice ID field."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
        )
        build_config = {
            "multi_native_locale": {},
            "murf_voice_list": mock_voice_dict,
            "locale": {"value": "en-US"},
        }
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "", field_name="voice_id")
            assert result["multi_native_locale"]["show"] is False

    def test_update_build_config_unknown_field(self, component_class, default_kwargs, mock_voice_objects):
        """Test build config update with unknown field returns original config."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"foo": "bar"}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "baz", field_name="unknown_field")
            assert result == build_config

    def test_update_build_config_no_field_name(self, component_class, default_kwargs, mock_voice_objects):
        """Test build config update with no field name returns original config."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=mock_voice_objects,
        )
        build_config = {"foo": "bar"}
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.update_build_config(build_config, "baz", field_name=None)
            assert result == build_config

    # Edge Cases and Error Handling Tests

    def test_initialize_voice_list_data_with_empty_voice_list(self, component_class, default_kwargs):
        """Test voice list initialization with empty API response."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=None,
        )
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.initialize_voice_list_data()
            assert isinstance(result, dict)
            assert "error" in result
            assert "No voices found" in result["error"]

    def test_initialize_voice_list_data_with_malformed_voice_data(self, component_class, default_kwargs):
        """Test voice list initialization with malformed voice data."""
        _, _, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
            mock_get_voices_return=[{"voice_id": "test", "display_name": "Test"}],
        )
        with patch_context:
            component = component_class()
            component.set_attributes(default_kwargs)
            result = component.initialize_voice_list_data()

            assert isinstance(result, dict)
            assert "error" in result

    def test_generate_speech_with_all_parameters(self, component_class, default_kwargs):
        """Test speech generation with all parameters set."""
        _, mock_client, patch_context = self._mock_murf_client(
            mock_generate_return={"audio_url": "http://example.com/audio.mp3"},
        )
        with patch_context:
            kwargs = dict(default_kwargs)
            kwargs.update(
                {
                    "text": "Hello, world!",
                    "encode_as_base_64": True,
                    "channel_type": "Stereo",
                    "format": "wav",
                    "rate": 10,
                    "pitch": -5,
                    "sample_rate": "48000",
                }
            )

            component = component_class()
            component.set_attributes(kwargs)
            result = component.generate_speech()

            assert isinstance(result, Data)
            mock_client.text_to_speech.generate.assert_called_once()
            call_args = mock_client.text_to_speech.generate.call_args[1]
            assert call_args["encode_as_base_64"] is True
            assert call_args["channel_type"] == "stereo"
            assert call_args["format"] == "wav"
