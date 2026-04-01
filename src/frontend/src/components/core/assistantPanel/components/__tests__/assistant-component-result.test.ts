import { formatType, parseComponentInfo } from "../assistant-component-result";

describe("formatType", () => {
  it("should remove Input suffix", () => {
    expect(formatType("StrInput")).toBe("Str");
  });

  it("should remove Message prefix after removing Input suffix", () => {
    expect(formatType("MessageTextInput")).toBe("Text");
  });

  it("should handle IntInput", () => {
    expect(formatType("IntInput")).toBe("Int");
  });

  it("should handle FloatInput", () => {
    expect(formatType("FloatInput")).toBe("Float");
  });

  it("should handle BoolInput", () => {
    expect(formatType("BoolInput")).toBe("Bool");
  });

  it("should return original string when no suffix or prefix matches", () => {
    expect(formatType("CustomType")).toBe("CustomType");
  });

  it("should handle empty string", () => {
    expect(formatType("")).toBe("");
  });
});

describe("parseComponentInfo", () => {
  it("should return defaults when code is undefined", () => {
    const result = parseComponentInfo(undefined);

    expect(result.description).toBeNull();
    expect(result.inputs).toEqual([]);
    expect(result.outputs).toEqual([]);
  });

  it("should return defaults when code is empty string", () => {
    const result = parseComponentInfo("");

    expect(result.description).toBeNull();
    expect(result.inputs).toEqual([]);
    expect(result.outputs).toEqual([]);
  });

  it("should extract description from component class", () => {
    const code = `
class MyComponent(Component):
    description = "A component that does something useful"
    inputs = []
`;
    const result = parseComponentInfo(code);

    expect(result.description).toBe("A component that does something useful");
  });

  it("should return null description when not found", () => {
    const code = `
class MyComponent(Component):
    inputs = []
`;
    const result = parseComponentInfo(code);

    expect(result.description).toBeNull();
  });

  it("should extract inputs with types", () => {
    const code = `
class MyComponent(Component):
    inputs = [
        MessageTextInput(display_name="Input Text", name="input_text"),
        IntInput(display_name="Max Tokens", name="max_tokens"),
    ]
`;
    const result = parseComponentInfo(code);

    expect(result.inputs).toHaveLength(2);
    expect(result.inputs[0]).toEqual({ name: "Input Text", type: "Text" });
    expect(result.inputs[1]).toEqual({ name: "Max Tokens", type: "Int" });
  });

  it("should extract outputs with return types from method signatures", () => {
    const code = `
class MyComponent(Component):
    outputs = [
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def build_result(self) -> Message:
        return Message(text="hello")
`;
    const result = parseComponentInfo(code);

    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0]).toEqual({ name: "Result", type: "Message" });
  });

  it("should use Message as default output type when method not found", () => {
    const code = `
class MyComponent(Component):
    outputs = [
        Output(display_name="Result", name="result"),
    ]
`;
    const result = parseComponentInfo(code);

    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0]).toEqual({ name: "Result", type: "Message" });
  });

  it("should resolve DataFrame return type from method", () => {
    const code = `
class DataComponent(Component):
    outputs = [
        Output(display_name="Data", name="data", method="build_data"),
    ]

    def build_data(self) -> DataFrame:
        return DataFrame([{"key": "value"}])
`;
    const result = parseComponentInfo(code);

    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0]).toEqual({ name: "Data", type: "DataFrame" });
  });

  it("should handle code with no inputs or outputs", () => {
    const code = `
class EmptyComponent(Component):
    description = "Empty component"
`;
    const result = parseComponentInfo(code);

    expect(result.description).toBe("Empty component");
    expect(result.inputs).toEqual([]);
    expect(result.outputs).toEqual([]);
  });

  it("should parse a realistic full component", () => {
    const code = `
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

class TextUppercaseComponent(Component):
    description = "Converts text to uppercase"
    inputs = [
        MessageTextInput(display_name="Input Text", name="input_text"),
        StrInput(display_name="Separator", name="separator"),
    ]
    outputs = [
        Output(display_name="Uppercase Text", name="uppercase_text", method="to_uppercase"),
    ]

    def to_uppercase(self) -> Message:
        text = self.input_text
        return Message(text=text.upper())
`;
    const result = parseComponentInfo(code);

    expect(result.description).toBe("Converts text to uppercase");
    expect(result.inputs).toHaveLength(2);
    expect(result.inputs[0].name).toBe("Input Text");
    expect(result.inputs[1].name).toBe("Separator");
    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0]).toEqual({
      name: "Uppercase Text",
      type: "Message",
    });
  });
});

