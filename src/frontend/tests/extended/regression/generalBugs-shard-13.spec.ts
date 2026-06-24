import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";
import { renameFlow } from "../../utils/rename-flow";

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

test("should share component with share button", async ({ page }) => {
  skipIfMissing.storeApiKey();
  loadDotenvIfLocal(__dirname);

  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("api-key-button-store").click({
    timeout: 200000,
  });

  await page
    .getByPlaceholder(TEXTS.placeholderApiKey)
    .fill(process.env.STORE_API_KEY ?? "");

  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(1000);
  await expect(page.getByText(TEXTS.toastApiKeySaved)).toBeVisible();
  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await awaitBootstrapTest(page, {
    skipGoto: true,
  });

  await page.waitForTimeout(1000);

  const randomName = Math.random().toString(36).substring(2);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page
    .getByRole("heading", { name: TEXTS.templateBasicPrompting })
    .click();

  await renameFlow(page, { flowName: randomName });

  await page.waitForSelector('[data-testid="shared-button-flow"]', {
    timeout: 100000,
  });

  await page.getByTestId("shared-button-flow").first().click();
  await expect(page.getByText("Name:")).toBeVisible();
  await expect(page.getByText("Description:")).toBeVisible();
  await expect(page.getByText("Set workflow status to public")).toBeVisible();
  await page
    .getByText(
      "Attention: API keys in specified fields are automatically removed upon sharing.",
    )
    .isVisible();
  await expect(page.getByText("Export").first()).toBeVisible();
  await expect(page.getByText("Share Flow").first()).toBeVisible();
  await page.waitForTimeout(3000);

  await expect(page.getByText("Agent").first()).toBeVisible();
  await expect(page.getByText("Memory").first()).toBeVisible();
  await expect(page.getByText("Chain").first()).toBeVisible();
  await expect(page.getByText("Vector Store").first()).toBeVisible();
  await expect(page.getByText("Prompt").last()).toBeVisible();
  await page.getByTestId("public-checkbox").isChecked();

  const flowName = await page.getByTestId("input-flow-name").inputValue();
  const flowDescription = await page
    .getByPlaceholder("Flow description")
    .inputValue();
  await expect(page.getByText(flowName).last()).toBeVisible();
  await expect(page.getByText(flowDescription).last()).toBeVisible();
  await page.waitForTimeout(1000);

  // Trigger the actual share before asserting the success toast; re-sharing an
  // already-published flow surfaces a replace confirmation.
  await page.getByTestId("share-modal-button-flow").click();
  const replace = await page.getByTestId("replace-button").isVisible();
  if (replace) {
    await page.getByTestId("replace-button").click();
  }

  await expect(page.getByText("Flow shared successfully").last()).toBeVisible();
});
