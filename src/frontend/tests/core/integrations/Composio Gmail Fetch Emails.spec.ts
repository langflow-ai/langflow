import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

dotenv.config({ path: path.resolve(process.cwd(), ".env") });
test.use({ trace: "off", video: "off" });

import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";

test(
  "Gmail Fetch Emails",
  { tag: ["@release", "@components", "@composio"] },
  async ({ page }) => {
    // Force backend to use streaming so we don't hit multi-run behavior.
    await page.route("**/api/v1/config", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.event_delivery = "streaming";
      await route.fulfill({ response, json });
    });

    test.skip(
      !process?.env?.COMPOSIO_API_KEY,
      "COMPOSIO_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 10000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("gmail");

    // Add the Gmail (Composio) node from the sidebar.
    await page
      .getByTestId("composioGmail")
      .hover()
      .then(async (): Promise<void> => {
        await page.getByTestId("add-component-button-gmail").click();
      });

    // Remove any stale API key badges and paste our key.
    await removeOldApiKeys(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .fill(process.env.COMPOSIO_API_KEY!);

    // Wait until Gmail shows as connected.
    await page.waitForSelector('[data-testid="button_connected_gmail"]', {
      timeout: 30000,
    });

    // Give the UI a couple seconds to settle after connecting.
    await page.waitForTimeout(3000);

    // Open the action picker and choose 'Fetch emails'.
    await page.getByTestId("button_open_list_selection").click();

    // Prefer the action’s test id by name; fall back to the slug if that's what the UI renders.
    const fetchByName = page.getByTestId("list_item_fetch_emails");
    const fetchByNameCount = await fetchByName.count();
    if (fetchByNameCount > 0) {
      await fetchByName.click();
      await page.waitForSelector('[role="dialog"]', {
        state: "detached",
        timeout: 10000,
      });
    } else {
      // If the UI exposes the slug test id instead.
      const fetchBySlug = page.getByTestId("list_item_GMAIL_FETCH_EMAILS");
      await fetchBySlug.click();
      await page.waitForSelector('[role="dialog"]', {
        state: "detached",
        timeout: 10000,
      });
    }

    // Optionally tweak params (e.g., max_results).
    const maxResultsField = page.getByTestId("int_int_max_results");
    if ((await maxResultsField.count()) > 0) {
      await maxResultsField.fill("10");
    }

    // Give the action UI a moment to render.
    await page.waitForTimeout(2000);

    // Run the Gmail node.
    await page.getByTestId("button_run_gmail").click();

    // If the success toast appears, great; if not, we'll still validate via the output.
    try {
      await page.waitForSelector("text=built successfully", { timeout: 60000 });
    } catch (_e) {
      // Some runs skip the toast; keep going.
    }

    // Open the output dataframe (Gmail-specific test id if present; otherwise the first dataframe).
    const gmailDfBtn = page.getByTestId("output-inspection-dataframe-gmailapi");
    if ((await gmailDfBtn.count()) > 0) {
      await gmailDfBtn.click();
    } else {
      const anyDfBtn = page
        .locator("[data-testid^='output-inspection-dataframe-']")
        .first();
      if ((await anyDfBtn.count()) > 0) {
        await anyDfBtn.click();
      }
    }

    // Make sure at least one grid cell is rendered.
    await expect(async () => {
      const cells = await page.getByRole("gridcell").count();
      expect(cells).toBeGreaterThan(0);
    }).toPass({ timeout: 30000 });
  },
);
