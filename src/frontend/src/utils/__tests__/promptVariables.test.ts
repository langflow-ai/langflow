import {
  isReservedVariableName,
  variableHighlightClass,
} from "../promptVariables";

// Same case list as test_validate_prompt_reserved_prefix.py in the backend; keep the two
// in sync so the editor never marks a name the API would accept, or vice versa.
const REJECTED = ["_x", "_", "__y", "_type", "_frontend_node_flow_id"];
const ACCEPTED = ["var", "a_b", "var_1", "private_", "x"];

describe("isReservedVariableName", () => {
  it.each(REJECTED)("treats %s as reserved", (name) => {
    expect(isReservedVariableName(name)).toBe(true);
  });

  it.each(ACCEPTED)("leaves %s alone", (name) => {
    expect(isReservedVariableName(name)).toBe(false);
  });

  it("does not flag an underscore that is not the first character", () => {
    expect(isReservedVariableName("user_name")).toBe(false);
  });

  it("does not flag an empty name", () => {
    expect(isReservedVariableName("")).toBe(false);
  });
});

describe("variableHighlightClass", () => {
  it("returns the invalid class for a reserved name", () => {
    expect(variableHighlightClass("_x")).toBe("chat-message-highlight-invalid");
  });

  it("returns the regular class for an accepted name", () => {
    expect(variableHighlightClass("var")).toBe("chat-message-highlight");
  });
});
