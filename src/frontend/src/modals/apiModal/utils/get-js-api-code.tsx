import useFlowStore from "@/stores/flowStore";
import { GetCodeType } from "@/types/tweaks";

/**
 * Function to generate JavaScript code for interfacing with an API using the LangflowClient class.
 * @param {string} flowId - The id of the flow.
 * @param {boolean} isAuth - Whether the API requires authentication.
 * @param {any[]} tweaksBuildedObject - Customizations applied to the flow.
 * @param {string} [endpointName] - Optional endpoint name.
 * @returns {string} - The JavaScript code as a string.
 */
export default function getJsApiCode({
  flowId,
  isAuth,
  tweaksBuildedObject,
  endpointName,
  activeTweaks,
}: GetCodeType): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject)
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 8);
  const inputs = useFlowStore.getState().inputs;
  const outputs = useFlowStore.getState().outputs;
  const hasChatInput = inputs.some((input) => input.type === "ChatInput");
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");

  return `${activeTweaks ? "" : 'let inputValue = ""; // Insert input value here\n\n'}fetch(
  "${window.location.protocol}//${window.location.host}/api/v1/run/${endpointName || flowId}?stream=false",
  {
    method: "POST",
    headers: {
      "Authorization": "Bearer <TOKEN>",
      "Content-Type": "application/json",${isAuth ? '\n\t\t\t"x-api-key": <your api key>' : ""}
    },
    body: JSON.stringify({${activeTweaks ? "" : "\n\t\t\tinput_value: inputValue, "}
      output_type: ${hasChatOutput ? '"chat"' : '"text"'},
      input_type: ${hasChatInput ? '"chat"' : '"text"'},
      tweaks: ${tweaksString}
    }),
  },
)
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));
`;
}
