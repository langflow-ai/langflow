# from typing import Dict, List

# import dspy

# from langflow import CustomComponent
# from langflow.field_typing import Text


# class ReActAgentComponent(CustomComponent):
#     display_name = "ReAct Agent"
#     description = "A component to create a ReAct Agent."
#     icon = "user-secret"

#     def build_config(self):
#         return {
#             "input_value": {
#                 "display_name": "Input",
#                 "input_types": ["Text"],
#                 "info": "The input value for the ReAct Agent.",
#             },
#             "instructions": {
#                 "display_name": "Instructions",
#                 "info": "The Prompt.",
#             },
#             "inputs": {
#                 "display_name": "Inputs",
#                 "info": "The Name and Description of the Input Fields.",
#             },
#             "outputs": {
#                 "display_name": "Outputs",
#                 "info": "The Name and Description of the Output Fields.",
#             },
#         }

#     def build(
#         self,
#         input_value: List[dict],
#         instructions: Text,
#         inputs: List[dict],
#         outputs: List[Dict],
#     ) -> Text:
#         # inputs is a list of dictionaries where the key is the name of the input
#         # and the value is the description of the input
#         input_fields = (
#             {}
#         )  # dict[str, FieldInfo] InputField and OutputField are subclasses of pydantic.Field
#         for input_dict in inputs:
#             for name, description in input_dict.items():
#                 prefix = name if ":" in name else f"{name}:"
#                 input_fields[name] = dspy.InputField(
#                     prefix=prefix, description=description
#                 )

#         output_fields = {}  # dict[str, FieldInfo]
#         for output_dict in outputs:
#             for name, description in output_dict.items():
#                 prefix = name if ":" in name else f"{name}:"
#                 output_fields[name] = dspy.OutputField(
#                     prefix=prefix, description=description
#                 )

#         signature = dspy.make_signature(inputs, instructions=instructions)
#         agent = dspy.ReAct(
#             signature=signature,
#         )
#         inputs_dict = {}
#         for input_dict in input_value:
#             inputs_dict.update(input_dict)

#         result = agent(inputs_dict)
