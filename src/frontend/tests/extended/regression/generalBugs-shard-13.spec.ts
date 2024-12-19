import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "should be able to share a component on the store by clicking on the share button on the canvas",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.STORE_API_KEY,
      "STORE_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByText("Close", { exact: true }).click();

    await page.waitForSelector('[data-testid="user-profile-settings"]', {
      timeout: 3000,
    });
    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Settings", { exact: true }).first().click();

    await page
      .getByPlaceholder("Insert your API Key")
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await expect(page.getByText("API key saved successfully")).toBeVisible({
      timeout: 3000,
    });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await expect(page.getByText("New Flow", { exact: true })).toBeVisible({
      timeout: 3000,
    });

    await page.getByText("New Flow", { exact: true }).click();

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector("text=share", { timeout: 10000 });
    await page.waitForSelector("text=playground", { timeout: 10000 });
    await page.waitForSelector("text=api", { timeout: 10000 });

    await page.getByTestId("shared-button-flow").click();

    await page.waitForSelector("text=Share Flow", {
      timeout: 10000,
    });
    await page.waitForSelector('[data-testid="shared-button-flow"]', {
      timeout: 10000,
    });
    await page.waitForSelector("text=Share Flow", { timeout: 10000 });

    await page.getByTestId("share-modal-button-flow").click();

    let replace = await page.getByTestId("replace-button").isVisible();

    if (replace) {
      await page.getByTestId("replace-button").click();
    }

    await page.waitForSelector("text=flow shared successfully ", {
      timeout: 10000,
    });

    await page.waitForSelector("text=share", { timeout: 10000 });
    await page.waitForSelector("text=playground", { timeout: 10000 });
    await page.waitForSelector("text=api", { timeout: 10000 });

    await page.getByTestId("shared-button-flow").click();

    await page.waitForSelector("text=Publish workflow to the Langflow Store.", {
      timeout: 10000,
    });
    await page.waitForSelector('[data-testid="shared-button-flow"]', {
      timeout: 10000,
    });
    await page.waitForSelector("text=Share Flow", { timeout: 10000 });

    await page.getByTestId("share-modal-button-flow").click();

    replace = await page.getByTestId("replace-button").isVisible();

    if (replace) {
      await page.getByTestId("replace-button").click();
    }

    await page.waitForSelector("text=flow shared successfully ", {
      timeout: 10000,
    });
  },
);
