import type { Page } from "playwright/test";
import { addFlowToTestOnEmptyLangflow } from "./add-flow-to-test-on-empty-langflow";

export const awaitBootstrapTest = async (
  page: Page,
  options?: {
    skipGoto?: boolean;
    skipModal?: boolean;
  },
) => {
  if (!options?.skipGoto) {
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

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

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
        await page.getByTestId("new-project-btn").click();
        await page.waitForSelector('[data-testid="modal-title"]', {
          timeout: 5000,
        });
        modalCount = await page.getByTestId("modal-title")?.count();
      } catch (error) {
        if (attempts >= maxAttempts) {
          throw new Error(
            `Failed to open modal after ${maxAttempts} attempts: ${error}`,
          );
        }
        // Wait a bit before retrying
        await page.waitForTimeout(1000);
      }
    }

    if (modalCount === 0) {
      throw new Error(`Modal did not appear after ${maxAttempts} attempts`);
    }
  }
};
