import assemblyai as aai
from langflow.custom import Component
from langflow.io import DropdownInput, FloatInput, IntInput, MessageInput, SecretStrInput, DataInput, Output
from langflow.schema import Data
from loguru import logger


class AssemblyAILeMUR(Component):
    display_name = "AssemblyAI LeMUR"
    description = "Apply Large Language Models to spoken data using the AssemblyAI LeMUR framework"
    documentation = "https://www.assemblyai.com/docs/lemur"
    icon = "🔄"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Assembly API Key",
            info="Your AssemblyAI API key. You can get one from https://www.assemblyai.com/",
            advanced=False,
        ),
        DataInput(
            name="transcription_result",
            display_name="Transcription Result",
            info="The transcription result from AssemblyAI",
        ),
        MessageInput(
            name="prompt",
            display_name="Input Prompt",
            info="The text to prompt the model",
        ),
        DropdownInput(
            name="final_model",
            display_name="Final Model",
            options=["claude3_5_sonnet", "claude3_opus", "claude3_haiku", "claude3_sonnet"],
            value="claude3_5_sonnet",
            info="The model that is used for the final prompt after compression is performed",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            advanced=True,
            value=0.0,
            info="The temperature to use for the model",
        ),
        IntInput(
            name="max_output_size",
            display_name=" Max Output Size",
            advanced=True,
            value=2000,
            info="Max output size in tokens, up to 4000",
        ),
    ]

    outputs = [
        Output(display_name="LeMUR Response", name="lemur_response", method="run_lemur"),
    ]

    def run_lemur(self) -> Data:
        """Use the LeMUR task endpoint to input the LLM prompt."""
        aai.settings.api_key = self.api_key

        # check if it's an error message from the previous step
        if self.transcription_result.data.get("error"):
            self.status = self.transcription_result.data["error"]
            return self.transcription_result

        if not self.prompt or not self.prompt.text:
            self.status = "No prompt specified"
            return Data(data={"error": "No prompt specified"})

        try:
            transcript = aai.Transcript.get_by_id(self.transcription_result.data["id"])
        except Exception as e:
            error = f"Getting transcription failed: {str(e)}"
            self.status = error
            return Data(data={"error": error})

        if transcript.status == aai.TranscriptStatus.completed:
            try:
                result = transcript.lemur.task(
                    prompt=self.prompt.text,
                    final_model=self.get_final_model(self.final_model),
                    temperature=self.temperature,
                    max_output_size=self.max_output_size,
                )

                result = Data(data=result.dict())
                self.status = result
                return result
            except Exception as e:
                error = f"An Exception happened while calling LeMUR: {str(e)}"
                self.status = error
                return Data(data={"error": error})
        else:
            self.status = transcript.error
            return Data(data={"error": transcript.error})

    def get_final_model(self, model_name: str) -> aai.LemurModel:
        if model_name == "claude3_5_sonnet":
            return aai.LemurModel.claude3_5_sonnet
        elif model_name == "claude3_opus":
            return aai.LemurModel.claude3_opus
        elif model_name == "claude3_haiku":
            return aai.LemurModel.claude3_haiku
        elif model_name == "claude3_sonnet":
            return aai.LemurModel.claude3_sonnet
        else:
            raise ValueError(f"Model name not supported: {model_name}")
