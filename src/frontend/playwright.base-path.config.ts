import { defineConfig, devices } from "@playwright/test";

if (!process.env.LANGFLOW_BASE_PATH_TEST_URL) {
  throw new Error(
    "Set LANGFLOW_BASE_PATH_TEST_URL to a prefixed Langflow deployment.",
  );
}

export default defineConfig({
  testDir: "./tests/live",
  testMatch: "base-path.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.LANGFLOW_BASE_PATH_TEST_URL,
    trace: "retain-on-failure",
  },
});
