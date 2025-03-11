import { Page, test } from "@playwright/test";

type TestFunction = (args: { page: Page }) => Promise<void>;
type TestConfig = Parameters<typeof test>[1];

/**
 * Wraps a test function to run it with both streaming and polling event delivery modes.
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
  const eventDeliveryModes = ["streaming", "polling"] as const;

  for (const eventDelivery of eventDeliveryModes) {
    test(`${title} - ${eventDelivery}`, config, async ({ page }) => {
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
