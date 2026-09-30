import {
  extractTextFromResult,
  extractThreadId,
  extractToolTraces,
} from "../watsonx-result-parsers";

// ---------------------------------------------------------------------------
// extractTextFromResult
// ---------------------------------------------------------------------------

describe("extractTextFromResult", () => {
  it("returns empty string for null input", () => {
    expect(extractTextFromResult(null)).toBe("");
  });

  it("returns empty string for undefined input", () => {
    expect(extractTextFromResult(undefined)).toBe("");
  });

  it("returns empty string when result has no data", () => {
    expect(extractTextFromResult({})).toBe("");
  });

  it("returns empty string when message has no content array", () => {
    expect(extractTextFromResult({ data: { message: {} } })).toBe("");
  });

  it("returns empty string when content is not an array", () => {
    expect(
      extractTextFromResult({ data: { message: { content: "text" } } }),
    ).toBe("");
  });

  it("extracts text from type='text' content items", () => {
    const result = {
      data: {
        message: {
          content: [{ type: "text", text: "Hello world" }],
        },
      },
    };
    expect(extractTextFromResult(result)).toBe("Hello world");
  });

  it("extracts text from response_type='text' content items", () => {
    const result = {
      data: {
        message: {
          content: [
            { response_type: "text", text: "Hello from response_type" },
          ],
        },
      },
    };
    expect(extractTextFromResult(result)).toBe("Hello from response_type");
  });

  it("joins multiple text items with newlines", () => {
    const result = {
      data: {
        message: {
          content: [
            { type: "text", text: "Line 1" },
            { type: "text", text: "Line 2" },
          ],
        },
      },
    };
    expect(extractTextFromResult(result)).toBe("Line 1\nLine 2");
  });

  it("ignores non-text content items", () => {
    const result = {
      data: {
        message: {
          content: [
            { type: "image", text: "ignored" },
            { type: "text", text: "kept" },
          ],
        },
      },
    };
    expect(extractTextFromResult(result)).toBe("kept");
  });

  it("returns empty string when content array has no text items", () => {
    const result = {
      data: {
        message: {
          content: [{ type: "image" }, { type: "video" }],
        },
      },
    };
    expect(extractTextFromResult(result)).toBe("");
  });

  it("ignores items where text is not a string", () => {
    const result = {
      data: {
        message: {
          content: [
            { type: "text", text: 42 },
            { type: "text", text: "valid" },
          ],
        },
      },
    };
    expect(extractTextFromResult(result)).toBe("valid");
  });
});

// ---------------------------------------------------------------------------
// extractToolTraces
// ---------------------------------------------------------------------------

