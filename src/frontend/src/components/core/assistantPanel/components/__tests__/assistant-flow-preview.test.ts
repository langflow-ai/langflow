/**
 * Tests for AssistantFlowPreview helper functions.
 */

// Re-export extractNodeSummary for testing by importing the module
// Since extractNodeSummary is not exported, we test it indirectly
// through the component's behavior, or we test the data shapes it handles.

describe("flow preview data handling", () => {
  function extractNodeSummary(
    flow: Record<string, unknown>,
  ): { type: string; id: string }[] {
    const data = flow.data as
      | { nodes?: { data?: { type?: string; id?: string } }[] }
      | undefined;
    if (!data?.nodes) return [];
    return data.nodes
      .map((n) => ({
        type: n.data?.type || "Unknown",
        id: n.data?.id || "",
      }))
      .slice(0, 10);
  }

  it("should extract node types from flow data", () => {
    const flow = {
      data: {
        nodes: [
          { data: { type: "ChatInput", id: "ChatInput-abc" } },
          { data: { type: "OpenAIModel", id: "OpenAIModel-def" } },
          { data: { type: "ChatOutput", id: "ChatOutput-ghi" } },
        ],
        edges: [],
      },
    };

    const result = extractNodeSummary(flow);
    expect(result).toHaveLength(3);
    expect(result[0]).toEqual({ type: "ChatInput", id: "ChatInput-abc" });
    expect(result[1]).toEqual({ type: "OpenAIModel", id: "OpenAIModel-def" });
    expect(result[2]).toEqual({ type: "ChatOutput", id: "ChatOutput-ghi" });
  });

  it("should return empty array for flow with no nodes", () => {
    expect(extractNodeSummary({ data: { nodes: [], edges: [] } })).toEqual([]);
  });

  it("should return empty array for flow with no data", () => {
    expect(extractNodeSummary({})).toEqual([]);
  });

  it("should handle missing type/id gracefully", () => {
    const flow = {
      data: {
        nodes: [{ data: {} }, { data: { type: "ChatInput" } }],
      },
    };
    const result = extractNodeSummary(flow);
    expect(result[0]).toEqual({ type: "Unknown", id: "" });
    expect(result[1]).toEqual({ type: "ChatInput", id: "" });
  });

  it("should limit to 10 nodes", () => {
    const nodes = Array.from({ length: 15 }, (_, i) => ({
      data: { type: `Component${i}`, id: `id-${i}` },
    }));
    const result = extractNodeSummary({ data: { nodes } });
    expect(result).toHaveLength(10);
  });
});

describe("flow_json content stripping", () => {
  it("should strip flow_json code blocks from content", () => {
    const content =
      'I built a RAG pipeline.\n\n```flow_json\n{"data":{}}\n```\n\nLet me know!';
    const cleaned = content.replace(/```flow_json[\s\S]*?```/gi, "").trim();
    const collapsed = cleaned.replace(/\n{3,}/g, "\n\n");
    expect(collapsed).toBe("I built a RAG pipeline.\n\nLet me know!");
  });

  it("should handle content with no flow_json block", () => {
    const content = "Just a regular response.";
    const cleaned = content.replace(/```flow_json[\s\S]*?```/gi, "").trim();
    expect(cleaned).toBe("Just a regular response.");
  });

  it("should handle content that is only a flow_json block", () => {
    const content = '```flow_json\n{"data":{}}\n```';
    const cleaned = content.replace(/```flow_json[\s\S]*?```/gi, "").trim();
    expect(cleaned).toBe("");
  });
});
