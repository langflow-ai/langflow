import type { IVarHighlightType } from "../../../types/components";
import { variableHighlightClass } from "../../../utils/promptVariables";

/**
 * Escapes a value interpolated into a double-quoted HTML attribute.
 *
 * The tooltip text is a translated sentence, and several locales quote the prefix with a
 * plain `"` (en, pt, es). Interpolated raw, that quote closes the attribute early: the
 * browser reads only the text before it and turns the rest of the sentence into stray
 * attributes.
 */
function escapeAttributeValue(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

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
  const title =
    isInvalid && invalidTitle
      ? ` title="${escapeAttributeValue(invalidTitle)}"`
      : "";
  const text = addCurlyBraces ? `{${name}}` : name;

  return `<span class="font-semibold ${className}"${title}>${text}</span>`;
}
