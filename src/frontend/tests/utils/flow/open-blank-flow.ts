import { expect, type Page } from "@playwright/test";
import { awaitBootstrapTest } from "../await-bootstrap-test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";
import { waitForFlowEditorReady } from "./wait-for-flow-editor-ready";

/**
 * Bootstrap the app and open a blank flow.
 *
 * Replaces the 3-line ritual that appears in 50+ spec files:
 *   await awaitBootstrapTest(page);
 *   await page.waitForSelector('[data-testid="blank-flow"]', { timeout: 30000 });
 *   await page.getByTestId("blank-flow").click();
 */
export async function openBlankFlow(page: Page): Promise<string> {
  await awaitBootstrapTest(page);
  await page.waitForSelector(`[data-testid="${TID.blankFlow}"]`, {
    timeout: TIMEOUTS.standard,
  });
  const createResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST" &&
      url.pathname === "/api/v1/flows/"
    );
  });
  await page.getByTestId(TID.blankFlow).click();
  const createResponse = await createResponsePromise;
  expect(
    createResponse.ok(),
    `Creating a blank flow returned ${createResponse.status()}`,
  ).toBeTruthy();
  const createdFlow = await createResponse.json();
  const createdFlowId = (createdFlow as { id?: unknown })?.id;
  expect(
    typeof createdFlowId === "string" && createdFlowId.length > 0,
    "Creating a blank flow returned no flow id",
  ).toBeTruthy();
  await expect(page.getByTestId(TID.modalTitle)).toBeHidden({
    timeout: TIMEOUTS.standard,
  });
  await waitForFlowEditorReady(page);
  expect(
    new URL(page.url()).pathname.match(/\/flow\/([^/?#]+)/)?.[1],
    "The editor opened a different flow than the blank flow response",
  ).toBe(createdFlowId);
  return createdFlowId as string;
}
