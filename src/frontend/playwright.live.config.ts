import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";
import { PORT } from "./src/customization/config-constants";

// Deliberately not 7860: that is the blocking suite's backend port.
const LIVE_BACKEND_PORT = 7861;

// Spread the base config rather than passing it as defineConfig's first
// argument. Multi-argument defineConfig CONCATENATES array options instead of
// replacing them, so `defineConfig(baseConfig, { webServer: [...] })` starts the
// base servers *and* these ones — five servers, two of them on port 3000, which
// fails the run outright with "http://localhost:3000 is already used". Worse,
// without the port clash the suite would drive the base frontend, whose proxy
// targets the loopback-fixture backend, and every "live" assertion would pass
// without ever reaching a real provider. Spreading overrides `webServer`.
export default defineConfig({
  ...baseConfig,
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
  // Playwright only applies `env` to a server it starts itself, so this suite
  // also owns a dedicated port, database file, and `reuseExistingServer: false`
  // — otherwise a blocking-suite backend still listening on 7860 would be
  // reused and the "live" check would silently talk to the loopback fixture.
  webServer: [
    {
      command: `uv run uvicorn --factory langflow.main:create_app --host localhost --port ${LIVE_BACKEND_PORT} --loop asyncio --log-level error --no-access-log`,
      port: LIVE_BACKEND_PORT,
      env: {
        LANGFLOW_DATABASE_URL: "sqlite:///./temp-live",
        LANGFLOW_AUTO_LOGIN: "true",
        LANGFLOW_SUPERUSER: "langflow",
        LANGFLOW_SUPERUSER_PASSWORD: "test-superuser-password", // pragma: allowlist secret
        LANGFLOW_DEACTIVATE_TRACING: "true",
        LANGFLOW_LOG_LEVEL: "ERROR",
        DO_NOT_TRACK: "true",
        LANGFLOW_A2A_ENABLED: "true",
      },
      stderr: "pipe",
      reuseExistingServer: false,
      timeout: 120 * 750,
    },
    {
      command: "npm start",
      port: PORT || 3000,
      env: {
        VITE_PROXY_TARGET: `http://localhost:${LIVE_BACKEND_PORT}`,
      },
      reuseExistingServer: false,
    },
  ],
});
