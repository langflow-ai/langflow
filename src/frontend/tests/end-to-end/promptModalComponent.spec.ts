import { expect, test } from "@playwright/test";

test("PromptTemplateComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("promptTemplate");

  await page.waitForTimeout(2000);

  await page
    .locator('//*[@id="promptsPromptTemplate"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("prompt-input-0").click();

  // await page.getByTestId("edit-prompt-sanitized").click();
  // await page.getByTestId("modal-title").click();
  await page
    .getByTestId("modal-prompt-input-0")
    .fill("{prompt} example {prompt1}");

  let value = await page.getByTestId("modal-prompt-input-0").inputValue();

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
  await page.getByTestId("text-area-modal").fill("prompt_value_!@#!@#");

  value = await page.getByTestId("text-area-modal").inputValue();

  if (value != "prompt_value_!@#!@#") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("genericModalBtnSave").click();

  await page.getByTestId("div-textarea-prompt1").click();
  await page
    .getByTestId("text-area-modal")
    .fill("prompt_name_test_123123!@#!@#");

  value = await page.getByTestId("text-area-modal").inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page.getByTestId("text-area-modal").inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("genericModalBtnSave").click();

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

  await page.locator('//*[@id="saveChangesBtn"]').click();

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
