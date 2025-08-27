import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to see integrations in the sidebar when bundles is selected",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="shad-sidebar"]', {
      timeout: 30000,
    });
    await page.getByTestId("sidebar-nav-bundles").click();
    await expect(
      page.locator('[data-sidebar="group-label"]', { hasText: "Bundles" }),
    ).toBeVisible();
    await expect(page.getByText("Notion")).toBeVisible();
    await expect(page.getByText("AssemblyAI")).toBeVisible();
  },
);