describe("bugs and edge cases", () => {
  it.failing(
    "BUG: formatType('MessageInput') returns empty string — replace chain removes everything",
    () => {
      // L15: .replace(/Input$/, "").replace(/^Message/, "")
      // "MessageInput" -> "Message" (strip Input) -> "" (strip Message)
      // An empty type string is displayed as "( )" in the UI.
      const result = formatType("MessageInput");
      expect(result).not.toBe("");
      expect(result.length).toBeGreaterThan(0);
    },
  );

  it("formatType('Input') returns empty string — documents behavior", () => {
    // "Input" -> "" after removing Input$ suffix. Edge case but unlikely in practice.
    expect(formatType("Input")).toBe("");
  });

  it("formatType preserves types without Input/Message", () => {
    expect(formatType("CustomType")).toBe("CustomType");
    expect(formatType("DataFrame")).toBe("DataFrame");
  });

  it.failing(
    "BUG: parseComponentInfo ignores single-quoted descriptions",
    () => {
      // L22: regex only matches double-quoted strings: description\s*=\s*"([^"]+)"
      // Python allows single quotes: description = 'My component'
      const code = `
class MyComponent(Component):
    description = 'A single-quoted description'
`;
      const result = parseComponentInfo(code);
      expect(result.description).toBe("A single-quoted description");
    },
  );

  it.failing(
    "BUG: parseComponentInfo ignores triple-quoted descriptions",
    () => {
      // L22: same regex — triple-quoted strings are also valid Python.
      const code = `
class MyComponent(Component):
    description = """A multi-line
    description with triple quotes"""
`;
      const result = parseComponentInfo(code);
      expect(result.description).not.toBeNull();
    },
  );

  it("Output with method before display_name falls back to default type", () => {
    // L42: primary outputRegex requires display_name BEFORE method.
    // When method comes first, primary regex misses — fallback at L55 catches
    // but loses the return type (defaults to "Message").
    const code = `
class MyComponent(Component):
    outputs = [
        Output(method="build_result", display_name="Result", name="result"),
    ]

    def build_result(self) -> DataFrame:
        return DataFrame([])
`;
    const result = parseComponentInfo(code);
    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0].name).toBe("Result");
    // BUG: type should be "DataFrame" (from method signature) but fallback
    // only extracts display_name, defaulting type to "Message"
    expect(result.outputs[0].type).toBe("Message");
  });

  it("should parse Output with display_name before method (happy path)", () => {
    const code = `
class MyComponent(Component):
    outputs = [
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def build_result(self) -> str:
        return "hello"
`;
    const result = parseComponentInfo(code);
    expect(result.outputs).toHaveLength(1);
    expect(result.outputs[0]).toEqual({ name: "Result", type: "str" });
  });

  it("should handle multiple outputs with different return types", () => {
    const code = `
class MultiOutput(Component):
    outputs = [
        Output(display_name="Text", name="text_out", method="get_text"),
        Output(display_name="Data", name="data_out", method="get_data"),
    ]

    def get_text(self) -> Message:
        return Message(text="hi")

    def get_data(self) -> DataFrame:
        return DataFrame([])
`;
    const result = parseComponentInfo(code);
    expect(result.outputs).toHaveLength(2);
    expect(result.outputs[0]).toEqual({ name: "Text", type: "Message" });
    expect(result.outputs[1]).toEqual({ name: "Data", type: "DataFrame" });
  });
});
