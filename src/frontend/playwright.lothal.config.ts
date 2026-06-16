import { defineConfig, devices } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { PORT } from "./src/customization/config-constants";

dotenv.config();
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

// Dedicated config for the Lothal e2e suite. Unlike the main config (whose
// webServer runs LANGFLOW_AUTO_LOGIN=true for the 180+ legacy specs that assume
// auto-login), this boots the backend exactly like the real Lothal deployment:
// auto-login OFF, public signup OFF, new users inactive (the docker-compose.prod
// lockdown). The specs therefore drive the real auth funnels — sign in with the
// provisioned superuser, hit the real signup-disabled gate — with no mocking.
//
// Run: npx playwright test --config playwright.lothal.config.ts
// Locally it reuses an already-running auto-login-off app on :3000/:7860;
// in CI it spawns its own.
export default defineConfig({
  testDir: "./tests/extended/features/lothal",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  // Sequential: the suite shares one backend DB (clean-slate is done per test
  // via the real API, which only stays deterministic without parallel writers).
  workers: 1,
  timeout: 5 * 60 * 1000,
  reporter: process.env.CI
    ? "blob"
    : [
        ["list"],
        ["html", { outputFolder: "playwright-report", open: "never" }],
      ],
  use: {
    baseURL: `http://localhost:${PORT || 3000}/`,
    actionTimeout: 20000,
    trace: "on-first-retry",
    contextOptions: { javaScriptEnabled: true },
  },
  globalTeardown: require.resolve("./tests/globalTeardown.ts"),
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        contextOptions: {
          permissions: ["clipboard-read", "clipboard-write"],
        },
      },
    },
  ],
  webServer: [
    {
      command:
        "uv run uvicorn --factory langflow.main:create_app --host localhost --port 7860 --loop asyncio --log-level error --no-access-log",
      port: 7860,
      env: {
        LANGFLOW_DATABASE_URL: "sqlite:///./temp-lothal",
        LANGFLOW_AUTO_LOGIN: "false",
        LANGFLOW_SUPERUSER: "langflow",
        LANGFLOW_SUPERUSER_PASSWORD: "langflow",
        LANGFLOW_ENABLE_SIGNUP: "false",
        LANGFLOW_NEW_USER_IS_ACTIVE: "false",
        LANGFLOW_DEACTIVATE_TRACING: "true",
        LANGFLOW_LOG_LEVEL: "ERROR",
        DO_NOT_TRACK: "true",
      },
      stdout: "ignore",
      reuseExistingServer: true,
      timeout: 120 * 750,
    },
    {
      command: "npm start",
      port: PORT || 3000,
      env: { VITE_PROXY_TARGET: "http://localhost:7860" },
      reuseExistingServer: true,
    },
  ],
});
