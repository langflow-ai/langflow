import type { BrowserContext, Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { ANIMATIONS, TIMEOUTS } from "../constants/timeouts";
import { buildFlowAndWait } from "../flow/build-flow-and-wait";
import { openStarterProject } from "../flow/open-starter-project";
import { initialGPTsetup } from "../initialGPTsetup";

export type PublishedFlow = {
  /** The new tab where the shareable playground opens. */
  playgroundPage: Page;
  /** The URL of the shareable playground (useful for reload-in-place tests). */
  url: string;
};

/**
 * End-to-end: open Basic Prompting, configure GPT, build, publish, toggle
 * the public switch, and open the shareable playground in a new tab.
 *
 * Replaces 4 separate inline implementations (auth, persistence,
 * token-display, publish-flow specs) — each of which had a different
 * return contract.
 */
export async function publishBasicPromptingAndOpenShareablePlayground(
  page: Page,
  context: BrowserContext,
  options?: { skipBootstrap?: boolean },
): Promise<PublishedFlow> {
  await openStarterProject(page, "Basic Prompting", {
    skipBootstrap: options?.skipBootstrap,
  });
  await initialGPTsetup(page);

  await buildFlowAndWait(page);

  await page.getByTestId(TID.publishButton).click();
  await page.waitForSelector(`[data-testid="${TID.shareablePlayground}"]`, {
    timeout: TIMEOUTS.medium,
  });
  await page.waitForTimeout(ANIMATIONS.fullscreenPlayground);
  await page.getByTestId(TID.publishSwitch).click();
  await page.waitForTimeout(ANIMATIONS.publishTogglePropagation);

  const pagePromise = context.waitForEvent("page");
  await page.getByTestId(TID.shareablePlayground).click();
  const playgroundPage = await pagePromise;
  await playgroundPage.waitForTimeout(ANIMATIONS.shareablePlaygroundMount);

  return { playgroundPage, url: playgroundPage.url() };
}
