import { expect, test } from "@playwright/test";

test("chat_io_teste", { tag: ["@release", "@workspace"] }, async ({ page }) => {
  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForSelector('[data-testid="modal-title"]', {
      timeout: 3000,
    });
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    state: "visible",
  });
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");
  await page.waitForSelector('[data-testid="outputsChat Output"]', {
    timeout: 2000,
  });

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat input");
  await page.waitForSelector('[data-testid="inputsChat Input"]', {
    timeout: 2000,
  });

  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  const elementsChatInput = await page
    .locator('[data-testid="handle-chatinput-shownode-message-right"]')
    .all();

  let visibleElementHandle;

  for (const element of elementsChatInput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  // Click and hold on the first element
  await visibleElementHandle.hover();
  await page.mouse.down();

  // Move to the second element

  const elementsChatOutput = await page
    .getByTestId("handle-chatoutput-shownode-text-left")
    .all();

  for (const element of elementsChatOutput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover();

  // Release the mouse
  await page.mouse.up();

  await page.getByTestId("fit_view").click();
  await page.getByText("Playground", { exact: true }).last().click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();
  await page.getByTestId("input-chat-playground").fill("teste");
  await page.getByTestId("button-send").first().click();
  const chat_input = page.getByTestId("chat-message-User-teste");
  await expect(chat_input).toHaveText("teste", { timeout: 10000 });
});
