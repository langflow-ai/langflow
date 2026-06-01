import type { JSONValue } from "@/types/chat";
import { looksPreformatted, unwrapToolMessage } from "../toolOutput";

describe("unwrapToolMessage", () => {
  it("unwraps a canonical LangChain ToolMessage shape down to its .content", () => {
    const out = unwrapToolMessage({
      content: "the body",
      name: "fetch",
      id: "abc",
      tool_call_id: "toolu_x",
      status: "success",
    });
    expect(out).toBe("the body");
  });

  it("leaves the envelope intact when extra fields are present", () => {
    // The producer might be carrying tool-specific data; silently
    // dropping it would lose information.
    const envelope = { content: "the body", custom_field: 42 } as JSONValue;
    expect(unwrapToolMessage(envelope)).toEqual(envelope);
  });

  it("leaves arrays untouched", () => {
    const arr = [1, 2, 3] as JSONValue;
    expect(unwrapToolMessage(arr)).toBe(arr);
  });

  it("leaves objects without a content key untouched", () => {
    const obj = { result: 42, count: 7 } as JSONValue;
    expect(unwrapToolMessage(obj)).toBe(obj);
  });

  it("leaves primitives untouched", () => {
    expect(unwrapToolMessage("hello")).toBe("hello");
    expect(unwrapToolMessage(42)).toBe(42);
    expect(unwrapToolMessage(null)).toBe(null);
  });
});

describe("looksPreformatted", () => {
  it("flags pandas-style column-padded output", () => {
    // The actual pandas df.to_string() output that broke the playground:
    // dozens of consecutive spaces between column values.
    const s =
      "                                                text                   url\n" +
      "0  Langflow | Low-code AI builder for agentic and...  https://langflow.org";
    expect(looksPreformatted(s)).toBe(true);
  });

  it("flags strings containing tabs", () => {
    expect(looksPreformatted("col1\tcol2\tcol3")).toBe(true);
  });

  it("flags strings with very long single lines", () => {
    // A 130-char single line is almost certainly a log entry or wide
    // payload that markdown would mangle.
    expect(looksPreformatted("x".repeat(130))).toBe(true);
  });

  it("leaves ordinary prose alone", () => {
    expect(
      looksPreformatted(
        "Langflow.org is up — it's described as a Low-code AI builder.",
      ),
    ).toBe(false);
  });

  it("leaves short markdown alone", () => {
    expect(looksPreformatted("**Result:** the answer is 42")).toBe(false);
  });

  it("ignores leading-indent CommonMark code blocks", () => {
    // 4-space-indented lines are a CommonMark indented code block. The old
    // `/ {4,}/` heuristic tripped on the leading run and forced the whole
    // output into a monospace block; markdown should still render here.
    const s =
      "Here is the code:\n\n    const x = 1;\n    const y = 2;\n\nDone.";
    expect(looksPreformatted(s)).toBe(false);
  });

  it("still flags interior column padding (table alignment)", () => {
    // 4+ spaces AFTER content on a line is genuine column alignment that
    // markdown would mangle.
    expect(looksPreformatted("name    value\nfoo     42")).toBe(true);
  });
});
