import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";

test(
  "Gmail Fetch Emails",
  { tag: ["@release", "@components", "@composio"] },
  async ({ page }) => {
    // Force event delivery to streaming (remove multi-run variants)
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

    // Add Gmail (Composio) component from the sidebar
    await page
      .getByTestId("composioGmail")
      .hover()
      .then(async (): Promise<void> => {
        await page.getByTestId("add-component-button-gmail").click();
      });

    // Clean up any existing API key badges and fill with provided key
    await removeOldApiKeys(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .fill(process.env.COMPOSIO_API_KEY!);

    // Wait for Gmail connection to be established
    await page.waitForSelector('[data-testid="button_connected_gmail"]', {
      timeout: 30000,
    });

    // Open action list and select Fetch emails (by name or slug)
    await page.getByTestId("button_open_list_selection").click();

    // Prefer explicit testid for action by name; fallback to slug if needed
    const fetchByName = page.getByTestId("list_item_fetch_emails");
    const fetchByNameCount = await fetchByName.count();
    if (fetchByNameCount > 0) {
      await fetchByName.click();
      await page.waitForSelector('[role="dialog"]', { state: 'detached', timeout: 10000 });
    } else {
      // If UI exposes slug explicitly
      const fetchBySlug = page.getByTestId("list_item_GMAIL_FETCH_EMAILS");
      await fetchBySlug.click();
      await page.waitForSelector('[role="dialog"]', { state: 'detached', timeout: 10000 });
    }

    // Optionally set params, e.g., max_results
    const maxResultsField = page.getByTestId("int_int_max_results");
    if ((await maxResultsField.count()) > 0) {
      await maxResultsField.fill("10");
    }

    // Wait briefly to allow action UI to load
    await page.waitForTimeout(2000);

    // Run the Gmail node
    await page.getByTestId("button_run_gmail").click();

    // Prefer success toast, but don't fail if it doesn't render; we'll validate output directly.
    try {
      await page.waitForSelector("text=built successfully", { timeout: 60000 });
    } catch (_e) {
      // Non-blocking: some runs may skip the toast; proceed to output validation.
    }

    // Inspect the output dataframe (try Gmail-specific testid, else any dataframe inspector)
    const gmailDfBtn = page.getByTestId("output-inspection-dataframe-gmailapi");
    if ((await gmailDfBtn.count()) > 0) {
      await gmailDfBtn.click();
    } else {
      const anyDfBtn = page.locator("[data-testid^='output-inspection-dataframe-']").first();
      if ((await anyDfBtn.count()) > 0) {
        await anyDfBtn.click();
      }
    }

    // Wait until grid has at least one cell
    await expect(async () => {
      const cells = await page.getByRole("gridcell").count();
      expect(cells).toBeGreaterThan(0);
    }).toPass({ timeout: 30000 });
  },
); 