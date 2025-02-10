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
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 2)
      .replace(/^ {2}/gm, "    ")
      .replace(/}$/, "  }");
  const inputs = useFlowStore.getState().inputs;
  const outputs = useFlowStore.getState().outputs;
  const hasChatInput = inputs.some((input) => input.type === "ChatInput");
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");

  return `# Install the Langflow client
# npm install @datastax/langflow-client

import { LangflowClient } from "@datastax/langflow-client";

const client = new LangflowClient({
  baseUrl: "${window.location.protocol}//${window.location.host}"${isAuth ? ",\n  apiKey: <your api key>" : ""}
})
const flow = client.flow("${endpointName || flowId}");

let inputValue = ""; // Insert input value here

flow.run(inputValue, {
  output_type: ${hasChatOutput ? '"chat"' : '"text"'},
  input_type: ${hasChatInput ? '"chat"' : '"text"'},
  session_id: "user_1",
  tweaks: ${tweaksString}
}).then(response => {
  // get the text of the first chat response
  console.log(response.chatOutputText());
  // Or get all the outputs
  console.log(response.outputs);
}.catch(error => {
  console.error(error);
});`;
}
