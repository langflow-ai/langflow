import os
import httpx
import logging
from typing import Any, Dict, List
from langflow.custom import Component
from langflow.io import (
    DropdownInput,
    MessageTextInput,
    IntInput,
    Output,
    SecretStrInput,
    FloatInput,
    BoolInput,
    NestedDictInput
)
from langflow.schema import Data
from langflow.schema.dotdict import dotdict
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LangWatchComponent(Component):
    display_name: str = "Langwatch Evaluator"
    description: str = "Evaluates various aspects of language models using Langwatch's evaluation endpoints."
    documentation: str = "https://docs.langwatch.ai/langevals/documentation/introduction"
    icon: str = "Langwatch"
    name: str = "LangwatchEvaluator"

    inputs = [
        DropdownInput(
            name="evaluator_name",
            display_name="Evaluator Name",
            options=[],
            required=True,
            info="Select an evaluator.",
            refresh_button=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            info="Enter your Langwatch API key.",
        ),
        MessageTextInput(
            name="input",
            display_name="Input",
            required=False,
            info="The input text for evaluation.",
        ),
        MessageTextInput(
            name="output",
            display_name="Output",
            required=False,
            info="The output text for evaluation.",
        ),
        MessageTextInput(
            name="expected_output",
            display_name="Expected Output",
            required=False,
            info="The expected output for evaluation.",
        ),
        MessageTextInput(
            name="contexts",
            display_name="Contexts",
            required=False,
            info="The contexts for evaluation (comma-separated).",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The maximum time (in seconds) allowed for the server to respond before timing out.",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="evaluation_result", display_name="Evaluation Result", method="evaluate"),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.evaluators = self.get_evaluators()
        self.dynamic_inputs = {}
        self._code = data.get('_code', '')
        self.current_evaluator = None
        if self.evaluators:
            self.current_evaluator = list(self.evaluators.keys())[0]

    def get_evaluators(self) -> Dict[str, Any]:
        url = f"{os.getenv('LANGWATCH_ENDPOINT', 'https://app.langwatch.ai')}/api/evaluations/list"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('evaluators', {})
        except httpx.RequestError as e:
            logger.error(f"Error fetching evaluators: {e}")
            self.status = f"Error fetching evaluators: {e}"
            return {}

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        try:
            logger.info(f"Updating build config. Field name: {field_name}, Field value: {field_value}")
            
            if field_name is None or field_name == "evaluator_name":
                self.evaluators = self.get_evaluators()
                build_config["evaluator_name"]["options"] = list(self.evaluators.keys())

                # Set a default evaluator if none is selected
                if not self.current_evaluator and self.evaluators:
                    self.current_evaluator = list(self.evaluators.keys())[0]
                    build_config["evaluator_name"]["value"] = self.current_evaluator

                # Definir as chaves padrão que devem estar sempre presentes
                default_keys = [
                    "code",
                    "_type",
                    "evaluator_name",
                    "api_key",
                    "input",
                    "output",
                    "timeout"
                ]

                if field_value and field_value in self.evaluators:
                    if self.current_evaluator != field_value:
                        self.current_evaluator = field_value
                        evaluator = self.evaluators[field_value]
                        
                        # Limpar inputs dinâmicos anteriores
                        keys_to_remove = [key for key in build_config.keys() 
                                       if key not in default_keys]
                        for key in keys_to_remove:
                            del build_config[key]
                        
                        # Limpar atributos dinâmicos do componente
                        for attr in list(self.__dict__.keys()):
                            if (attr not in default_keys and 
                                attr not in ['evaluators', 'dynamic_inputs', '_code', 'current_evaluator']):
                                delattr(self, attr)
                        
                        # Adicionar novos inputs dinâmicos
                        self.dynamic_inputs = self.get_dynamic_inputs(evaluator)
                        for name, input_config in self.dynamic_inputs.items():
                            build_config[name] = input_config.to_dict()
                        
                        # Atualizar campos obrigatórios
                        required_fields = {"api_key", "evaluator_name"}.union(evaluator.get('requiredFields', []))
                        for key in build_config:
                            if isinstance(build_config[key], dict):
                                build_config[key]['required'] = key in required_fields
                
                # Validar presença das chaves padrão
                missing_keys = [key for key in default_keys if key not in build_config]
                if missing_keys:
                    logger.warning(f"Missing required keys in build_config: {missing_keys}")
                    # Adicionar chaves faltantes com valores padrão
                    for key in missing_keys:
                        build_config[key] = {"value": None, "type": "str"}
            
            # Ensure the current_evaluator is always set in the build_config
            build_config["evaluator_name"]["value"] = self.current_evaluator

            logger.info(f"Current evaluator set to: {self.current_evaluator}")
            return build_config
            
        except Exception as e:
            logger.error(f"Error updating component: {str(e)}")
            self.status = f"Error updating component: {str(e)}"
            return build_config

    def get_dynamic_inputs(self, evaluator: Dict[str, Any]):
        try:
            settings = evaluator.get('settings', {})
            dynamic_inputs = {}
            
            for setting_name, setting_config in settings.items():
                schema = evaluator.get('settings_json_schema', {}).get('properties', {}).get(setting_name, {})
                
                input_params = {
                    "name": setting_name,
                    "display_name": setting_name.replace('_', ' ').title(),
                    "info": setting_config.get('description', ''),
                    "required": False
                }
                
                if schema.get('type') == 'object':
                    input_type = NestedDictInput
                    input_params["value"] = schema.get('default', setting_config.get('default', {}))
                elif schema.get('type') == 'boolean':
                    input_type = BoolInput
                    input_params["value"] = schema.get('default', setting_config.get('default', False))
                elif schema.get('type') == 'number':
                    is_float = isinstance(schema.get('default', setting_config.get('default')), float)
                    input_type = FloatInput if is_float else IntInput
                    input_params["value"] = schema.get('default', setting_config.get('default', 0))
                elif 'enum' in schema:
                    input_type = DropdownInput
                    input_params["options"] = schema['enum']
                    input_params["value"] = schema.get('default', setting_config.get('default'))
                else:
                    input_type = MessageTextInput
                    default_value = schema.get('default', setting_config.get('default'))
                    input_params["value"] = str(default_value) if default_value is not None else ''
                
                dynamic_inputs[setting_name] = input_type(**input_params)
            
            return dynamic_inputs
            
        except Exception as e:
            logger.error(f"Error creating dynamic inputs: {str(e)}")
            self.status = f"Error creating dynamic inputs: {str(e)}"
            return {}

    async def evaluate(self) -> Data:
        if not self.api_key:
            return Data(data={"error": "API key is required"})

        # Prioritize evaluator_name if it exists
        evaluator_name = getattr(self, 'evaluator_name', None) or self.current_evaluator

        if not evaluator_name:
            if self.evaluators:
                evaluator_name = list(self.evaluators.keys())[0]
                logger.info(f"No evaluator was selected. Using default: {evaluator_name}")
            else:
                return Data(data={"error": "No evaluator selected and no evaluators available. Please choose an evaluator."})

        try:
            evaluator = self.evaluators.get(evaluator_name)
            if not evaluator:
                return Data(data={"error": f"Selected evaluator '{evaluator_name}' not found."})

            logger.info(f"Evaluating with evaluator: {evaluator_name}")

            endpoint = f"/api/evaluations/{evaluator_name}/evaluate"
            url = f"{os.getenv('LANGWATCH_ENDPOINT', 'https://app.langwatch.ai')}{endpoint}"

            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": self.api_key
            }

            payload = {
                "data": {
                    "input": self.input,
                    "output": self.output,
                    "expected_output": self.expected_output,
                    "contexts": self.contexts.split(',') if self.contexts else []
                },
                "settings": {}
            }

            if self._tracing_service and self._tracing_service._tracers and "langwatch" in self._tracing_service._tracers:
                payload["trace_id"] = str(self._tracing_service._tracers["langwatch"].trace_id)

            for setting_name in self.dynamic_inputs.keys():
                payload["settings"][setting_name] = getattr(self, setting_name, None)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                
            response.raise_for_status()
            result = response.json()
            
            formatted_result = json.dumps(result, indent=2)
            self.status = f"Evaluation completed successfully. Result:\n{formatted_result}"
            return Data(data=result)

        except Exception as e:
            error_message = f"Evaluation error: {str(e)}"
            logger.error(error_message)
            self.status = error_message
            return Data(data={"error": error_message})

    async def build(self) -> Dict[str, Any]:
        return {
            "evaluation_result": await self.evaluate()
        }