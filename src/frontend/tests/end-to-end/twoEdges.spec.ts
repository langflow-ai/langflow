import { expect, test } from "@playwright/test";

test("user should be able to see multiple edges and interact with them", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.waitForTimeout(1000);

  await page.getByText("Vector Store RAG", { exact: true }).last().click();
  await page.waitForTimeout(3000);
  await page.getByText("Retriever", { exact: true }).first().isVisible();
  await page.getByText("Search Results", { exact: true }).first().isVisible();
  await page.getByTestId("icon-Eye").nth(24).click();
  await page.getByText("Retriever", { exact: true }).first().isHidden();
  await page.getByTestId("icon-ChevronDown").last().isVisible();
  await page.getByTestId("icon-ChevronDown").last().click();
  await page.getByText("Retriever", { exact: true }).first().isVisible();
  await page.getByText("Search Results", { exact: true }).first().isVisible();

  await page.getByTestId("icon-EyeOff").nth(0).isVisible();
});
