/**
 * Function to get the python code for the API
 * @param {string} flow - The current flow
 * @param {any[]} tweak - The tweaks
 * @returns {string} - The python code
 */
export default function getPythonCode(
  flowName: string,
  tweaksBuildedObject,
): string {
  const tweaksObject = tweaksBuildedObject[0];

  return `from langflow.load import run_flow_from_json
  TWEAKS = ${JSON.stringify(tweaksObject, null, 2)}

  result = run_flow_from_json(flow="${flowName}.json",
                              input_value="message",
                              fallback_to_env_vars=True, # False by default
                              tweaks=TWEAKS)`;
}
