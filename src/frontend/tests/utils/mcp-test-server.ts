import { ChildProcess, spawn } from "node:child_process";
import { Page } from "@playwright/test";

interface MCPServerConfig {
  transport: "streamableHttp" | "sse";
  port?: number;
  maxStartupTime?: number;
}

interface MCPServerHandle {
  url: string;
  process: ChildProcess;
  stop: () => void;
}

/**
 * Starts an MCP test server with proper health checking and error handling.
 * Throws if the server fails to start or crashes.
 */
export async function startMCPTestServer(
  config: MCPServerConfig,
): Promise<MCPServerHandle> {
  const {
    transport,
    port = 3001,
    maxStartupTime = 30000, // 30 seconds max
  } = config;

  const endpoint = transport === "streamableHttp" ? "/mcp" : "/sse";
  const serverUrl = `http://localhost:${port}${endpoint}`;

  return new Promise((resolve, reject) => {
    let resolved = false;
    const startTime = Date.now();

    // Start the server using the locally installed package
    const serverProcess = spawn(
      "npx",
      ["@modelcontextprotocol/server-everything", transport],
      {
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, PORT: port.toString() },
      },
    );

    let stdoutData = "";
    let stderrData = "";

    // Capture output for debugging
    serverProcess.stdout?.on("data", (data) => {
      stdoutData += data.toString();
    });

    serverProcess.stderr?.on("data", (data) => {
      stderrData += data.toString();
    });

    // Handle process errors
    serverProcess.on("error", (error) => {
      if (!resolved) {
        resolved = true;
        reject(
          new Error(
            `Failed to start MCP server: ${error.message}\nStdout: ${stdoutData}\nStderr: ${stderrData}`,
          ),
        );
      }
    });

    // Handle process exit
    serverProcess.on("exit", (code, signal) => {
      if (!resolved) {
        resolved = true;
        reject(
          new Error(
            `MCP server exited prematurely (code: ${code}, signal: ${signal})\nStdout: ${stdoutData}\nStderr: ${stderrData}`,
          ),
        );
      }
    });

    // Poll for server readiness with exponential backoff
    const pollInterval = 200; // Start with 200ms
    let attempts = 0;

    const checkHealth = async () => {
      if (resolved) return;

      const elapsed = Date.now() - startTime;
      if (elapsed > maxStartupTime) {
        resolved = true;
        serverProcess.kill();
        reject(
          new Error(
            `MCP server failed to start within ${maxStartupTime}ms\nStdout: ${stdoutData}\nStderr: ${stderrData}`,
          ),
        );
        return;
      }

      try {
        // Try to connect to the server
        const response = await fetch(serverUrl, {
          method: "HEAD",
          signal: AbortSignal.timeout(1000),
        });

        // Server responded, consider it ready
        if (!resolved) {
          resolved = true;
          resolve({
            url: serverUrl,
            process: serverProcess,
            stop: () => {
              serverProcess.kill("SIGTERM");
              // Force kill after 5 seconds
              setTimeout(() => {
                if (!serverProcess.killed) {
                  serverProcess.kill("SIGKILL");
                }
              }, 5000);
            },
          });
        }
      } catch (error) {
        // Server not ready yet, schedule next check
        attempts++;
        const nextDelay = Math.min(pollInterval * Math.pow(1.5, attempts), 2000);
        setTimeout(checkHealth, nextDelay);
      }
    };

    // Start health checking after a brief initial delay
    setTimeout(checkHealth, 500);
  });
}

/**
 * Helper to wait for MCP tools to load in the UI
 */
export async function waitForMCPToolsLoaded(
  page: Page,
  timeout: number = 30000,
) {
  await page.waitForSelector(
    '[data-testid="dropdown_str_tool"]:not([disabled])',
    {
      timeout,
      state: "visible",
    },
  );
}
