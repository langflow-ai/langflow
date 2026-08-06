import type { IVarHighlightType } from "../../../types/components";
import { variableHighlightClass } from "../../../utils/promptVariables";

export default function varHighlightHTML({
  name,
  addCurlyBraces,
  variableName,
  invalidTitle,
}: IVarHighlightType): string {
  // `name` is the text to render; `variableName` is the bare identifier the rule reads.
  // The two differ in mustache, where the rendered text carries its own braces.
  const className = variableHighlightClass(variableName ?? name);
  const isInvalid = className === "chat-message-highlight-invalid";
  // Only ever set from a translated constant, never from user input, so a quote inside a
  // variable name cannot break out of the attribute.
  const title = isInvalid && invalidTitle ? ` title="${invalidTitle}"` : "";
  const text = addCurlyBraces ? `{${name}}` : name;

  return `<span class="font-semibold ${className}"${title}>${text}</span>`;
}
