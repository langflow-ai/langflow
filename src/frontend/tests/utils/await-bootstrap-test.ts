import type { Page } from "@playwright/test";
import {
  openTemplatesModal,
  waitForNewProjectButton,
} from "./flow/new-project-flow";
import { seedFlowIfEmpty } from "./flow/seed-flow-if-empty";

export const awaitBootstrapTest = async (
  page: Page,
  options?: {
    skipGoto?: boolean;
    skipModal?: boolean;
    seedFlowIfEmpty?: boolean;
  },
) => {
  const prepareMainPage = async (shouldGoto: boolean) => {
    if (shouldGoto) {
      await page.goto("/");
    }

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    if (options?.seedFlowIfEmpty ?? true) {
      await seedFlowIfEmpty(page);
    }

    await waitForNewProjectButton(page);
  };

  await prepareMainPage(!options?.skipGoto);

  if (!options?.skipModal) {
    await openTemplatesModal(page);
  }
};
