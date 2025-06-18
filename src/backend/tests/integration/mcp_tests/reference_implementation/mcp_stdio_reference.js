import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// ---------------------------------------------------------------------------
// StdIO MCP Test Server – mirrors the unified HTTP/SSE server but speaks only
// the MCP stdio transport (suitable for spawning as a child process).
// ---------------------------------------------------------------------------

const server = new McpServer({
  name: "Langflow MCP STDIO Test Server",
  version: "1.0.0"
});

// Echo tool – same as HTTP variant
server.tool(
  "echo",
  { message: z.string().describe("Message to echo back") },
  async ({ message }) => ({
    content: [{ type: "text", text: `Echo: ${message}` }]
  })
);

// Server info
server.tool("get_server_info", {}, async () => ({
  content: [{
    type: "text",
    text: JSON.stringify(
      {
        name: "Langflow MCP STDIO Test Server",
        version: "1.0.0",
        transport: "stdio",
        supported_protocols: ["2025-03-26"],
        timestamp: new Date().toISOString(),
        test_suite: "langflow-integration"
      },
      null,
      2
    )
  }]
}));

// Math tool
server.tool(
  "add_numbers",
  { a: z.number(), b: z.number() },
  async ({ a, b }) => ({ content: [{ type: "text", text: `Result: ${a + b}` }] })
);

// Complex tool
server.tool(
  "process_data",
  {
    data: z.object({
      name: z.string(),
      values: z.array(z.number())
    })
  },
  async ({ data }) => ({
    content: [
      {
        type: "text",
        text: JSON.stringify(
          {
            processed: true,
            name: data.name,
            sum: data.values.reduce((p, v) => p + v, 0),
            count: data.values.length
          },
          null,
          2
        )
      }
    ]
  })
);

// Simulate error tool
server.tool(
  "simulate_error",
  { kind: z.enum(["validation", "runtime", "timeout"]) },
  async ({ kind }) => {
    switch (kind) {
      case "validation":
        throw new Error("Validation error: Invalid input parameters");
      case "runtime":
        throw new Error("Runtime error: Something went wrong during execution");
      case "timeout":
        await new Promise((r) => setTimeout(r, 1000));
        throw new Error("Timeout error: Operation took too long");
      default:
        throw new Error("Unknown error type");
    }
  }
);

// ---------------------------------------------------------------------------
// Bootstrap – connect to stdio transport
// ---------------------------------------------------------------------------
(async () => {
  try {
    const transport = new StdioServerTransport(process.stdin, process.stdout);
    await server.connect(transport);
  } catch (error) {
    console.error("Failed to start MCP stdio server:", error);
    process.exit(1);
  }
})();