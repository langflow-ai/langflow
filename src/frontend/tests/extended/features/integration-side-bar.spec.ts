import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to see integrations in the sidebar if mvp_components is true",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="shad-sidebar"]', {
      timeout: 30000,
    });
    await expect(page.getByText("Bundles")).toBeVisible();
    await expect(page.getByText("Notion")).toBeVisible();
    await expect(page.getByText("AssemblyAI")).toBeVisible();
  },
);
