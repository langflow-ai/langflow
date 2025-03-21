import { test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to see multiple edges and interact with them",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByText("Vector Store RAG", { exact: true }).last().click();
    await page.getByText("Retriever", { exact: true }).first().isVisible();
    await page.getByText("Search Results", { exact: true }).first().isVisible();

    const focusElementsOnBoard = async ({ page }) => {
      await page.waitForSelector('[data-testid="fit_view"]', {
        timeout: 30000,
      });
      const focusElements = await page.getByTestId("fit_view");
      await focusElements.click();
    };

    await focusElementsOnBoard({ page });

    await page.getByText("Retriever", { exact: true }).first().isHidden();
    await page.getByTestId("icon-ChevronDown").last().isVisible();
    await page.getByTestId("icon-ChevronDown").last().click();
    await page.getByText("Retriever", { exact: true }).first().isVisible();
    await page.getByText("Search Results", { exact: true }).first().isVisible();

    await page.getByTestId("icon-EyeOff").nth(0).isVisible();
  },
);
