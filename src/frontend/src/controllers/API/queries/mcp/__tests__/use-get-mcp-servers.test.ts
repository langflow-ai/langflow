import { mergeMCPServerCounts } from "../use-get-mcp-servers";

describe("mergeMCPServerCounts", () => {
  it("clears a cached error when refreshed counts omit an error", () => {
    const merged = mergeMCPServerCounts(
      [
        {
          name: "server",
          mode: null,
          toolsCount: null,
          error: "Connection refused",
        },
      ],
      [
        {
          name: "server",
          mode: "streamable_http",
          toolsCount: 2,
        },
      ],
    );

    expect(merged).toEqual([
      {
        name: "server",
        mode: "streamable_http",
        toolsCount: 2,
        error: undefined,
      },
    ]);
  });
});
