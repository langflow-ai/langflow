import { expect, test } from "@playwright/test";

test("chat_io_teste", async ({ page }) => {
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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat output");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

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

  await page.getByLabel("fit view").click();
  await page.getByText("Playground", { exact: true }).last().click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();
  await page.getByTestId("input-chat-playground").fill("teste");
  await page.getByTestId("icon-LucideSend").first().click();
  const chat_output = page.getByTestId("chat-message-AI-teste");
  const chat_input = page.getByTestId("chat-message-User-teste");
  await expect(chat_output).toHaveText("teste");
  await expect(chat_input).toHaveText("teste");
});
