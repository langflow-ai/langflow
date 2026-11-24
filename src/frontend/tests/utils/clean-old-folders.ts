import { expect, type Page } from "@playwright/test";
import { TEXTS } from "../utils/constants/texts";
import { getSidebarProjectOptionsButton } from "./project-sidebar";
export const cleanOldFolders = async (page: Page) => {
  let numberOfFolders = await page.getByText(TEXTS.labelNewProject).count();

  while (numberOfFolders > 0) {
    const getFirstFolderName = (await page
      .getByText(TEXTS.labelNewProject)
      .first()
      .textContent()) as string;

    await page.getByText(TEXTS.labelNewProject).first().hover();

    const moreOptionsBtn = getSidebarProjectOptionsButton(
      page,
      getFirstFolderName,
    ).last();
    await moreOptionsBtn.waitFor({ state: "visible", timeout: 5000 });
    await moreOptionsBtn.click();
    await page.getByText(TEXTS.delete, { exact: true }).last().click();
    const [deleteResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" &&
          /\/api\/v1\/projects\/[^/]+$/.test(new URL(response.url()).pathname),
      ),
      page.getByTestId("btn_delete_delete_confirmation_modal").click(),
    ]);
    expect(deleteResponse.ok()).toBe(true);

    numberOfFolders--;
    await expect(page.getByText(TEXTS.labelNewProject)).toHaveCount(
      numberOfFolders,
    );
  }
};
