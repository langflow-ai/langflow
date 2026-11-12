import { mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

const directory = mkdtempSync(path.join(tmpdir(), "langflow-upgrade-qa-"));
const knowledgeBasesDirectory = path.join(directory, "knowledge-bases");
mkdirSync(knowledgeBasesDirectory);

export default defineConfig({
  ...base,
  testDir: "./tests/live",
  testMatch: "admin-upgrade-repair.spec.ts",
  testIgnore: [],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  globalTeardown: undefined,
  use: { ...base.use, baseURL: "http://127.0.0.1:3011/" },
  webServer: [
    {
      command:
        "uv run --no-sync uvicorn --factory langflow.main:create_app --host 127.0.0.1 --port 7881 --loop asyncio --log-level error --no-access-log",
      url: "http://127.0.0.1:7881/health",
      env: {
        LANGFLOW_DATABASE_URL: `sqlite:///${path.join(directory, "qa.db")}`,
        LANGFLOW_CONFIG_DIR: path.join(directory, "config"),
        LANGFLOW_KNOWLEDGE_BASES_DIR: knowledgeBasesDirectory,
        LANGFLOW_AUTO_LOGIN: "true",
        LANGFLOW_DEACTIVATE_TRACING: "true",
        DO_NOT_TRACK: "true",
      },
      reuseExistingServer: false,
      timeout: 180_000,
    },
    {
      command: "npm start -- --host 127.0.0.1 --port 3011 --strictPort",
      url: "http://127.0.0.1:3011",
      env: { VITE_PROXY_TARGET: "http://127.0.0.1:7881" },
      reuseExistingServer: false,
      timeout: 90_000,
    },
  ],
});
