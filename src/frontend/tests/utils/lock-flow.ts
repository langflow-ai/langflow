import { expect, type Page } from "@playwright/test";
import { waitForFlowEditorReady } from "./flow/wait-for-flow-editor-ready";

type FlowLockState = {
  locked?: boolean;
};

function getFlowId(page: Page): string {
  const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
  if (!flowId) {
    throw new Error(`Expected a flow URL; got ${page.url()}`);
  }
  return flowId;
}

async function setFlowLocked(page: Page, locked: boolean): Promise<void> {
  const flowId = getFlowId(page);
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await expect(page.getByTestId("lock-flow-switch")).toHaveAttribute(
    "data-state",
    locked ? "checked" : "unchecked",
  );
  await expect(page.getByTestId("save-flow-settings")).toBeEnabled();
  const [saveResponse] = await Promise.all([
    page.waitForResponse((response) => {
      const request = response.request();
      if (
        request.method() !== "PATCH" ||
        new URL(response.url()).pathname !== `/api/v1/flows/${flowId}`
      ) {
        return false;
      }
      const body = request.postDataJSON() as FlowLockState | null;
      return body?.locked === locked;
    }),
    page.getByTestId("save-flow-settings").click(),
  ]);
  expect(saveResponse.ok()).toBe(true);

  await page.waitForSelector('[data-testid="save-flow-settings"]', {
    state: "hidden",
    timeout: 10000,
  });

  const persistedResponse = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(persistedResponse.ok()).toBe(true);
  const persistedFlow = (await persistedResponse.json()) as FlowLockState;
  expect(persistedFlow.locked).toBe(locked);

  await page.reload();
  await waitForFlowEditorReady(page);
  await page.getByTestId("flow_name").click();
  await expect(page.getByTestId("lock-flow-switch")).toHaveAttribute(
    "data-state",
    locked ? "checked" : "unchecked",
  );
  await page.getByTestId("cancel-flow-settings").click();
  await expect(page.getByTestId("save-flow-settings")).toBeHidden({
    timeout: 10000,
  });
}

export async function lockFlow(page: Page): Promise<void> {
  await setFlowLocked(page, true);
}

export async function unlockFlow(page: Page): Promise<void> {
  await setFlowLocked(page, false);
}
