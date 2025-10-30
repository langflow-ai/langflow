# text_to_speech.py
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, MultilineInput, SecretStrInput, SliderInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output


class MurfTextToSpeech(Component):
    display_name = "Murf Text to Speech"
    description = "Convert text to speech using Murf AI"
    icon = "Murf"
    documentation = "https://murf.ai/api/docs/api-reference/text-to-speech/generate"

    inputs = [
        MultilineInput(
            name="text",
            display_name="Input",
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Murf API Key",
            info="The Murf API Key to use for the Murf model.",
            advanced=False,
            value="MURF_API_KEY",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="locale",
            display_name="Locale",
            dynamic=True,
            show=False,
            real_time_refresh=True,
            info="The locale of the voice to use for speech synthesis.",
        ),
        DropdownInput(
            name="voice_id",
            display_name="Voice ID",
            dynamic=True,
            show=False,
            real_time_refresh=True,
            info="The voice ID to use for speech synthesis.",
        ),
        DropdownInput(
            name="multi_native_locale",
            display_name="Multi Native Locale",
            dynamic=True,
            show=False,
            required=False,
            info="The multi native locale to use for speech synthesis.",
        ),
        BoolInput(
            name="encode_as_base_64",
            display_name="Encode as Base 64",
            value=False,
            advanced=True,
            info="Whether to encode the audio as base 64.",
        ),
        DropdownInput(
            name="channel_type",
            display_name="Channel Type",
            options=["Mono", "Stereo"],
            value="Mono",
            advanced=True,
            info="The channel type to use for speech synthesis.",
        ),
        DropdownInput(
            name="format",
            display_name="Output Format",
            options=["mp3", "wav", "flac", "alaw", "ulaw", "pcm", "ogg"],
            value="mp3",
            advanced=True,
            info="The format of the audio to use for speech synthesis.",
        ),
        SliderInput(
            name="rate", display_name="Speed", value=0, range_spec=RangeSpec(min=-50, max=50, step=1), advanced=True
        ),
        SliderInput(
            name="pitch", display_name="Pitch", value=0, range_spec=RangeSpec(min=-50, max=50, step=1), advanced=True
        ),
        DropdownInput(
            name="sample_rate",
            display_name="Sample Rate",
            options=["8000", "24000", "44100", "48000"],
            value="44100",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="response", display_name="Response", method="generate_speech"),
    ]

    def generate_speech(self) -> Data:
        try:
            from murf import Murf

            # Initialize Murf client
            client = Murf(api_key=self.api_key)

            if not self.api_key:
                msg = "Set your MURF_API_KEY as environment variable."
                raise ValueError(msg)

            # Generate speech
            res = client.text_to_speech.generate(
                text=self.text,
                voice_id=self.voice_id,
                encode_as_base_64=self.encode_as_base_64,
                channel_type=self.channel_type.lower(),
                format=self.format,
                rate=self.rate,
                pitch=self.pitch,
                sample_rate=int(self.sample_rate),
                **({"multi_native_locale": self.multi_native_locale} if self.multi_native_locale is not None else {}),
            )
            return Data(data=res)
        except Exception as e:  # noqa: BLE001
            self.log(f"Error generating speech: {e!s}")
            return Output(name="error", message=Message(text=f"API error: {e}"), error=True)

    def initialize_voice_list_data(self) -> dict:
        try:
            from murf import Murf

            client = Murf(api_key=self.api_key)
            voice_list = client.text_to_speech.get_voices()
            voice_list_dict = [voice.__dict__ for voice in voice_list]
            locales_to_voices = {}
            for voice in voice_list_dict:
                locale = voice["locale"]
                if locale not in locales_to_voices:
                    locales_to_voices[locale] = {
                        "display_name": f"{voice['display_language']}({voice['accent']})",
                        "voice_list": {},
                    }
                locales_to_voices[locale]["voice_list"][voice["voice_id"]] = voice
            return locales_to_voices  # noqa: TRY300
        except (KeyError, AttributeError, ValueError) as e:
            self.log(f"Error initializing Murf Voice List: {e}")
            msg = f"Error initializing Murf Voice List: {e}"
            return Data(data={"error": msg})

    def _update_build_config_locale(self, build_config: dict) -> dict:
        voices = build_config.get("murf_voice_list")
        if voices:
            build_config["locale"]["options"] = list(voices.keys())
            build_config["locale"]["options_metadata"] = [
                {locale: voices[locale].get("display_name")} for locale in list(voices.keys())
            ]
            build_config["locale"]["value"] = "en-US"  # default: en-US
            build_config["locale"]["show"] = True
            build_config = self._update_build_config_voice_id(build_config)
        else:
            build_config["locale"]["show"] = False
        return build_config

    def _update_build_config_voice_id(self, build_config: dict) -> dict:
        selected_locale = build_config["locale"]["value"]
        voices = build_config.get("murf_voice_list")
        if voices and selected_locale in voices:
            options = voices.get(selected_locale).get("voice_list")
            build_config["voice_id"]["options"] = list(options.keys())
            build_config["voice_id"]["options_metadata"] = [
                {
                    "Name": voice.get("display_name"),
                    "Voice ID": voice.get("voice_id"),
                    "Description": voice.get("description"),
                    "Gender": voice.get("gender"),
                    "Locale": voice.get("locale"),
                    "Accent": voice.get("accent"),
                    "Styles": voice.get("available_styles"),
                    "Supported Locales": list(voice.get("supported_locales").keys()),
                }
                for voice in options.values()
            ]
            build_config["voice_id"]["value"] = next(iter(options.keys()))
            build_config["voice_id"]["show"] = True
            build_config = self._update_build_config_multi_native_locale(
                build_config, build_config["voice_id"]["value"], voices
            )
        else:
            build_config["voice_id"]["show"] = False
        return build_config

    def _update_build_config_multi_native_locale(
        self, build_config: dict, field_value: str, voices: dict | None = None
    ) -> dict:
        if voices is None:
            voices = build_config["murf_voice_list"]
            if voices is None or len(voices) == 0:
                voices = self.initialize_voice_list_data()
                build_config["murf_voice_list"] = voices
        selected_locale = build_config["locale"]["value"]
        selected_voice_id = field_value

        selected_voice = voices[selected_locale]["voice_list"][selected_voice_id]
        if selected_voice and selected_voice["supported_locales"]:
            locale_options = selected_voice["supported_locales"].keys()
            build_config["multi_native_locale"]["options"] = list(locale_options)
            options_metadata = []
            for locale in selected_voice["supported_locales"].values():
                if locale is dict:
                    options_metadata.append({"locale": locale.get("detail")})
                else:
                    options_metadata.append({"locale": locale.__dict__.get("detail")})
            build_config["multi_native_locale"]["options_metadata"] = options_metadata
            build_config["multi_native_locale"]["value"] = selected_voice.get("locale")
            build_config["multi_native_locale"]["show"] = True
        else:
            build_config["multi_native_locale"]["show"] = False
        return build_config

    def build_config(self, build_config):
        api_key = self.config.get("api_key")
        voices = self.config.get("murf_voice_list")

        if api_key and not voices:
            voices = self.initialize_voice_list_data()
            build_config["murf_voice_list"] = voices
            build_config = self._update_build_config_locale(build_config)

        return build_config

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "api_key" and len(field_value) > 0:
            voices = build_config.get("murf_voice_list")
            if voices is None or len(voices.keys()) == 0:
                voices = self.initialize_voice_list_data()
                build_config["murf_voice_list"] = voices
            build_config = self._update_build_config_locale(build_config)
        elif field_name == "locale":
            if field_value:
                build_config = self._update_build_config_voice_id(build_config)
            else:
                build_config["voice_id"]["show"] = False
        elif field_name == "voice_id":
            if field_value:
                build_config = self._update_build_config_multi_native_locale(build_config, field_value)
            else:
                build_config["multi_native_locale"]["show"] = False
        return build_config
