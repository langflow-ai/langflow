import type { InputFieldType } from "@/types/api";
import {
  isBackendRefusedField,
  isFieldTweakable,
  isTweakableType,
} from "../api-exposure-rules";

const field = (type: string, extra: Partial<InputFieldType> = {}) =>
  ({ type, show: true, ...extra }) as InputFieldType;

describe("isTweakableType", () => {
  it.each(["str", "bool", "int", "float", "dict", "table", "slider"])(
    "accepts %s, whose value is an editable literal",
    (type) => {
      expect(isTweakableType(type)).toBe(true);
    },
  );

  it("accepts model, whose value is a literal even though the node renders a handle", () => {
    expect(isTweakableType("model")).toBe(true);
  });

  it("rejects handle-only inputs, which carry no literal to send", () => {
    expect(isTweakableType("other")).toBe(false);
  });

  it("rejects an unknown or missing type", () => {
    expect(isTweakableType(undefined)).toBe(false);
    expect(isTweakableType("brand-new-widget")).toBe(false);
  });
});

describe("isBackendRefusedField", () => {
  it("refuses any code-typed field, whatever its name", () => {
    expect(
      isBackendRefusedField("PythonFunction", "function_code", "code"),
    ).toBe(true);
    expect(
      isBackendRefusedField("SomeBenignComponent", "snippet", "code"),
    ).toBe(true);
  });

  it("refuses the conventional code field on every component", () => {
    expect(isBackendRefusedField("SomeBenignComponent", "code", "str")).toBe(
      true,
    );
  });

  it("refuses a code-execution input ONLY on a code-execution component", () => {
    expect(
      isBackendRefusedField("PythonREPLComponent", "python_code", "str"),
    ).toBe(true);
    expect(
      isBackendRefusedField("PythonREPLComponent", "global_imports", "str"),
    ).toBe(true);
    expect(
      isBackendRefusedField("CSVAgent", "allow_dangerous_code", "bool"),
    ).toBe(true);
    // Same field name on a component that cannot execute code stays tweakable.
    expect(
      isBackendRefusedField("SomeBenignComponent", "python_code", "str"),
    ).toBe(false);
  });

  it("refuses a protected sink ONLY on the component that owns it", () => {
    expect(isBackendRefusedField("SQLComponent", "database_url", "str")).toBe(
      true,
    );
    expect(isBackendRefusedField("SQLComponent", "query", "str")).toBe(true);
    // `query` is a common field name; only SQLComponent's is a protected sink.
    expect(isBackendRefusedField("NewsSearch", "query", "str")).toBe(false);
  });

  it("leaves the other inputs of a code-execution component alone", () => {
    expect(
      isBackendRefusedField("PythonREPLComponent", "input_value", "str"),
    ).toBe(false);
  });
});

describe("isFieldTweakable", () => {
  it("accepts a plain literal input on an ordinary component", () => {
    expect(isFieldTweakable("Agent", "system_prompt", field("str"))).toBe(true);
  });

  it("accepts the Language Model selector — the case the snippet used to drop", () => {
    expect(isFieldTweakable("Agent", "model", field("model"))).toBe(true);
  });

  it("rejects a handle-only input", () => {
    expect(isFieldTweakable("Agent", "tools", field("other"))).toBe(false);
  });

  it("rejects internal fields", () => {
    expect(isFieldTweakable("Agent", "_internal", field("str"))).toBe(false);
  });

  it("rejects what the backend would refuse", () => {
    expect(isFieldTweakable("SQLComponent", "database_url", field("str"))).toBe(
      false,
    );
    expect(
      isFieldTweakable("PythonREPLComponent", "python_code", field("str")),
    ).toBe(false);
    expect(
      isFieldTweakable("PythonFunction", "function_code", field("code")),
    ).toBe(false);
  });

  it("rejects a missing template", () => {
    expect(isFieldTweakable("Agent", "model", undefined)).toBe(false);
  });
});
