import { type Page } from "@playwright/test";
import { test } from "../fixtures";

type TestFunction = (args: { page: Page }) => Promise<void>;
type TestConfig = Parameters<typeof test>[1];

/**
 * Wraps a test function to run it with both streaming and polling event delivery modes.
 * Adds a 3-second delay between test runs to ensure proper separation.
 *
 * @param title The test title
 * @param config The test configuration (tags, etc)
 * @param testFn The test function to wrap
 */
export function withEventDeliveryModes(
  title: string,
  config: TestConfig,
  testFn: TestFunction,
  { timeout = 10000 }: { timeout?: number } = {},
) {
  const eventDeliveryModes = ["streaming", "polling", "direct"] as const;

  for (const [index, eventDelivery] of eventDeliveryModes.entries()) {
    test(`${title} - ${eventDelivery}`, config, async ({ page }) => {
      if (index === 0) {
        await new Promise((resolve) => setTimeout(resolve, timeout));
      }

      // Intercept the config request and modify the event_delivery setting
      await page.route("**/api/v1/config", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        json.event_delivery = eventDelivery;
        await route.fulfill({ response, json });
      });

      // Run the original test function
      await testFn({ page });
    });
  }
}
