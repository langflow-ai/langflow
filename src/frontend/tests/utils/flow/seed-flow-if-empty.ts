import { expect, type Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TEXTS } from "../constants/texts";
import { TIMEOUTS } from "../constants/timeouts";
import { openTemplatesModal } from "./new-project-flow";
import { selectStarterTemplate } from "./select-starter-template";
import { waitForFlowEditorReady } from "./wait-for-flow-editor-ready";

export async function seedFlowIfEmpty(page: Page): Promise<boolean> {
  const emptyPageButton = page.getByTestId(TID.newProjectBtnEmptyPage);
  const regularNewProjectButton = page.getByTestId(TID.newProjectBtn);
  await expect
    .poll(
      async () =>
        (await emptyPageButton.isVisible().catch(() => false)) ||
        (await regularNewProjectButton.isVisible().catch(() => false)),
      { timeout: TIMEOUTS.standard },
    )
    .toBe(true);

  if (!(await emptyPageButton.isVisible())) {
    return false;
  }

  await openTemplatesModal(page, { fromEmptyPage: true });
  await selectStarterTemplate(page, TEXTS.templateBasicPrompting);
  await waitForFlowEditorReady(page);
  await page.goto("/");
  await expect(page.getByTestId("mainpage_title")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  return true;
}
