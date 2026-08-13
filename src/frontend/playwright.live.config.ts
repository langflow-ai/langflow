import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";
import { PORT } from "./src/customization/config-constants";

export default defineConfig(baseConfig, {
  testDir: "./tests/live",
  testIgnore: [],
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    ...baseConfig.use,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  // The blocking suite routes OpenAI-compatible traffic to a loopback fixture.
  // The live smoke deliberately owns a separate server list so neither that
  // fixture nor its OPENAI_BASE_URL can leak into the real-provider check.
  webServer: [
    {
      command:
        "uv run uvicorn --factory langflow.main:create_app --host localhost --port 7860 --loop asyncio --log-level error --no-access-log",
      port: 7860,
      env: {
        LANGFLOW_DATABASE_URL: "sqlite:///./temp",
        LANGFLOW_AUTO_LOGIN: "true",
        LANGFLOW_SUPERUSER: "langflow",
        LANGFLOW_SUPERUSER_PASSWORD: "test-superuser-password", // pragma: allowlist secret
        LANGFLOW_DEACTIVATE_TRACING: "true",
        LANGFLOW_LOG_LEVEL: "ERROR",
        DO_NOT_TRACK: "true",
        LANGFLOW_A2A_ENABLED: "true",
      },
      stderr: "pipe",
      reuseExistingServer: true,
      timeout: 120 * 750,
    },
    {
      command: "npm start",
      port: PORT || 3000,
      env: {
        VITE_PROXY_TARGET: "http://localhost:7860",
      },
      reuseExistingServer: true,
    },
  ],
});
