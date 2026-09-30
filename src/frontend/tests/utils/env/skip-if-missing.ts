import { test } from "../../fixtures";

/**
 * Named skip-guards for environment-gated tests.
 *
 * Use inside a `test(...)` body (NOT at module scope — Playwright's
 * `test.skip(condition, reason)` must be called from inside a test).
 *
 *   test("foo", async ({ page }) => {
 *     skipIfMissing.openAiKey();
 *     ...
 *   });
 */
export const skipIfMissing = {
  openAiKey: (): void => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );
  },

  anthropicKey: (): void => {
    test.skip(
      !process?.env?.ANTHROPIC_API_KEY,
      "ANTHROPIC_API_KEY required to run this test",
    );
  },

  storeApiKey: (): void => {
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );
  },

  autoLoginDisabled: (): void => {
    test.skip(
      process?.env?.LANGFLOW_AUTO_LOGIN !== "false",
      "Server must run with AUTO_LOGIN=FALSE for this test",
    );
  },

  wxoDeploymentsEnabled: (): void => {
    test.skip(
      process?.env?.LANGFLOW_FEATURE_WXO_DEPLOYMENTS !== "true",
      "Requires LANGFLOW_FEATURE_WXO_DEPLOYMENTS=true",
    );
  },
};