describe("extractToolTraces", () => {
  it("returns empty array for null input", () => {
    expect(extractToolTraces(null)).toEqual([]);
  });

  it("returns empty array for undefined input", () => {
    expect(extractToolTraces(undefined)).toEqual([]);
  });

  it("returns empty array when result has no data", () => {
    expect(extractToolTraces({})).toEqual([]);
  });

  it("returns empty array when step_history is missing", () => {
    expect(extractToolTraces({ data: { message: {} } })).toEqual([]);
  });

  it("returns empty array when step_history is not an array", () => {
    expect(
      extractToolTraces({ data: { message: { step_history: "invalid" } } }),
    ).toEqual([]);
  });

  it("returns empty array for empty step_history", () => {
    expect(
      extractToolTraces({ data: { message: { step_history: [] } } }),
    ).toEqual([]);
  });

  it("extracts tool trace from new WxO format (tool_calls + tool_response)", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              role: "assistant",
              step_details: [
                {
                  type: "tool_calls",
                  agent_display_name: "MainAgent",
                  tool_calls: [
                    {
                      id: "call-1",
                      name: "search_tool",
                      args: { query: "test" },
                    },
                  ],
                },
                {
                  type: "tool_response",
                  tool_call_id: "call-1",
                  content: "Search results here",
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces).toHaveLength(1);
    expect(traces[0]).toEqual({
      toolName: "search_tool",
      input: { query: "test" },
      output: "Search results here",
      agentName: "MainAgent",
    });
  });

  it("leaves output undefined when tool_call has no matching tool_response", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  type: "tool_calls",
                  tool_calls: [{ id: "call-1", name: "my_tool", args: {} }],
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces).toHaveLength(1);
    expect(traces[0].output).toBeUndefined();
  });

  it("uses 'unknown' as toolName when call has no name", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  type: "tool_calls",
                  tool_calls: [{ id: "call-1", args: {} }], // no name
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces[0].toolName).toBe("unknown");
  });

  it("skips tool_calls entries without an id", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  type: "tool_calls",
                  tool_calls: [{ name: "tool_without_id", args: {} }], // no id
                },
              ],
            },
          ],
        },
      },
    };

    expect(extractToolTraces(result)).toHaveLength(0);
  });

  it("extracts multiple tools from a single step", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  type: "tool_calls",
                  tool_calls: [
                    { id: "c1", name: "tool_a", args: { x: 1 } },
                    { id: "c2", name: "tool_b", args: { y: 2 } },
                  ],
                },
                {
                  type: "tool_response",
                  tool_call_id: "c1",
                  content: "a result",
                },
                {
                  type: "tool_response",
                  tool_call_id: "c2",
                  content: "b result",
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces).toHaveLength(2);
    const traceA = traces.find((t) => t.toolName === "tool_a");
    const traceB = traces.find((t) => t.toolName === "tool_b");
    expect(traceA?.output).toBe("a result");
    expect(traceB?.output).toBe("b result");
  });

  it("extracts traces from legacy format (tool_use + tool_result)", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  tool_use: { name: "legacy_tool", input: { param: "value" } },
                  tool_result: { output: "legacy output" },
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces).toHaveLength(1);
    expect(traces[0]).toMatchObject({
      toolName: "legacy_tool",
      input: { param: "value" },
      output: "legacy output",
    });
  });

  it("handles legacy tool_use without tool_result", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  tool_use: { name: "legacy_tool", input: {} },
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces).toHaveLength(1);
    expect(traces[0].output).toBeUndefined();
  });

  it("ignores step_details with type='tool_call' (echo of original call)", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [{ type: "tool_call", name: "echo_entry" }],
            },
          ],
        },
      },
    };
    expect(extractToolTraces(result)).toHaveLength(0);
  });

  it("handles steps with no step_details", () => {
    const result = {
      data: {
        message: {
          step_history: [{ role: "assistant" }], // no step_details
        },
      },
    };
    expect(extractToolTraces(result)).toEqual([]);
  });

  it("collects traces across multiple steps", () => {
    const result = {
      data: {
        message: {
          step_history: [
            {
              step_details: [
                {
                  type: "tool_calls",
                  tool_calls: [{ id: "c1", name: "tool_a", args: {} }],
                },
                {
                  type: "tool_response",
                  tool_call_id: "c1",
                  content: "result_a",
                },
              ],
            },
            {
              step_details: [
                {
                  type: "tool_calls",
                  tool_calls: [{ id: "c2", name: "tool_b", args: {} }],
                },
                {
                  type: "tool_response",
                  tool_call_id: "c2",
                  content: "result_b",
                },
              ],
            },
          ],
        },
      },
    };

    const traces = extractToolTraces(result);
    expect(traces).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// extractThreadId
// ---------------------------------------------------------------------------

describe("extractThreadId", () => {
  it("returns null for null input", () => {
    expect(extractThreadId(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(extractThreadId(undefined)).toBeNull();
  });

  it("returns null for empty object", () => {
    expect(extractThreadId({})).toBeNull();
  });

  it("extracts thread_id directly from providerData", () => {
    expect(extractThreadId({ thread_id: "tid-1" })).toBe("tid-1");
  });

  it("returns null when top-level thread_id is an empty string", () => {
    expect(extractThreadId({ thread_id: "" })).toBeNull();
  });

  it("returns null when top-level thread_id is not a string", () => {
    expect(extractThreadId({ thread_id: 12345 })).toBeNull();
  });

  it("extracts thread_id from result.data.message.thread_id", () => {
    const providerData = {
      result: {
        data: {
          message: { thread_id: "msg-thread-1" },
        },
      },
    };
    expect(extractThreadId(providerData)).toBe("msg-thread-1");
  });

  it("returns null when message.thread_id is an empty string", () => {
    const providerData = {
      result: { data: { message: { thread_id: "" } } },
    };
    expect(extractThreadId(providerData)).toBeNull();
  });

  it("extracts thread_id from result.data.message.context.wxo_thread_id", () => {
    const providerData = {
      result: {
        data: {
          message: {
            context: { wxo_thread_id: "wxo-tid-1" },
          },
        },
      },
    };
    expect(extractThreadId(providerData)).toBe("wxo-tid-1");
  });

  it("returns null when wxo_thread_id is an empty string", () => {
    const providerData = {
      result: {
        data: {
          message: { context: { wxo_thread_id: "" } },
        },
      },
    };
    expect(extractThreadId(providerData)).toBeNull();
  });

  it("extracts thread_id from result.data.thread_id", () => {
    const providerData = {
      result: {
        data: { thread_id: "data-tid-1" },
      },
    };
    expect(extractThreadId(providerData)).toBe("data-tid-1");
  });

  it("prefers top-level thread_id over nested locations", () => {
    const providerData = {
      thread_id: "top-level",
      result: {
        data: { message: { thread_id: "msg-level" } },
      },
    };
    expect(extractThreadId(providerData)).toBe("top-level");
  });

  it("prefers message.thread_id over context.wxo_thread_id", () => {
    const providerData = {
      result: {
        data: {
          message: {
            thread_id: "msg-level",
            context: { wxo_thread_id: "wxo-level" },
          },
        },
      },
    };
    expect(extractThreadId(providerData)).toBe("msg-level");
  });

  it("prefers context.wxo_thread_id over data.thread_id", () => {
    const providerData = {
      result: {
        data: {
          thread_id: "data-level",
          message: {
            context: { wxo_thread_id: "wxo-level" },
          },
        },
      },
    };
    expect(extractThreadId(providerData)).toBe("wxo-level");
  });

  it("returns null when no thread_id found anywhere", () => {
    expect(
      extractThreadId({ status: "pending", execution_id: "e1" }),
    ).toBeNull();
  });
});
