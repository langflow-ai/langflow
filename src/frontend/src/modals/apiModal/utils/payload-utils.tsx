/**
 * Utility functions for handling payload generation and tweaks logic
 * across different API code generators (Python, JavaScript, cURL)
 */

/**
 * Collects all keys from tweaks object to avoid duplicates in base payload
 */
export function collectTweaksKeys(
  tweaksObject: any,
  activeTweaks: boolean,
): Set<string> {
  const tweaksKeys = new Set<string>();
  if (tweaksObject && activeTweaks) {
    Object.values(tweaksObject).forEach((component: any) => {
      if (component && typeof component === "object") {
        Object.keys(component).forEach((key) => tweaksKeys.add(key));
      }
    });
  }
  return tweaksKeys;
}

/**
 * Builds base payload excluding keys that exist in tweaks
 */
export function buildBasePayload(
  tweaksKeys: Set<string>,
  input_value: string,
  input_type: string,
  output_type: string,
  includeSessionId = false,
): Record<string, string> {
  const basePayload: Record<string, string> = {};

  if (!tweaksKeys.has("input_value")) {
    basePayload.input_value = input_value;
  }
  if (!tweaksKeys.has("output_type")) {
    basePayload.output_type = output_type;
  }
  if (!tweaksKeys.has("input_type")) {
    basePayload.input_type = input_type;
  }

  // Add session_id for JavaScript if not in tweaks
  if (includeSessionId && !tweaksKeys.has("session_id")) {
    basePayload.session_id = "user_1";
  }

  return basePayload;
}

/**
 * Gets formatted tweaks string for different languages
 */
export function getFormattedTweaksString(
  tweaksObject: any,
  activeTweaks: boolean,
  format: "python" | "javascript" | "json" = "json",
  indent = 2,
): string {
  if (!tweaksObject || !activeTweaks) {
    return "{}";
  }

  let tweaksString = JSON.stringify(tweaksObject, null, indent);

  if (format === "python") {
    tweaksString = tweaksString
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null/g, "None");
  }

  // Add proper indentation to the closing brace
  const indentSpaces = " ".repeat(indent / 2);
  tweaksString = tweaksString.replace(/\n}/g, `\n${indentSpaces}}`);

  return tweaksString;
}
