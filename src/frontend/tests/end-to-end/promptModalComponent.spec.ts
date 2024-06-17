import { expect, test } from "@playwright/test";

test("PromptTemplateComponent", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

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
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("prompt");

  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="inputsPrompt"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTestId("prompt-input-template").click();

  await page
    .getByTestId("modal-prompt-input-template")
    .fill("{prompt} example {prompt1}");

  let value = await page
    .getByTestId("modal-prompt-input-template")
    .inputValue();

  if (value != "{prompt} example {prompt1}") {
    expect(false).toBeTruthy();
  }

  let valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
  if (valueBadgeOne != "prompt") {
    expect(false).toBeTruthy();
  }

  let valueBadgeTwo = await page.locator('//*[@id="badge1"]').innerText();
  if (valueBadgeTwo != "prompt1") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("genericModalBtnSave").click();

  await page.getByTestId("div-textarea-prompt").click();
  await page.getByTestId("textarea-prompt").fill("prompt_value_!@#!@#");

  value = await page.getByTestId("textarea-prompt").inputValue();

  if (value != "prompt_value_!@#!@#") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("save-button-modal").click();

  const replace = await page.getByTestId("replace-button").isVisible();

  if (replace) {
    await page.getByTestId("replace-button").click();
  }

  await page.getByTestId("div-textarea-prompt1").click();
  await page
    .getByTestId("textarea-prompt1")
    .fill("prompt_name_test_123123!@#!@#");

  value = await page.getByTestId("textarea-prompt1").inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page.getByTestId("textarea-prompt1").inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  value = await page.locator('//*[@id="textarea-edit-prompt"]').inputValue();

  if (value != "prompt_value_!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page.locator('//*[@id="textarea-edit-prompt1"]').inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page
    .locator('//*[@id="prompt-area-edit-template"]')
    .innerText();

  if (value != "{prompt} example {prompt1}") {
    expect(false).toBeTruthy();
  }

  await page
    .locator('//*[@id="textarea-edit-prompt1"]')
    .fill("prompt_edit_test_12312312321!@#$");
  await page
    .locator('//*[@id="textarea-edit-prompt"]')
    .fill("prompt_edit_test_44444444444!@#$");

  await page.locator('//*[@id="showtemplate"]').click();
  expect(await page.locator('//*[@id="showtemplate"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showtemplate"]').click();
  expect(
    await page.locator('//*[@id="showtemplate"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showtemplate"]').click();
  expect(await page.locator('//*[@id="showtemplate"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showtemplate"]').click();
  expect(
    await page.locator('//*[@id="showtemplate"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeTruthy();

  await page.getByText("Save Changes", { exact: true }).click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeTruthy();

  value = await page.locator('//*[@id="textarea-edit-prompt"]').inputValue();

  if (value != "prompt_edit_test_44444444444!@#$") {
    expect(false).toBeTruthy();
  }

  value = await page.locator('//*[@id="textarea-edit-prompt1"]').inputValue();

  if (value != "prompt_edit_test_12312312321!@#$") {
    expect(false).toBeTruthy();
  }

  value = await page
    .locator('//*[@id="prompt-area-edit-template"]')
    .innerText();

  if (value != "{prompt} example {prompt1}") {
    expect(false).toBeTruthy();
  }
});
