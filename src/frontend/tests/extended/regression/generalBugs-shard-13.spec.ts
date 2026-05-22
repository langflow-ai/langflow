import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";

test(
  "should be able to share a component on the store by clicking on the share button on the canvas (requires store API key)",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    skipIfMissing.storeApiKey();
    loadDotenvIfLocal(__dirname);
    await awaitBootstrapTest(page);

    await page.getByText(TEXTS.close, { exact: true }).click();

    await page.waitForSelector('[data-testid="user-profile-settings"]', {
      timeout: 3000,
    });
    await page.getByTestId("user-profile-settings").click();

    await page.getByText(TEXTS.settings, { exact: true }).first().click();

    await page
      .getByPlaceholder(TEXTS.placeholderApiKey)
      .fill(process.env.STORE_API_KEY ?? "");

    await page.getByTestId("api-key-save-button-store").click();

    await expect(page.getByText("API key saved successfully")).toBeVisible({
      timeout: 3000,
    });

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await expect(page.getByText("New Flow", { exact: true })).toBeVisible({
      timeout: 3000,
    });

    await openTemplatesModal(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
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
