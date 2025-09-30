import { expect, type Page } from "playwright/test";
import { convertTestName } from "./convert-test-name";

export const cleanOldFolders = async (page: Page) => {
  let numberOfFolders = await page.getByText("New Project").count();

  while (numberOfFolders > 0) {
    const getFirstFolderName = convertTestName(
      (await page.getByText("New Project").first().textContent()) as string,
    );

    await page
      .getByText("New Project")
      .first()
      .hover()
      .then(async () => {
        await page
          .getByTestId(`more-options-button_${getFirstFolderName}`)
          .last()
          .click();
        await page.getByText("Delete", { exact: true }).last().click();
        await page.getByText("Delete", { exact: true }).last().click();
      });

    await page.waitForTimeout(500);
    numberOfFolders--;
  }
};
