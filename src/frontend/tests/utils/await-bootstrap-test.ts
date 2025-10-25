import type { Page } from "playwright/test";
import { checkRateLimit } from "../fixtures";
import { addFlowToTestOnEmptyLangflow } from "./add-flow-to-test-on-empty-langflow";

export const awaitBootstrapTest = async (
  page: Page,
  options?: {
    skipGoto?: boolean;
    skipModal?: boolean;
  },
  test?: any,
) => {
  if (!options?.skipGoto) {
    await page.goto("/");
  }

  if (await checkRateLimit(page)) {
    console.warn("Rate limit detected, skipping test");
    test.skip();
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

    while (modalCount === 0) {
      await page.getByTestId("new-project-btn").click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }
  }
};
