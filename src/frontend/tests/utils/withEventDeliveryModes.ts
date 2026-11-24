import { type Page } from "@playwright/test";
import { test } from "../fixtures";

type TestFunction = (args: { page: Page }) => Promise<void>;
type TestConfig = Parameters<typeof test>[1];

/**
 * Shim that historically expanded a spec into one test per v1
 * ``event_delivery`` mode (streaming / polling / direct). The v2 workflows
 * endpoint replaced the three modes with a single AG-UI SSE path, so the
 * wrapper now just registers the test once. Kept as a no-op so existing
 * spec call sites don't all have to change in this PR; a follow-up can
 * delete the wrapper and inline ``test`` at every call site.
 *
 * @param title The test title
 * @param config The test configuration (tags, etc)
 * @param testFn The test function to wrap
 */
export function withEventDeliveryModes(
  title: string,
  config: TestConfig,
  testFn: TestFunction,
) {
  test(title, config, async ({ page }) => {
    await testFn({ page });
  });
}
