/**
 * Unified MCP Test Server
 * 
 * This server supports both MCP protocol versions for comprehensive integration testing:
 * - Streamable HTTP (2025-03-26) on /mcp endpoint
 * - HTTP+SSE (2024-11-05) on /sse endpoint
 * 
 * This eliminates the need for separate test servers and provides a single
 * server that can test protocol detection and fallback behavior.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from "express";
import { randomUUID } from "node:crypto";
import { z } from "zod";

// Create an MCP server with test-specific configuration
const server = new McpServer({
  name: "Langflow Unified MCP Test Server",
  version: "1.0.0"
});

// Test tools - canonical implementations for integration testing

// Echo tool - basic functionality test
server.tool(
  "echo",
  { message: z.string().describe("Message to echo back") },
  async ({ message }) => ({
    content: [{ type: "text", text: `Echo: ${message}` }]
  })
);

// Server info tool - protocol detection test
server.tool(
  "get_server_info",
  {},
  async () => ({
    content: [{
      type: "text", 
      text: JSON.stringify({
        name: "Langflow Unified MCP Test Server",
        version: "1.0.0",
        transport: "unified",
        supported_protocols: ["2025-03-26", "2024-11-05"],
        timestamp: new Date().toISOString(),
        test_suite: "langflow-integration"
      }, null, 2)
    }]
  })
);

// Math tool - parameter validation test
server.tool(
  "add_numbers",
  { 
    a: z.number().describe("First number"),
    b: z.number().describe("Second number")
  },
  async ({ a, b }) => ({
    content: [{ 
      type: "text", 
      text: `Result: ${a + b}` 
    }]
  })
);

// Complex tool - nested parameters test
server.tool(
  "process_data",
  {
    data: z.object({
      name: z.string(),
      values: z.array(z.number())
    }).describe("Data to process")
  },
  async ({ data }) => ({
    content: [{
      type: "text",
      text: JSON.stringify({
        processed: true,
        name: data.name,
        sum: data.values.reduce((a, b) => a + b, 0),
        count: data.values.length
      }, null, 2)
    }]
  })
);

// Error simulation tool - error handling test
server.tool(
  "simulate_error",
  { error_type: z.enum(["validation", "runtime", "timeout"]).describe("Type of error to simulate") },
  async ({ error_type }) => {
    switch (error_type) {
      case "validation":
        throw new Error("Validation error: Invalid input parameters");
      case "runtime":
        throw new Error("Runtime error: Something went wrong during execution");
      case "timeout":
        // Simulate a timeout scenario
        await new Promise(resolve => setTimeout(resolve, 1000));
        throw new Error("Timeout error: Operation took too long");
      default:
        throw new Error("Unknown error type");
    }
  }
);

// Add a test resource for resource functionality testing
server.resource(
  "test-config",
  "config://test",
  async (uri) => ({
    contents: [{
      uri: uri.href,
      text: JSON.stringify({
        test_server: "unified",
        supported_protocols: ["2025-03-26", "2024-11-05"],
        capabilities: ["tools", "resources", "prompts"],
        test_data: "This is test configuration data"
      }, null, 2)
    }]
  })
);

// Add a test prompt for prompt functionality testing
server.prompt(
  "test-greeting",
  { name: z.string().optional().describe("Name to greet") },
  ({ name = "World" }) => ({
    messages: [{
      role: "user",
      content: {
        type: "text",
        text: `Hello, ${name}! This is a test prompt from the unified MCP server.`
      }
    }]
  })
);

// Set up Express app
const app = express();
app.use(express.json());

// Enable CORS for cross-origin testing
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, mcp-session-id, x-mcp-session-id');
  if (req.method === 'OPTIONS') {
    res.sendStatus(200);
  } else {
    next();
  }
});

// Transport storage
const streamableTransports = {}; // Session ID -> transport for Streamable HTTP
const sseTransports = {}; // Session ID -> transport for HTTP+SSE (legacy)

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ 
    status: 'ok', 
    server: 'langflow-unified-mcp-test',
    supported_protocols: ['2025-03-26', '2024-11-05'],
    endpoints: {
      streamable_http: '/mcp',
      http_sse: '/sse',
      messages: '/messages',
      debug: '/debug'
    },
    uptime: process.uptime()
  });
});

// Debug endpoint – returns runtime information useful during development and testing
app.get('/debug', (req, res) => {
  res.status(200).json({
    status: 'ok',
    server: 'langflow-unified-mcp-test',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    pid: process.pid,
    node_version: process.version,
    memory_usage: process.memoryUsage(),
    session_counts: {
      streamable_http: Object.keys(streamableTransports).length,
      http_sse: Object.keys(sseTransports).length
    },
    active_sessions: {
      streamable_http: Object.keys(streamableTransports),
      http_sse: Object.keys(sseTransports)
    }
  });
});

// =============================================================================
// STREAMABLE HTTP TRANSPORT (MCP 2025-03-26) - /mcp endpoint
// =============================================================================

// Handle POST requests for Streamable HTTP client-to-server communication
app.post('/mcp', async (req, res) => {
  try {
    console.log("[Unified Server] Streamable HTTP POST request to /mcp");
    
    // Check for existing session ID
    const sessionId = req.headers['mcp-session-id'] || req.headers['x-mcp-session-id'];
    let transport;

    if (sessionId && streamableTransports[sessionId]) {
      // Reuse existing transport
      transport = streamableTransports[sessionId];
      console.log(`[Unified Server] Reusing existing session: ${sessionId}`);
    } else {
      // Create new transport
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (sessionId) => {
          // Store the transport by session ID
          streamableTransports[sessionId] = transport;
          console.log(`[Unified Server] Session initialized: ${sessionId}`);
        }
      });

      // Clean up transport when closed
      transport.onclose = () => {
        if (transport.sessionId) {
          delete streamableTransports[transport.sessionId];
          console.log(`[Unified Server] Session closed: ${transport.sessionId}`);
        }
      };
      
      // Connect server to transport
      await server.connect(transport);
    }

    // Handle the request
    await transport.handleRequest(req, res, req.body);
    
  } catch (error) {
    console.error("[Unified Server] Error handling Streamable HTTP request:", error);
    if (!res.headersSent) {
      res.status(500).json({
        error: "Internal server error",
        message: error.message
      });
    }
  }
});

// Handle GET requests for Streamable HTTP server-to-client communication
app.get('/mcp', async (req, res) => {
  try {
    console.log("[Unified Server] Streamable HTTP GET request to /mcp");
    
    const sessionId = req.headers['mcp-session-id'] || req.headers['x-mcp-session-id'];
    
    if (!sessionId || !streamableTransports[sessionId]) {
      return res.status(400).json({
        error: "Session ID required for GET requests"
      });
    }
    
    const transport = streamableTransports[sessionId];
    await transport.handleRequest(req, res);
    
  } catch (error) {
    console.error("[Unified Server] Error handling Streamable HTTP GET:", error);
    if (!res.headersSent) {
      res.status(500).json({
        error: "Internal server error",
        message: error.message
      });
    }
  }
});

// ----------------------------------------------------------------------
// Graceful session-termination endpoint
// ----------------------------------------------------------------------
app.delete('/mcp', async (req, res) => {
  const sessionId = req.headers['mcp-session-id'] || req.headers['x-mcp-session-id'];

  // Unknown session → keep current behaviour (404) so callers know
  if (!sessionId || !streamableTransports[sessionId]) {
    return res.status(404).json({ error: 'Unknown session' });
  }

  try {
    const transport = streamableTransports[sessionId];

    // Ask the transport (and therefore the underlying MCP server) to shut down
    // Some SDK versions expose `.close()`, others `.shutdown()`.  Both are
    // safe to call inside a try/catch – pick whichever exists.
    if (typeof transport.close === 'function') {
      await transport.close();
    } else if (typeof transport.shutdown === 'function') {
      await transport.shutdown();
    }

    delete streamableTransports[sessionId];
    console.log(`[Unified Server] Session terminated via DELETE: ${sessionId}`);
    return res.sendStatus(204);   // No-Content → success
  } catch (err) {
    console.error('[Unified Server] Error during session terminate:', err);
    return res.status(500).json({ error: 'Failed to terminate session' });
  }
});

// =============================================================================
// HTTP+SSE TRANSPORT (MCP 2024-11-05) - /sse and /messages endpoints
// =============================================================================

// SSE endpoint - establishes the HTTP+SSE connection (legacy protocol)
app.get("/sse", async (req, res) => {
  console.log("[Unified Server] HTTP+SSE connection request to /sse");
  
  try {
    // Create SSE transport for legacy clients (following official SDK pattern)
    const transport = new SSEServerTransport("/messages", res);
    sseTransports[transport.sessionId] = transport;
    
    // Clean up transport when connection closes
    res.on("close", () => {
      delete sseTransports[transport.sessionId];
      console.log(`[Unified Server] HTTP+SSE session closed: ${transport.sessionId}`);
    });
    
    await server.connect(transport);
    
    console.log(`[Unified Server] HTTP+SSE connection established with session: ${transport.sessionId}`);
  } catch (error) {
    console.error("[Unified Server] Error establishing HTTP+SSE connection:", error);
    if (!res.headersSent) {
      res.status(500).json({
        error: "Failed to establish SSE connection",
        message: error.message
      });
    }
  }
});

// Messages endpoint - handles HTTP+SSE client-to-server communication
app.post("/messages", async (req, res) => {
  console.log("[Unified Server] HTTP+SSE POST request to /messages");
  
  try {
    // Get session ID from query parameters (following official SDK pattern)
    const sessionId = req.query.sessionId;
    const transport = sseTransports[sessionId];
    
    if (!transport) {
      return res.status(400).json({
        error: "No transport found for sessionId. Connect to /sse first.",
        sessionId: sessionId
      });
    }
    
    await transport.handlePostMessage(req, res, req.body);
    
  } catch (error) {
    console.error("[Unified Server] Error handling HTTP+SSE message:", error);
    if (!res.headersSent) {
      res.status(500).json({
        error: "Internal server error",
        message: error.message
      });
    }
  }
});

// =============================================================================
// SERVER STARTUP
// =============================================================================

// Get port from command line argument or default to 8000
const port = process.argv[2] ? parseInt(process.argv[2]) : 8000;

app.listen(port, '127.0.0.1', () => {
  console.log(`🚀 Langflow Unified MCP Test Server starting...`);
  console.log(`   Name: Langflow Unified MCP Test Server`);
  console.log(`   Version: 1.0.0`);
  console.log(`   Port: ${port}`);
  console.log(`   Protocols: MCP 2025-03-26 (Streamable HTTP), MCP 2024-11-05 (HTTP+SSE)`);
  console.log(`   Endpoints:`);
  console.log(`     - Streamable HTTP: http://localhost:${port}/mcp`);
  console.log(`     - HTTP+SSE: http://localhost:${port}/sse`);
  console.log(`     - Messages: http://localhost:${port}/messages`);
  console.log(`     - Health: http://localhost:${port}/health`);
  console.log(`     - Debug: http://localhost:${port}/debug`);
  console.log(`   Test Suite: langflow-integration`);
  console.log(`✅ Unified MCP Test Server ready`);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n[Unified Server] Shutting down gracefully...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n[Unified Server] Shutting down gracefully...');
  process.exit(0);
}); 
