import type { JSONValue } from "@/types/chat";
import {
  isToolMessageEnvelope,
  looksPreformatted,
  unwrapToolMessage,
} from "../toolOutput";

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

describe("isToolMessageEnvelope", () => {
  it("recognises an envelope carrying non-standard metadata", () => {
    // The shape ToolOutputDisplay surfaces under a Metadata tab: a
    // LangChain ToolMessage with the full plumbing (additional_kwargs,
    // response_metadata, type, artifact) that the user might want to
    // inspect.
    expect(
      isToolMessageEnvelope({
        content: "Current date: 2026-05-28",
        additional_kwargs: {},
        response_metadata: {},
        type: "tool",
        name: "get_current_date",
        id: "x",
        tool_call_id: "toolu_y",
        artifact: null,
        status: "success",
      }),
    ).toBe(true);
  });

  it("does not recognise outputs whose keys are only standard plumbing", () => {
    // {content, name, id, tool_call_id, status} — no metadata worth
    // hiding behind a tab. unwrapToolMessage handles this directly.
    expect(
      isToolMessageEnvelope({
        content: "the body",
        name: "fetch",
        id: "abc",
        tool_call_id: "toolu_x",
        status: "success",
      }),
    ).toBe(false);
  });

  it("rejects objects without a content key", () => {
    expect(isToolMessageEnvelope({ result: "12" })).toBe(false);
  });

  it("rejects arrays, primitives, and null", () => {
    expect(isToolMessageEnvelope([1, 2, 3] as JSONValue)).toBe(false);
    expect(isToolMessageEnvelope("hi")).toBe(false);
    expect(isToolMessageEnvelope(42)).toBe(false);
    expect(isToolMessageEnvelope(null)).toBe(false);
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
