import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to see multiple edges and interact with them",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByText("Vector Store RAG", { exact: true }).last().click();
    await expect(page.getByText("Retriever", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Search Results", { exact: true }).first()).toBeVisible();
    await page.getByTestId("canvas_controls_dropdown").click();

    const focusElementsOnBoard = async ({ page }) => {
      await page.waitForSelector('[data-testid="fit_view"]', {
        timeout: 30000,
      });
      const focusElements = await page.getByTestId("fit_view");
      await focusElements.click();
    };

    await focusElementsOnBoard({ page });
    await page.getByTestId("canvas_controls_dropdown").click({ force: true });

    await page.getByText("Retriever", { exact: true }).first().isHidden();
    await expect(page.getByTestId("icon-ChevronDown").last()).toBeVisible();
    await page.getByTestId("icon-ChevronDown").last().click();
    await expect(page.getByText("Retriever", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Search Results", { exact: true }).first()).toBeVisible();
    await expect(page.getByTestId("icon-EyeOff").nth(0)).toBeVisible();
  },
);
