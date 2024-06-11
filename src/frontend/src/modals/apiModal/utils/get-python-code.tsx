/**
 * Function to get the python code for the API
 * @param {string} flow - The current flow
 * @param {any[]} tweaksBuildedObject - The tweaks
 * @returns {string} - The python code
 */
export default function getPythonCode(
  flowName: string,
  tweaksBuildedObject: any[],
): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject && tweaksBuildedObject.length > 0) {
    const tweaksObject = tweaksBuildedObject[0];
    if (!tweaksObject) {
      throw new Error("expected tweaks");
    }
    tweaksString = JSON.stringify(tweaksObject, null, 2)
      .replace(/true/g, "True")
      .replace(/false/g, "False");
  }

  return `from langflow.load import run_flow_from_json
TWEAKS = ${tweaksString}

result = run_flow_from_json(flow="${flowName}.json",
                            input_value="message",
                            fallback_to_env_vars=True, # False by default
                            tweaks=TWEAKS)`;
}
