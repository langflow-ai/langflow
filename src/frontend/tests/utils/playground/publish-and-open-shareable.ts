import type { BrowserContext, Page } from "@playwright/test";
import { expect } from "@playwright/test";
import { configureLoopbackOpenAI } from "../configure-loopback-openai";
import { TID } from "../constants/testIds";
import { TEXTS } from "../constants/texts";
import { ANIMATIONS, TIMEOUTS } from "../constants/timeouts";
import { buildFlowAndWait } from "../flow/build-flow-and-wait";
import { openStarterProject } from "../flow/open-starter-project";

export type PublishedFlow = {
  /** The new tab where the shareable playground opens. */
  playgroundPage: Page;
  /** The URL of the shareable playground (useful for reload-in-place tests). */
  url: string;
};

/**
 * End-to-end: open Basic Prompting, configure the loopback model, build, publish, toggle
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
  await configureLoopbackOpenAI(page);

  await buildFlowAndWait(page);

  await page.getByTestId(TID.publishButton).click();
  await page.waitForSelector(`[data-testid="${TID.shareablePlayground}"]`, {
    timeout: TIMEOUTS.medium,
  });
  await page.waitForTimeout(ANIMATIONS.fullscreenPlayground);
  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/?#]+)/)?.[1];
  if (!flowId) {
    throw new Error(`Expected a /flow/:id editor URL, got ${page.url()}`);
  }
  const publishResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "PATCH" &&
      url.pathname === `/api/v1/flows/${flowId}`
    );
  });
  await page.getByTestId(TID.publishSwitch).click();
  const publishResponse = await publishResponsePromise;
  expect(
    publishResponse.ok(),
    `Publishing flow ${flowId} returned ${publishResponse.status()}`,
  ).toBeTruthy();

  const pagePromise = context.waitForEvent("page");
  await page.getByTestId(TID.shareablePlayground).click();
  const playgroundPage = await pagePromise;
  await playgroundPage.waitForURL(new RegExp(`/playground/${flowId}/?$`), {
    timeout: TIMEOUTS.long,
  });
  await playgroundPage
    .getByPlaceholder(TEXTS.placeholderSendMessage)
    .waitFor({ state: "visible", timeout: TIMEOUTS.long });

  return { playgroundPage, url: playgroundPage.url() };
}
