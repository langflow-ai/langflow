import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("fresh start playground", async ({ page }) => {
  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

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
  await page.getByTestId('input-chat-playground').click();
  await page.getByTestId('input-chat-playground').fill('message 1');
  await page.getByTestId('chat-message-User-message 1').click();
  await page.getByTestId('chat-message-AI-message 1').getByText('message').click();
  await page.getByText('Default Session').click();
  await page.getByText('👋 Langflow Chat').click();
  await page.getByText('Default SessionRenameMessage').click();
  await page.getByTestId('chat-message-User-message 1').click();
  await page.getByTestId('chat-message-AI-message 1').getByText('message').click();
  await page.locator('div').filter({ hasText: /^Usermessage 1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByText('ChatDefault SessionRenameMessage logsDeleteNew ChatUsermessage').click();
  await page.getByTestId('chat-message-User-message 1').click();
  await page.locator('div').filter({ hasText: /^Usermessage 1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByTestId('textarea').fill('edit_1');
  await page.getByRole('button', { name: 'Save' }).click();
  await page.getByTestId('chat-message-User-edit_1').click();
  await page.locator('div').filter({ hasText: /^Useredit_1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByTestId('textarea').fill('cancel_edit');
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByTestId('chat-message-User-edit_1').click();
  await page.locator('div').filter({ hasText: /^Useredit_1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByTestId('textarea').fill('cancel_edit_blur');
  await page.getByLabel('Playground').locator('div').filter({ hasText: 'ChatDefault' }).nth(2).click();
  await page.getByTestId('chat-message-User-edit_1').click();
  await page.getByTestId('chat-message-AI-message 1').getByText('message').click();
  await page.locator('div').filter({ hasText: /^AImessage 1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByTestId('textarea').fill('edit_bot_1');
  await page.getByRole('button', { name: 'Save' }).click();
  await page.locator('div').filter({ hasText: /^AIedit_bot_1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByTestId('textarea').fill('edit_bot_cancel');
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByText('edit_bot_1').click();
  await page.locator('div').filter({ hasText: /^AIedit_bot_1$/ }).getByRole('button').click();
  await page.getByTestId('textarea').click();
  await page.getByTestId('textarea').fill('edit_bot_blur_cancel');
  await page.locator('div').filter({ hasText: /^AI$/ }).first().click();

  await page.getByRole('combobox').click();
  await page.getByLabel('Message logs').click();
  await page.getByText('Page 1 of 1', { exact: true }).click();
  await page.getByRole('combobox').click();
  await page.getByLabel('Rename').getByText('Rename').click();
  await page.getByRole('textbox').fill('new name');
  await page.getByLabel('Chat', { exact: true }).getByRole('button').nth(1).click();
  await page.getByRole('combobox').click();
  await page.getByLabel('Rename').getByText('Rename').click();
  await page.getByRole('textbox').fill('cancel name');
  await page.getByRole('button').first().click();
  await page.getByText('new name').click();
  await page.getByText('new name').click();
  await page.getByRole('combobox').click();
  await page.getByLabel('Rename').getByText('Rename').click();
  await page.getByRole('textbox').fill('cancel_blur');
  await page.getByLabel('Chat', { exact: true }).click();
  await page.getByText('new name').click();
  await page.getByText('new name').click();

  await page.getByRole('combobox').click();
  await page.getByLabel('Delete').click();
  await page.getByText('No memories available.').click();
  await page.locator('form').getByRole('button').click();
  await page.getByTestId('input-chat-playground').click();
  await page.getByTestId('input-chat-playground').fill('session_after_delete');
  await page.getByRole('button', { name: 'New Chat' }).click();
  await page.getByText('👋 Langflow Chat').click();
  await page.getByTestId('input-chat-playground').click();

  await page.getByTestId('input-chat-playground').fill('second session');
  await page.getByTestId('chat-message-User-second session').click();
  await page.getByTestId('chat-message-AI-second session').getByText('second session').click();
  await page.getByLabel('Playground').getByText('Session Oct 09, 05:35:39 PM').click();
  await page.getByText('new nameRenameMessage').click();
  await page.getByTestId('chat-message-User-session_after_delete').click();
  await page.getByText('Session Oct 09, 05:35:39 PMRenameMessage logsDelete').click();
  await page.getByTestId('chat-message-User-second session').click();
});
