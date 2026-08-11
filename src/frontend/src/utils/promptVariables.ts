/**
 * Prompt variable naming rules shared by every place that highlights or lists them.
 *
 * Mirror of the four rejection paths of `validate_prompt`
 * (`src/lfx/src/lfx/base/prompts/api_utils.py`), in the order the backend applies them:
 *
 *   1. leading digit      `_fix_variable`           `{1var}`
 *   2. invalid character  `_INVALID_CHARACTERS`     `{my var}`
 *   3. reserved prefix    `_check_reserved_prefix`  `{_x}`
 *   4. reserved name      `_INVALID_NAMES`          `{code}`
 *
 * The order matters: the reason picks the message the editor shows, and it has to be the
 * one Check & Save would report for the same name.
 *
 * All four are rejected on Check & Save; these helpers let the editor say so while the
 * user is still typing. The case list is mirrored by
 * `test_validate_prompt_reserved_prefix.py`; keep the two in sync when a rule changes.
 */

/** Mirror of `RESERVED_VARIABLE_PREFIX`: the `_*` node-template metadata namespace. */
export const RESERVED_VARIABLE_PREFIX = "_";

/** Mirror of `_INVALID_NAMES`: names that collide with node-template keys. */
export const RESERVED_VARIABLE_NAMES = [
  "code",
  "input_variables",
  "output_parser",
  "partial_variables",
  "template",
  "template_format",
  "validate_template",
];

/**
 * Mirror of `_INVALID_CHARACTERS`.
 *
 * Deliberately not `INVALID_CHARACTERS` from `constants.ts`: that list also carries `\n`,
 * which the backend accepts, and a variable spanning a line break is how a multi-line
 * JSON literal reaches this code. `:` and `!` can never survive `promptVariableFieldName`
 * below; they are kept so the list still reads as the backend's.
 */
const INVALID_VARIABLE_CHARACTERS = [
  " ",
  ",",
  ".",
  ":",
  ";",
  "!",
  "?",
  "/",
  "\\",
  "(",
  ")",
  "[",
  "]",
];

export type InvalidVariableReason =
  | "leadingDigit"
  | "invalidCharacter"
  | "reservedPrefix"
  | "reservedName";

const INVALID_VARIABLE_MESSAGE_KEYS: Record<InvalidVariableReason, string> = {
  leadingDigit: "modal.prompt.invalidVariable.leadingDigit",
  invalidCharacter: "modal.prompt.invalidVariable.invalidCharacter",
  reservedPrefix: "modal.prompt.invalidVariable.reservedPrefix",
  reservedName: "modal.prompt.invalidVariable.reservedName",
};

/**
 * The name the backend will actually validate.
 *
 * f-string extraction runs through Python's `string.Formatter`, which ends the field name
 * at the first `!` (conversion) or `:` (format spec). So `{x:>10}` is the variable `x`,
 * and `{"a": 1}` -- a JSON literal, not a variable -- is the field `"a"`, which the
 * backend accepts. Reading the raw text instead would flag both as invalid.
 *
 * Mustache names never reach here with either character: the editor only recognizes
 * `[a-zA-Z_][a-zA-Z0-9_]*` inside `{{ }}`.
 */
export function promptVariableFieldName(rawName: string): string {
  const cut = rawName.search(/[!:]/);
  return cut === -1 ? rawName : rawName.slice(0, cut);
}

/** Why Check & Save would reject this name, or `null` if it would accept it. */
export function invalidVariableReason(
  rawName: string,
): InvalidVariableReason | null {
  const name = promptVariableFieldName(rawName);
  // An empty field name is a formatting artifact, not a variable the user typed.
  if (name === "") return null;
  if (/^[0-9]/.test(name)) return "leadingDigit";
  if (INVALID_VARIABLE_CHARACTERS.some((char) => name.includes(char))) {
    return "invalidCharacter";
  }
  if (name.startsWith(RESERVED_VARIABLE_PREFIX)) return "reservedPrefix";
  if (RESERVED_VARIABLE_NAMES.includes(name)) return "reservedName";
  return null;
}

/** Translation key explaining the rejection, or `null` when the name is valid. */
export function invalidVariableMessageKey(rawName: string): string | null {
  const reason = invalidVariableReason(rawName);
  return reason === null ? null : INVALID_VARIABLE_MESSAGE_KEYS[reason];
}

/** Class applied to a highlighted variable, red when the name will be rejected. */
export function variableHighlightClass(rawName: string): string {
  return invalidVariableReason(rawName) === null
    ? "chat-message-highlight"
    : "chat-message-highlight-invalid";
}
