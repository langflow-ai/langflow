import type { BrowserContext, Page, Request } from "@playwright/test";
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

/** `access_type` carried by a flow PATCH body, if any. */
function patchAccessType(request: Request): string | undefined {
  try {
    const body = request.postDataJSON() as { access_type?: string } | null;
    return body?.access_type;
  } catch {
    return undefined;
  }
}

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
  // The switch flushes any pending canvas autosave before it changes access,
  // and that flush is a PATCH to this same URL. Only the access-type PATCH
  // publishes the flow, so match on its body rather than on the first response
  // (nightly 33576072242: the autosave PATCH resolved first, the item was
  // clicked while the flow was still private, and no tab ever opened).
  const publishResponsePromise = page.waitForResponse((response) => {
    const request = response.request();
    if (request.method() !== "PATCH") return false;
    if (new URL(response.url()).pathname !== `/api/v1/flows/${flowId}`) {
      return false;
    }
    return patchAccessType(request) === "PUBLIC";
  });
  await page.getByTestId(TID.publishSwitch).click();
  const publishResponse = await publishResponsePromise;
  expect(
    publishResponse.ok(),
    `Publishing flow ${flowId} returned ${publishResponse.status()}`,
  ).toBeTruthy();

  // The menu item only renders the playground link once the store reflects
  // PUBLIC access, which lands after the response, so wait for the link itself
  // rather than clicking the item as soon as the request has returned.
  const shareableLink = page
    .getByTestId(TID.shareablePlayground)
    .getByRole("link");
  await expect(shareableLink).toBeVisible({ timeout: TIMEOUTS.medium });
  const pagePromise = context.waitForEvent("page");
  await shareableLink.click();
  const playgroundPage = await pagePromise;
  await playgroundPage.waitForURL(new RegExp(`/playground/${flowId}/?$`), {
    timeout: TIMEOUTS.long,
  });
  await playgroundPage
    .getByPlaceholder(TEXTS.placeholderSendMessage)
    .waitFor({ state: "visible", timeout: TIMEOUTS.long });

  return { playgroundPage, url: playgroundPage.url() };
}
