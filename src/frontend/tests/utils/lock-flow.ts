import { expect, type Page } from "@playwright/test";

export async function lockFlow(page: Page) {
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await expect(page.getByTestId("lock-flow-switch")).toHaveAttribute(
    "data-state",
    "checked",
  );
  await expect(page.getByTestId("save-flow-settings")).toBeEnabled();
  const [saveResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        /\/api\/v1\/flows\/[^/]+$/.test(new URL(response.url()).pathname),
    ),
    page.getByTestId("save-flow-settings").click(),
  ]);
  expect(saveResponse.ok()).toBe(true);

  await page.waitForSelector('[data-testid="save-flow-settings"]', {
    state: "hidden",
    timeout: 10000,
  });
  await expect(page.getByTestId("icon-Lock")).toBeVisible();
}

export async function unlockFlow(page: Page) {
  await page.getByTestId("flow_name").click();
  await page.getByTestId("lock-flow-switch").click();
  await expect(page.getByTestId("lock-flow-switch")).toHaveAttribute(
    "data-state",
    "unchecked",
  );
  await expect(page.getByTestId("save-flow-settings")).toBeEnabled();
  const [saveResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        /\/api\/v1\/flows\/[^/]+$/.test(new URL(response.url()).pathname),
    ),
    page.getByTestId("save-flow-settings").click(),
  ]);
  expect(saveResponse.ok()).toBe(true);
  await page.waitForSelector('[data-testid="save-flow-settings"]', {
    state: "hidden",
    timeout: 5000,
  });
}
