import { defineConfig, devices } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { PORT } from "./src/customization/config-constants";
import {
  AUTHZ_STARTUP_LOG,
  getE2EArtifactNamespace,
  getE2EDatabaseDirectory,
  getE2ETestIgnore,
  isAuthzE2EMode,
} from "./tests/utils/authz-e2e-mode.mjs";

dotenv.config();
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

const authzMode = isAuthzE2EMode();
const artifactNamespace = getE2EArtifactNamespace();
const databaseDirectory = getE2EDatabaseDirectory();

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
/**
 * See https://playwright.dev/docs/test-configuration.
 */

export default defineConfig({
  testDir: "./tests",
  testIgnore: getE2ETestIgnore(),
  /* Run tests in files in parallel */
  fullyParallel: !authzMode,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: authzMode ? 0 : 1,
  /* Opt out of parallel tests on CI. */
  workers: authzMode ? 1 : 2,
  outputDir: authzMode ? "test-results-authz" : "test-results",
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  timeout: 5 * 60 * 1000, // 5 minutes
  expect: {
    // Windows CI runners are markedly slower than Linux; assertions that poll
    // the backend (toHaveCount after a delete, toBeVisible after a fetch)
    // routinely blow the 5s default there.
    timeout: process.platform === "win32" ? 15_000 : 5_000,
  },
  // reporter: [
  //   ["html", { open: "never", outputFolder: "playwright-report/test-results" }],
  // ],
  reporter: process.env.CI
    ? [["blob", { outputDir: `blob-report-${artifactNamespace}` }]]
    : [
        ["list"], // console output in terminal
        [
          "html",
          {
            outputFolder: authzMode
              ? "playwright-report-authz"
              : "playwright-report",
            open: "never",
          },
        ], // generate HTML, don't open
      ],
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: `http://localhost:${PORT || 3000}/`,

    // Also the default for page.waitForResponse/waitForSelector calls that
    // pass no explicit timeout. Windows CI needs the extra headroom.
    actionTimeout: process.platform === "win32" ? 40_000 : 20_000,
    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: "on-first-retry",
    contextOptions: {
      javaScriptEnabled: true,
    },
  },

  globalTeardown: require.resolve("./tests/globalTeardown.ts"),

  /* Configure projects for major browsers */
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          // headless: false,
        },
        contextOptions: {
          // chromium-specific permissions
          permissions: ["clipboard-read", "clipboard-write"],
        },
      },
    },
    // {
    //   name: "firefox",
    //   use: {
    //     ...devices["Desktop Firefox"],
    //     launchOptions: {
    //       // headless: false,
    //       firefoxUserPrefs: {
    //         "dom.events.asyncClipboard.readText": true,
    //         "dom.events.testing.asyncClipboard": true,
    //       },
    //     },
    //   },
    // },
    // {
    //   name: "safari",
    //   use: {
    //     ...devices["Desktop Safari"],
    //     launchOptions: {
    //       // headless: false,
    //     },
    //   },
    // },
    // {
    //   name: "arc",
    //   use: {
    //     ...devices["Desktop Arc"],
    //     launchOptions: {
    //       // headless: false,
    //     },
    //   },
    // },
    // {
    //   name: "firefox",
    //   use: {
    //     ...devices["Desktop Firefox"],
    //     launchOptions: {
    //       headless: false,
    //       firefoxUserPrefs: {
    //         "dom.events.asyncClipboard.readText": true,
    //         "dom.events.testing.asyncClipboard": true,
    //       },
    //     },
    //   },
    // },
  ],
  webServer: [
    {
      command: "node tests/fixtures/openai-compatible-server.mjs",
      url: "http://127.0.0.1:8787/health",
      reuseExistingServer: true,
    },
    {
      command:
        (authzMode
          ? "node tests/fixtures/prepare-authz-server.mjs && uv run --no-sync"
          : "uv run") +
        " uvicorn --factory langflow.main:create_app --host localhost --port 7860 --loop asyncio --log-level error --no-access-log",
      port: 7860,
      env: {
        LANGFLOW_DATABASE_URL: `sqlite:///./${databaseDirectory}`,
        LANGFLOW_CONFIG_DIR: authzMode
          ? "./temp-authz-config"
          : "./temp-config",
        LANGFLOW_AUTO_LOGIN: authzMode ? "false" : "true",
        ...(authzMode ? { LANGFLOW_RATE_LIMIT_ENABLED: "false" } : {}),
        LANGFLOW_SUPERUSER: "langflow",
        LANGFLOW_SUPERUSER_PASSWORD: "test-superuser-password", // pragma: allowlist secret
        LANGFLOW_AUTHZ_ENABLED: authzMode ? "true" : "false",
        LANGFLOW_AUTHZ_SUPERUSER_BYPASS: "true",
        LANGFLOW_AUTHZ_AUDIT_ENABLED: authzMode ? "true" : "false",
        LANGFLOW_AUTHZ_AUDIT_DURABLE: authzMode ? "true" : "false",
        LANGFLOW_AUTHZ_AUDIT_RETENTION_DAYS: "30",
        LANGFLOW_DEACTIVATE_TRACING: "true",
        LANGFLOW_LOG_LEVEL: authzMode ? "INFO" : "ERROR",
        ...(authzMode ? { LANGFLOW_LOG_FILE: AUTHZ_STARTUP_LOG } : {}),
        OPENAI_API_KEY: "langflow-loopback-test-key", // pragma: allowlist secret
        OPENAI_BASE_URL: "http://127.0.0.1:8787/v1",
        // The E2E harness intentionally routes provider calls to its local OpenAI stub.
        LANGFLOW_SSRF_ALLOWED_HOSTS: "127.0.0.1",
        DO_NOT_TRACK: "true",
        // Serve the A2A discovery + JSON-RPC endpoints so the Agent tab tests
        // can publish and exercise a live agent.
        LANGFLOW_A2A_ENABLED: "true",
      },
      stdout:
        process.env.CI && process.platform === "win32" ? "pipe" : "ignore",
      stderr: "pipe",

      reuseExistingServer: !authzMode,
      // Windows CI runners can spend 60s+ on imports plus the Alembic
      // migration chain against the fresh SQLite DB before the port opens;
      // 90s boots are routinely lost there.
      timeout: process.platform === "win32" ? 240_000 : 90_000,
    },
    {
      command: "npm start",
      port: PORT || 3000,
      env: {
        VITE_PROXY_TARGET: "http://localhost:7860",
        LANGFLOW_E2E_AUTHZ: authzMode ? "true" : "false",
      },
      reuseExistingServer: !authzMode,
    },
  ],
});
