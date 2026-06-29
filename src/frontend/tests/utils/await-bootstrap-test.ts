import type { Page } from "@playwright/test";
import { addFlowToTestOnEmptyLangflow } from "./add-flow-to-test-on-empty-langflow";
import {
  openTemplatesModal,
  waitForNewProjectButton,
} from "./flow/new-project-flow";

export const awaitBootstrapTest = async (
  page: Page,
  options?: {
    skipGoto?: boolean;
    skipModal?: boolean;
  },
) => {
  const prepareMainPage = async (shouldGoto: boolean) => {
    if (shouldGoto) {
      await page.goto("/");
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    const countEmptyButton = await page
      .getByTestId("new_project_btn_empty_page")
      .count();
    if (countEmptyButton > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await waitForNewProjectButton(page);
  };

  await prepareMainPage(!options?.skipGoto);

  if (!options?.skipModal) {
    let modalCount = 0;
    try {
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (_error) {
      modalCount = 0;
    }

    let attempts = 0;
    const maxAttempts = 5;

    while (modalCount === 0 && attempts < maxAttempts) {
      attempts++;
      try {
        await openTemplatesModal(page);
        modalCount = await page.getByTestId("modal-title")?.count();
      } catch (error) {
        if (attempts >= maxAttempts) {
          throw new Error(
            `Failed to open modal after ${maxAttempts} attempts: ${error}`,
          );
        }
        // Wait a bit before retrying
        await page.waitForTimeout(1000);
        if (!options?.skipGoto) {
          await prepareMainPage(true);
        }
      }
    }

    if (modalCount === 0) {
      throw new Error(`Modal did not appear after ${maxAttempts} attempts`);
    }
  }
};
