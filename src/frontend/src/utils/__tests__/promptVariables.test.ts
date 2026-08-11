import {
  invalidVariableMessageKey,
  invalidVariableReason,
  promptVariableFieldName,
  variableHighlightClass,
} from "../promptVariables";

// Same case list as test_validate_prompt_reserved_prefix.py in the backend; keep the two
// in sync so the editor never marks a name the API would accept, or vice versa. Each
// entry is [name typed between braces, reason Check & Save would report].
const REJECTED: [string, string][] = [
  ["_x", "reservedPrefix"],
  ["_", "reservedPrefix"],
  ["__y", "reservedPrefix"],
  ["_type", "reservedPrefix"],
  ["_frontend_node_flow_id", "reservedPrefix"],
  ["1var", "leadingDigit"],
  ["9", "leadingDigit"],
  ["my var", "invalidCharacter"],
  [" x ", "invalidCharacter"],
  ["a.b", "invalidCharacter"],
  ["a(b)", "invalidCharacter"],
  ["a/b", "invalidCharacter"],
  ["a[0]", "invalidCharacter"],
  ["code", "reservedName"],
  ["template", "reservedName"],
  ["input_variables", "reservedName"],
  ["output_parser", "reservedName"],
  ["partial_variables", "reservedName"],
  ["template_format", "reservedName"],
  ["validate_template", "reservedName"],
];

const ACCEPTED = [
  "var",
  "a_b",
  "var_1",
  "private_",
  "x",
  "a-b",
  "a@b",
  "codes",
  "my_code",
  // Python's Formatter ends the field name at `!` or `:`, so these are the variable `x`
  // and the JSON literal `{"a": 1}`, all three of which the backend accepts.
  "x:>10",
  "x!r",
  '"a": 1',
];

describe("promptVariableFieldName", () => {
  it.each([
    ["x:>10", "x"],
    ["x!r", "x"],
    ["x!s:>10", "x"],
    ['"a": 1', '"a"'],
    ["var", "var"],
  ])("reads %s as the field %s", (raw, field) => {
    expect(promptVariableFieldName(raw)).toBe(field);
  });
});

describe("invalidVariableReason", () => {
  it.each(REJECTED)("rejects %s as %s", (name, reason) => {
    expect(invalidVariableReason(name)).toBe(reason);
  });

  it.each(ACCEPTED)("accepts %s", (name) => {
    expect(invalidVariableReason(name)).toBeNull();
  });

  it("does not flag an underscore that is not the first character", () => {
    expect(invalidVariableReason("user_name")).toBeNull();
  });

  it("does not flag an empty name", () => {
    expect(invalidVariableReason("")).toBeNull();
  });

  it("does not flag a line break, which the backend accepts", () => {
    expect(invalidVariableReason("a\nb")).toBeNull();
  });

  it("reports the reason the backend checks first", () => {
    // `_check_input_variables` runs before `_check_reserved_prefix`, so a name that
    // breaks both is reported as the character problem.
    expect(invalidVariableReason("_my var")).toBe("invalidCharacter");
  });
});

describe("invalidVariableMessageKey", () => {
  it.each([
    ["1var", "modal.prompt.invalidVariable.leadingDigit"],
    ["my var", "modal.prompt.invalidVariable.invalidCharacter"],
    ["_x", "modal.prompt.invalidVariable.reservedPrefix"],
    ["code", "modal.prompt.invalidVariable.reservedName"],
  ])("maps %s to %s", (name, key) => {
    expect(invalidVariableMessageKey(name)).toBe(key);
  });

  it("returns null for an accepted name", () => {
    expect(invalidVariableMessageKey("var")).toBeNull();
  });
});

describe("variableHighlightClass", () => {
  it.each(REJECTED.map(([name]) => name))(
    "returns the invalid class for %s",
    (name) => {
      expect(variableHighlightClass(name)).toBe(
        "chat-message-highlight-invalid",
      );
    },
  );

  it.each(ACCEPTED)("returns the regular class for %s", (name) => {
    expect(variableHighlightClass(name)).toBe("chat-message-highlight");
  });
});
