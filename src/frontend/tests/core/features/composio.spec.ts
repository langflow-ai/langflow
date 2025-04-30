import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";

test(
  "user should be able to interact with composio component",
  { tag: ["@release", "@workspace", "@api", "@components"] },
  async ({ page, context }) => {
    test.skip(
      !process?.env?.COMPOSIO_API_KEY,
      "COMPOSIO_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("gmail");

    await page
      .getByTestId("composioGmail")
      .hover()
      .then(async (): Promise<void> => {
        await page.getByTestId("add-component-button-gmail").click();
      });

    await removeOldApiKeys(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .fill(process.env.COMPOSIO_API_KEY!);

    await page.waitForSelector('[data-testid="button_connected_gmail"]', {
      timeout: 20000,
    });

    await page.getByTestId("button_open_list_selection").click();

    await page.getByTestId(`list_item_fetch_emails`).click();

    await page.getByTestId("int_int_max_results").fill("10");

    await page.getByTestId("button_run_gmail").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 30000,
    });

    await page.getByTestId("output-inspection-dataframe-gmailapi").click();

    const colNumber: number = await page.getByRole("gridcell").count();
    expect(colNumber).toBeGreaterThan(9);
  },
);
