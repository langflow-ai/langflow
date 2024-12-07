import { test } from "@playwright/test";

test(
  "user should be able to see multiple edges and interact with them",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

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

    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByText("Retriever", { exact: true }).first().isHidden();
    await page.getByTestId("icon-ChevronDown").last().isVisible();
    await page.getByTestId("icon-ChevronDown").last().click();
    await page.getByText("Retriever", { exact: true }).first().isVisible();
    await page.getByText("Search Results", { exact: true }).first().isVisible();

    await page.getByTestId("icon-EyeOff").nth(0).isVisible();
  },
);
