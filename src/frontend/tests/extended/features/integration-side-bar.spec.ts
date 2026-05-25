import { expect, test } from "../../fixtures";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

test(
  "user should be able to see integrations in the sidebar when bundles is selected",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);
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
