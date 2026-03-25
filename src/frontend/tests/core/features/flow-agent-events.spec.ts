import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("Flow Agent Events", () => {
  test(
    "should show agent working banner when events are posted and dismiss on settle",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Create a blank flow
      await page.getByTestId("blank-flow").click();

      // Wait for the flow editor to load
      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 30000,
      });

      // Get the flow ID from the URL
      const url = page.url();
      const flowIdMatch = url.match(/flow\/([a-f0-9-]+)/);
      expect(flowIdMatch).not.toBeNull();
      const flowId = flowIdMatch![1];

      // Post an event via the page's fetch (uses the page's auth cookies/headers)
      await page.evaluate(async (fid: string) => {
        await fetch(`/api/v1/flows/${fid}/events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type: "component_added",
            summary: "Added OpenAI Model",
          }),
        });
      }, flowId);

      // Wait for the "Agent is working..." banner to appear
      await expect(
        page.getByText("Agent is working on this flow..."),
      ).toBeVisible({ timeout: 15000 });

      // Post a flow_settled event
      await page.evaluate(async (fid: string) => {
        await fetch(`/api/v1/flows/${fid}/events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type: "flow_settled",
            summary: "Done building",
          }),
        });
      }, flowId);

      // Wait for the banner to disappear
      await expect(
        page.getByText("Agent is working on this flow..."),
      ).toBeHidden({ timeout: 15000 });
    },
  );
});
