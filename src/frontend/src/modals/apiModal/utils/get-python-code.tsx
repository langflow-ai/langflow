import { GetCodeType } from "@/types/tweaks";

/**
 * Function to get the python code for the API
 * @param {string} flow - The current flow
 * @param {any[]} tweaksBuildedObject - The tweaks
 * @returns {string} - The python code
 */
export default function getPythonCode({
  flowName,
  tweaksBuildedObject,
  activeTweaks,
}: GetCodeType): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject)
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 2)
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null|undefined/g, "None");

  return `from langflow.load import run_flow_from_json
TWEAKS = ${tweaksString}

result = run_flow_from_json(flow="${flowName}.json",
                            ${!activeTweaks ? `input_value="message",\n                            ` : ""}session_id="", # provide a session id if you want to use session state
                            fallback_to_env_vars=True, # False by default
                            tweaks=TWEAKS)`;
}
