import { Page } from "playwright/test";

export const awaitBootstrapTest = async (page: Page) => {
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
};
