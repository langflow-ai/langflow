import type { Page } from "@playwright/test";
import { awaitBootstrapTest } from "../await-bootstrap-test";
import { TID } from "../constants/testIds";

/**
 * Bootstrap the app, open the templates panel, and click the heading
 * for a starter project.
 *
 * Replaces the 3-step ritual that appears 50+ times across `core/integrations/`:
 *   await awaitBootstrapTest(page);
 *   await page.getByTestId("side_nav_options_all-templates").click();
 *   await page.getByRole("heading", { name: "<template name>" }).click();
 *
 * @param page          The Playwright page.
 * @param templateName  Exact heading text, e.g. "Basic Prompting".
 * @param options       skipBootstrap=true when the caller has already
 *                      bootstrapped (e.g. for AUTO_LOGIN=off flows).
 */
export async function openStarterProject(
  page: Page,
  templateName: string,
  options?: { skipBootstrap?: boolean },
): Promise<void> {
  if (!options?.skipBootstrap) {
    await awaitBootstrapTest(page);
  }
  await page.getByTestId(TID.sideNavAllTemplates).click();
  await page.getByRole("heading", { name: templateName }).first().click();
}
